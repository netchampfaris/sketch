# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The on-disk tree of one Prototype, and the path guard.

`name` is always the Prototype's hash primary key, never its slug. A slug is
unique per owner only, so two users with `dashboard` would share a directory.

Every agent-supplied path goes through `safe_join` and nothing else.
"""

import os
import posixpath
import shutil

import frappe

ROOT = ("private", "files", "sketch")

#: The most bytes `read_text` returns for one file. A Prototype file is a Vue
#: single-file component or a small module, so this is far above any real one.
#: It caps the reply for a file that is not.
MAX_TEXT_BYTES = 512 * 1024


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


def write_files(name: str, files: list[dict]) -> list[str]:
	"""Write each {"path", "content"}. Creates parent directories.

	Return the paths written, in the order given.
	"""
	written = []
	for entry in files or []:
		rel = entry.get("path")
		content = entry.get("content")
		if content is None:
			frappe.throw(frappe._("File {0} has no content").format(rel), frappe.ValidationError)

		absolute = safe_join(name, rel)
		os.makedirs(os.path.dirname(absolute), exist_ok=True)
		with open(absolute, "w", encoding="utf-8") as handle:
			handle.write(content)

		written.append(rel)

	return written


def edit_file(name: str, path: str, old_string: str, new_string: str) -> None:
	"""Replace one exact occurrence of `old_string`.

	Raises when `old_string` is absent, and when it occurs more than once.
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

	with open(absolute, "w", encoding="utf-8") as handle:
		handle.write(source.replace(old_string, new_string, 1))


def delete_file(name: str, path: str) -> None:
	"""Delete one file."""
	absolute = safe_join(name, path)
	if not os.path.isfile(absolute) and not os.path.islink(absolute):
		frappe.throw(frappe._("No such file: {0}").format(path), frappe.ValidationError)

	os.remove(absolute)


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
