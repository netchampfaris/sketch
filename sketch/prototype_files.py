# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The on-disk tree of one Prototype, and the path guard.

`name` is always the Prototype's hash primary key, never its slug. A slug is
unique per owner only, so two users with `dashboard` would share a directory.

Every agent-supplied path goes through `safe_join` and nothing else. It guards
where a path points and also how it is shaped: depth and segment length. Every
write goes through `preflight`, which holds the quotas that bound the tree in
files, bytes and folders.
"""

import io
import os
import posixpath
import shutil
import zipfile

import frappe

ROOT = ("private", "files", "sketch")

#: The most bytes `read_text` returns for one file. A Prototype file is a Vue
#: single-file component or a small module, so this is far above any real one.
#: It caps the reply for a file that is not.
MAX_TEXT_BYTES = 512 * 1024

#: The most files one write call may carry. It bounds the work one MCP request
#: buys, so a 25 MB body of one-byte entries cannot create a whole file system.
MAX_BATCH_FILES = 100

#: The most bytes one file may hold. A single-file component is a few kilobytes,
#: so this only stops a file used as storage.
MAX_FILE_BYTES = 1_000_000

#: The most files one tree may hold. Every reader loads the whole tree
#: (`viewer.payload`, `api.export_prototype`), so the tree is the reader's cost.
MAX_TREE_FILES = 500

#: The most bytes one tree may hold. Same reason as MAX_TREE_FILES, and it is
#: what keeps a guest read of a public Prototype bounded.
MAX_TREE_BYTES = 20_000_000

#: The most segments one path may hold, the file name included. A Prototype
#: tree is `src/pages`, `src/components`, `src/App.vue` and `src/router.ts`, so
#: it is shallow by nature. The deepest path in a vendored Recipe is 4 segments
#: (`src/components/settings/PreferencesPanel.vue`).
MAX_PATH_DEPTH = 10

#: The most UTF-8 bytes one path segment may hold. The longest name in a
#: vendored Recipe is 22 bytes (`NotificationsPanel.vue`). This also stays
#: under the 255 byte name limit of ext4, which `open()` reports as an OSError
#: that carries the absolute path.
MAX_SEGMENT_BYTES = 100

#: The most directories one tree may hold, the Prototype root not counted. The
#: largest vendored Recipe holds 4. Depth is the quota the file counters miss:
#: `_walk` yields files only, so 20 one-byte files at depth 800 made 16,020
#: directories and 63 MB that no file quota saw, and `delete_file` left every
#: one of them behind. Every walk in this module is O(directories), and
#: `revision()` runs on a Viewer poll every two seconds.
MAX_TREE_DIRS = 100


def prototype_dir(name: str) -> str:
	"""Absolute path to sites/<site>/private/files/sketch/<name>.

	Does not create the directory.
	"""
	if not name or "/" in name or "\\" in name or name in (".", ".."):
		frappe.throw(frappe._("Invalid prototype id"), frappe.ValidationError)

	return os.path.abspath(frappe.get_site_path(*ROOT, name))


def safe_join(name: str, rel: str) -> str:
	"""The path guard. Return the absolute path of `rel` inside the Prototype.

	Rejects an empty path, an absolute path, any `..` segment, and any result
	that leaves the Prototype directory after `os.path.realpath`. A symlink
	that points out of the tree is caught by the realpath step.

	It also rejects a path deeper than `MAX_PATH_DEPTH` and a segment longer
	than `MAX_SEGMENT_BYTES`. Shape is a quota, not a courtesy: a path is what
	makes `write_files` call `os.makedirs`, and a directory costs an inode and
	a block that the file counters in `preflight` never see.
	"""
	base = prototype_dir(name)

	if not isinstance(rel, str) or not rel.strip():
		frappe.throw(frappe._("Path must not be empty"), frappe.ValidationError)

	rel = rel.strip().replace("\\", "/")

	if rel.startswith("/") or os.path.isabs(rel) or (len(rel) > 1 and rel[1] == ":"):
		frappe.throw(
			frappe._("Path must be relative to the prototype: {0}").format(rel),
			frappe.ValidationError,
		)

	if "\x00" in rel:
		frappe.throw(frappe._("Path must not contain a null byte"), frappe.ValidationError)

	if ".." in rel.split("/"):
		frappe.throw(
			frappe._("Path must not contain '..': {0}").format(rel),
			frappe.ValidationError,
		)

	normalised = posixpath.normpath(rel)
	if normalised in (".", "..") or normalised.startswith("../") or normalised.startswith("/"):
		frappe.throw(
			frappe._("Path must stay inside the prototype: {0}").format(rel),
			frappe.ValidationError,
		)

	segments = normalised.split("/")
	if len(segments) > MAX_PATH_DEPTH:
		frappe.throw(
			frappe._("Path {0} is {1} folders deep. The limit is {2}.").format(
				rel, len(segments), MAX_PATH_DEPTH
			),
			frappe.ValidationError,
		)

	for segment in segments:
		if len(segment.encode("utf-8")) > MAX_SEGMENT_BYTES:
			frappe.throw(
				frappe._("A name in the path is longer than {0} bytes: {1}").format(
					MAX_SEGMENT_BYTES, segment[:40]
				),
				frappe.ValidationError,
			)

	target = os.path.realpath(os.path.join(base, normalised))
	real_base = os.path.realpath(base)

	if target != real_base and not target.startswith(real_base + os.sep):
		frappe.throw(
			frappe._("Path must stay inside the prototype: {0}").format(rel),
			frappe.ValidationError,
		)

	return target


def _walk(name: str):
	"""Yield (relative path, absolute path) for every real file in the tree.

	Symlinks are skipped. They are the one entry that can point out of the tree.
	"""
	base = prototype_dir(name)
	if not os.path.isdir(base):
		return

	for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
		dirnames[:] = [d for d in dirnames if not os.path.islink(os.path.join(dirpath, d))]
		for filename in sorted(filenames):
			absolute = os.path.join(dirpath, filename)
			if os.path.islink(absolute) or not os.path.isfile(absolute):
				continue
			yield os.path.relpath(absolute, base).replace(os.sep, "/"), absolute


def _walk_dirs(name: str):
	"""Yield the absolute path of every real directory under the tree root.

	The root itself is not yielded, because it is not a directory the agent
	made. Symlinked directories are skipped, for the reason `_walk` skips
	symlinked files. `preflight` counts what this yields, so a directory is a
	quota the same way a file is.
	"""
	base = prototype_dir(name)
	if not os.path.isdir(base):
		return

	for dirpath, dirnames, _filenames in os.walk(base, followlinks=False):
		dirnames[:] = [d for d in dirnames if not os.path.islink(os.path.join(dirpath, d))]
		for dirname in sorted(dirnames):
			yield os.path.join(dirpath, dirname)


def _prune_empty_dirs(name: str, start: str) -> None:
	"""Remove every empty directory from `start` up to the Prototype root.

	A delete that removes the file and leaves the folders behind lets a tree
	hold directories that no quota counts: the tree reads as empty and the next
	batch passes `preflight` again, while the inodes stay.

	The root is the stop. The loop runs only while the path is strictly inside
	the root, so a prune never removes the root and never reaches the private
	files folder above it. `os.path.realpath` is what makes that test true: a
	symlinked directory resolves out of the root and stops the walk.

	`os.rmdir` removes an empty directory only. A directory that still holds a
	file, or that a concurrent writer refilled, raises OSError and ends the
	walk up.
	"""
	base = os.path.realpath(prototype_dir(name))
	current = os.path.realpath(start)

	while current != base and current.startswith(base + os.sep):
		try:
			os.rmdir(current)
		except OSError:
			return

		current = os.path.dirname(current)


def list_files(name: str) -> list[dict]:
	"""Every file in the tree as {"path", "size"}, sorted by path."""
	out = []
	for rel, absolute in _walk(name):
		try:
			out.append({"path": rel, "size": os.path.getsize(absolute)})
		except OSError:
			continue

	return sorted(out, key=lambda row: row["path"])


def read_text(name: str, path: str, limit: int = MAX_TEXT_BYTES) -> dict:
	"""One file as {"path", "size", "content", "truncated"}, for a reader.

	`read_files` is the agent's door and it returns a file whole. This one
	answers a browser, so it stops at `limit` bytes and says when it did. The
	size is the file's own size, not the length of the content returned.

	Refuses a file that is not UTF-8 text. Every file an agent writes is
	source, so this only fires for something no viewer could print anyway.
	"""
	absolute = safe_join(name, path)
	if not os.path.isfile(absolute):
		frappe.throw(frappe._("No such file: {0}").format(path), frappe.ValidationError)

	size = os.path.getsize(absolute)
	with open(absolute, "rb") as handle:
		raw = handle.read(limit)

	# A null byte is the one cheap proof that this is not source. It is checked
	# before the decode, because a binary file that happens to decode would
	# otherwise reach the browser as a screen of control characters.
	if b"\x00" in raw:
		frappe.throw(frappe._("{0} is not a text file").format(path), frappe.ValidationError)

	truncated = size > len(raw)
	try:
		content = raw.decode("utf-8")
	except UnicodeDecodeError:
		if not truncated:
			frappe.throw(frappe._("{0} is not a text file").format(path), frappe.ValidationError)
		# The cut landed inside a character. Dropping that one partial
		# character is the whole repair: the caller already knows the tail is
		# missing, because `truncated` says so.
		content = raw.decode("utf-8", errors="ignore")

	return {"path": path, "size": size, "content": content, "truncated": truncated}


def zip_bytes(name: str, folder: str) -> bytes:
	"""The whole tree as one zip, with every file under `folder`/.

	The folder is why an unzip does not scatter `src/` and `README.md` into
	whatever directory the user ran it in.

	Symlinks never appear, because `_walk` skips them. A file that cannot be
	read, or whose timestamp predates 1980 and so has no place in a zip
	header, is left out rather than failing the whole archive.
	"""
	buffer = io.BytesIO()
	with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
		for rel, absolute in _walk(name):
			try:
				archive.write(absolute, arcname=f"{folder}/{rel}")
			except (OSError, ValueError):
				continue

	return buffer.getvalue()


def read_files(name: str, paths: list[str]) -> list[dict]:
	"""Read the named files as {"path", "content"}. Raises for a missing file."""
	out = []
	for rel in paths or []:
		absolute = safe_join(name, rel)
		if not os.path.isfile(absolute):
			frappe.throw(frappe._("No such file: {0}").format(rel), frappe.ValidationError)

		with open(absolute, encoding="utf-8") as handle:
			out.append({"path": rel, "content": handle.read()})

	return out


def preflight(name: str, incoming: list[dict]) -> None:
	"""Refuse a write that breaks a quota, before any file is opened.

	`incoming` is [{"path", "absolute", "bytes"}]: the whole batch, measured.
	Nothing is written until every entry passes, so a refused batch leaves the
	tree exactly as it was.

	The projected tree is the tree on disk, with each incoming entry put in
	place of the file it overwrites. Keying on the absolute path is what makes
	an overwrite count once, and a batch that names one path twice count once
	as well.

	Directories are projected the same way, because `write_files` calls
	`os.makedirs` for every parent the batch names. `safe_join` caps how deep
	one path goes, and `MAX_TREE_DIRS` caps how many the tree holds.

	An error names the relative path only. An absolute one leaks the bench
	root, the OS user and the private files layout.

	Known limit: this is check-then-act with no lock. Two write calls for one
	Prototype at the same time can both pass and together exceed a tree cap by
	up to one batch. A lock is not taken here, because a held lock that is
	never released is a worse failure than one oversized tree.
	"""
	if len(incoming) > MAX_BATCH_FILES:
		frappe.throw(
			frappe._("One write carries at most {0} files. This one carries {1}.").format(
				MAX_BATCH_FILES, len(incoming)
			),
			frappe.ValidationError,
		)

	for entry in incoming:
		if entry["bytes"] > MAX_FILE_BYTES:
			frappe.throw(
				frappe._("{0} is {1} bytes. One file holds at most {2}.").format(
					entry["path"], entry["bytes"], MAX_FILE_BYTES
				),
				frappe.ValidationError,
			)

		# open() on a directory raises an OSError that carries its absolute
		# path, so the guard sits here rather than in the writer.
		if os.path.isdir(entry["absolute"]):
			frappe.throw(frappe._("{0} is a directory").format(entry["path"]), frappe.ValidationError)

	projected = {}
	for _rel, absolute in _walk(name):
		try:
			projected[os.path.realpath(absolute)] = os.path.getsize(absolute)
		except OSError:
			continue

	for entry in incoming:
		projected[entry["absolute"]] = entry["bytes"]

	if len(projected) > MAX_TREE_FILES:
		frappe.throw(
			frappe._("This prototype holds at most {0} files. Delete one before you add another.").format(
				MAX_TREE_FILES
			),
			frappe.ValidationError,
		)

	total = sum(projected.values())
	if total > MAX_TREE_BYTES:
		frappe.throw(
			frappe._("This prototype holds at most {0} bytes. This write would make it {1}.").format(
				MAX_TREE_BYTES, total
			),
			frappe.ValidationError,
		)

	base = os.path.realpath(prototype_dir(name))
	directories = {os.path.realpath(absolute) for absolute in _walk_dirs(name)}
	for entry in incoming:
		# Every parent up to the root, because os.makedirs creates them all.
		parent = os.path.dirname(entry["absolute"])
		while parent != base and parent.startswith(base + os.sep):
			directories.add(parent)
			parent = os.path.dirname(parent)

	if len(directories) > MAX_TREE_DIRS:
		frappe.throw(
			frappe._("This prototype holds at most {0} folders. This write would make it {1}.").format(
				MAX_TREE_DIRS, len(directories)
			),
			frappe.ValidationError,
		)


def write_files(name: str, files: list[dict]) -> list[str]:
	"""Write each {"path", "content"}. Creates parent directories.

	Every path is joined and every size measured before the first open, so a
	batch that breaks a quota writes no file at all (`preflight`).

	Return the paths written, in the order given.
	"""
	planned = []
	for entry in files or []:
		rel = entry.get("path")
		content = entry.get("content")
		if content is None:
			frappe.throw(frappe._("File {0} has no content").format(rel), frappe.ValidationError)

		planned.append(
			{
				"path": rel,
				"absolute": safe_join(name, rel),
				"bytes": len(content.encode("utf-8")),
				"content": content,
			}
		)

	preflight(name, planned)

	written = []
	for entry in planned:
		os.makedirs(os.path.dirname(entry["absolute"]), exist_ok=True)
		with open(entry["absolute"], "w", encoding="utf-8") as handle:
			handle.write(entry["content"])

		written.append(entry["path"])

	return written


def edit_file(name: str, path: str, old_string: str, new_string: str) -> None:
	"""Replace one exact occurrence of `old_string`.

	Raises when `old_string` is absent, and when it occurs more than once.

	An edit grows a file, so it passes the same quotas as a write
	(`preflight`). The file on disk is left alone when it does not.
	"""
	absolute = safe_join(name, path)
	if not os.path.isfile(absolute):
		frappe.throw(frappe._("No such file: {0}").format(path), frappe.ValidationError)

	with open(absolute, encoding="utf-8") as handle:
		source = handle.read()

	count = source.count(old_string)
	if count == 0:
		frappe.throw(
			frappe._("old_string is not in {0}. Read the file again and retry.").format(path),
			frappe.ValidationError,
		)
	if count > 1:
		frappe.throw(
			frappe._("old_string occurs {0} times in {1}. Give more surrounding lines.").format(
				count, path
			),
			frappe.ValidationError,
		)

	updated = source.replace(old_string, new_string, 1)
	preflight(name, [{"path": path, "absolute": absolute, "bytes": len(updated.encode("utf-8"))}])

	with open(absolute, "w", encoding="utf-8") as handle:
		handle.write(updated)


def delete_file(name: str, path: str) -> None:
	"""Delete one file, and every folder it leaves empty.

	The prune goes up to the Prototype root and stops there
	(`_prune_empty_dirs`). Without it a delete returns the file quota but not
	the directory quota, so the same batch is written and deleted again and
	again until the disk has no inodes left.
	"""
	absolute = safe_join(name, path)
	if not os.path.isfile(absolute) and not os.path.islink(absolute):
		frappe.throw(frappe._("No such file: {0}").format(path), frappe.ValidationError)

	os.remove(absolute)
	_prune_empty_dirs(name, os.path.dirname(absolute))


def revision(name: str) -> str:
	"""A short string that changes whenever any file in the tree changes.

	The Viewer polls this to decide when to reload. It is a stat walk, not a
	content hash: the file count and the newest modification time in
	nanoseconds. A write that leaves the mtime where it was is missed. No
	writer in Sketch does that, and a stat walk stays cheap enough to answer
	every two seconds.

	Returns "" for a tree that does not exist.
	"""
	base = prototype_dir(name)
	if not os.path.isdir(base):
		return ""

	count = 0
	newest = 0
	for _rel, absolute in _walk(name):
		try:
			stamp = os.stat(absolute).st_mtime_ns
		except OSError:
			continue

		count += 1
		if stamp > newest:
			newest = stamp

	return f"{count}-{newest}"


def read_tree(name: str) -> dict[str, str]:
	"""The whole tree as {relative path: source}.

	Best effort: a file that vanishes between the walk and the read is skipped.
	Returns {} when the directory does not exist.
	"""
	tree = {}
	for rel, absolute in _walk(name):
		try:
			with open(absolute, encoding="utf-8") as handle:
				tree[rel] = handle.read()
		except (OSError, UnicodeDecodeError):
			continue

	return tree


def delete_tree(name: str) -> None:
	"""Delete the whole directory. Never raises for a missing directory."""
	base = prototype_dir(name)
	if os.path.isdir(base):
		shutil.rmtree(base, ignore_errors=True)
