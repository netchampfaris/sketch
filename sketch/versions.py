# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The version log of one Prototype: what changed, and the prompt that asked.

`name` is always the Prototype's hash primary key (doc.name), never its slug.
A slug is unique per owner only, so two users can both hold `dashboard`.

A write tool notes its change and records nothing. The note lands in the
Prototype's `pending_changes` list, folded by path. The agent calls `commit`
once at the end of the user request. That writes one Sketch Prototype Version
row from the whole pending list and clears it, so one request makes one
version however many tool calls it took.

A Version stores the prompt, the time, the file names, and a manifest: the hash
of every file in the tree after it (`sketch/snapshots.py` holds the bytes). So
any version can be restored. A restore is itself recorded as a new version, of
kind Restore, which means it can be undone the same way. History is never
rewritten. The kinds are Request (a `commit`), Restore, and Created (the
first version of a new or forked Prototype).

A row recorded before manifests existed has an empty one, and cannot be
restored.
"""

import json

import frappe
from frappe.query_builder import Order

from sketch import snapshots, thumbnails

ADDED = "added"
MODIFIED = "modified"
DELETED = "deleted"

PROTOTYPE = "Sketch Prototype"
VERSION = "Sketch Prototype Version"

REQUEST = "Request"
RESTORE = "Restore"
CREATED = "Created"


def lock(name: str) -> None:
	"""Hold the Prototype row until this transaction ends.

	Every writer of the tree takes it first, so a write waits for a restore
	(or a commit) in flight and never lands in the middle of one.
	"""
	frappe.db.get_value(PROTOTYPE, name, "name", for_update=True)


def note(name: str, path: str, action: str) -> None:
	"""Fold one change into the pending list of this Prototype.

	`action` is one of ADDED, MODIFIED or DELETED. Nothing is recorded until
	`commit` runs.
	"""
	if not path:
		return

	changes = pending(name)
	_fold(changes, path, action)
	_set_pending(name, changes)


def note_write(name: str, paths: list[str], existed: set[str]) -> None:
	"""Fold a batch of written paths into the pending list.

	A path in `existed` was already on disk before the write, so it is a
	modification. Every other path is an addition.
	"""
	existed = existed or set()
	changes = pending(name)
	for path in paths or []:
		if path:
			_fold(changes, path, MODIFIED if path in existed else ADDED)

	_set_pending(name, changes)


def pending(name: str) -> list[dict]:
	"""The changes noted since the last version, oldest first.

	Each row is {"path", "action"}. One path holds one row.
	"""
	return _parse(frappe.db.get_value(PROTOTYPE, name, "pending_changes"))


def pending_count(name: str) -> int:
	"""How many files changed since the last version."""
	return len(pending(name))


def commit(doc, prompt: str, summary: str | None = None, source: str | None = None):
	"""Record the pending changes as one version. Returns the version doc.

	Returns None and changes nothing when nothing is pending, so a second
	`commit` in one request is a no-op and never a duplicate row. Raises
	frappe.ValidationError when the prompt is blank. The prompt is stored
	verbatim: no trim of inner whitespace, no truncation, no HTML strip.

	`prompt` and `summary` set `ignore_xss_filter` on the doctype, so Frappe
	stores them raw. Without it `_sanitize_content` runs `sanitize_html` on any
	prompt that holds `<` or `>`, and the person reads back text they never
	typed. Neither field is ever rendered as HTML: the SPA history dialog
	prints both through Vue interpolation (`{{ version.prompt }}` in
	frontend/src/components/PrototypeHistoryDialog.vue), which escapes them.

	The caller resolves the Prototype through prototype.resolve_owned first,
	which is permission-checked, so the row is written with ignore_permissions
	and the Prototype's owner.
	"""
	if not (prompt or "").strip():
		frappe.throw(frappe._("A version needs the user prompt"), frappe.ValidationError)

	# Two commits on one Prototype queue here, so they cannot read the same
	# pending list or the same maximum sequence and write two rows for one request.
	lock(doc.name)

	changes = pending(doc.name)
	if not changes:
		return None

	version = record(
		doc, REQUEST, prompt, changes, snapshots.capture(doc.name), summary=summary, source=source
	)
	_set_pending(doc.name, [])
	return version


def record(
	doc,
	kind: str,
	prompt: str,
	changes: list[dict],
	manifest: dict,
	restored_from: int | None = None,
	summary: str | None = None,
	source: str | None = None,
):
	"""Insert one version row. Returns the version doc.

	The one insert behind `commit`, `restore` and `record_created`. The caller
	holds the Prototype row `for update` already, so the sequence it reads
	here is its own.
	"""
	version = frappe.new_doc(VERSION)
	version.prototype = doc.name
	version.sequence = _next_sequence(doc.name)
	version.kind = kind
	version.restored_from = restored_from
	version.source = source
	version.prompt = prompt
	version.summary = summary
	version.changes = json.dumps(changes)
	version.manifest = json.dumps(manifest)
	version.restorable = 1 if manifest else 0
	version.files_added = _count(changes, ADDED)
	version.files_modified = _count(changes, MODIFIED)
	version.files_deleted = _count(changes, DELETED)
	# The Version belongs to the person who owns the Prototype, so the
	# `if_owner` rules let that person read the history.
	version.owner = doc.owner
	version.insert(ignore_permissions=True)
	return version


def record_created(doc, prompt: str):
	"""Record version 1 of a Prototype that starts with files: every file added.

	Called by create and fork once the tree is written, so a restore can always
	go back to how the Prototype began.
	"""
	lock(doc.name)
	manifest = snapshots.capture(doc.name)
	return record(doc, CREATED, prompt, diff({}, manifest), manifest)


def restore(doc, sequence: int, dry_run: bool = False, source: str = "App") -> dict:
	"""Put the tree back as it was after version `sequence`.

	The restore is recorded as a new version, so history only grows and a
	restore can be undone by restoring the version before it. Changes still
	pending are committed first, so work the agent had not filed is not lost.

	Raises frappe.ValidationError for a version that does not exist or that was
	recorded before manifests did. With `dry_run` it only reports the files
	that would change. A restore that would change nothing records nothing.
	`source` says who asked: "App" for the Sketch UI, "Agent" for the MCP tool.
	"""
	target = _manifest_of(doc.name, sequence)
	if dry_run:
		changes = diff(snapshots.manifest(doc.name), target)
		return {"sequence": sequence, "changes": changes, **_counts(changes)}

	lock(doc.name)
	if pending(doc.name):
		commit(doc, f"Unsaved changes, kept before restoring version {sequence}")

	# Stored now, so the tree being replaced can always be put back.
	current = snapshots.capture(doc.name)
	changes = diff(current, target)
	result = {"sequence": sequence, "changes": changes, **_counts(changes)}
	if not changes:
		return {**result, "recorded": False}

	# The row goes in before the disk changes. If `apply` fails it puts the old
	# tree back and raises, and the rollback takes the row with it.
	version = record(
		doc,
		RESTORE,
		f"Restored version {sequence}",
		changes,
		target,
		restored_from=sequence,
		source=source,
	)
	snapshots.apply(doc.name, target, current)
	thumbnails.request_refresh(doc.name)
	return {
		**result,
		"recorded": True,
		"sequence": version.sequence,
		"restored_from": sequence,
	}


def prune(doc, sequence: int, dry_run: bool = False) -> dict:
	"""Delete version `sequence` and every older one, then the blobs nobody needs.

	The current (newest) version is never deletable. A blob stays when a kept
	version's manifest names it or the tree on disk holds it. Returns
	{"deleted": rows, "freed_bytes": bytes}. With `dry_run` nothing is removed.
	"""
	if not dry_run:
		_lock_fresh(doc.name)

	latest = frappe.db.sql(
		"select max(sequence) from `tabSketch Prototype Version` where prototype = %s", doc.name
	)[0][0]
	if sequence < 1 or sequence >= (latest or 0):
		frappe.throw(
			frappe._("Only versions older than the current one can be deleted"), frappe.ValidationError
		)

	deleted = frappe.db.count(VERSION, {"prototype": doc.name, "sequence": ["<=", sequence]})
	if dry_run:
		freed = snapshots.collect(doc.name, _kept_blobs(doc.name, sequence), dry_run=True)
		return {"deleted": deleted, "freed_bytes": freed}

	# Rows go first and are committed, so a failure from here on leaves only
	# orphan blobs, which the next prune clears. Never a row without its blobs.
	frappe.db.delete(VERSION, {"prototype": doc.name, "sequence": ["<=", sequence]})
	_lock_fresh(doc.name)
	freed = snapshots.collect(doc.name, _kept_blobs(doc.name, sequence))
	return {"deleted": deleted, "freed_bytes": freed}


def _kept_blobs(name: str, sequence: int) -> set[str]:
	"""Blobs a prune must keep: the tree on disk and every version after `sequence`."""
	keep = set(snapshots.manifest(name).values())
	for raw in frappe.get_all(
		VERSION, filters={"prototype": name, "sequence": [">", sequence]}, pluck="manifest"
	):
		keep.update(_parse_manifest(raw).values())
	return keep


def _lock_fresh(name: str) -> None:
	"""Commit, then lock, so the reads that follow see every commit before the lock.

	MariaDB's repeatable read keeps a request's first snapshot even after a
	`for update`. A prune reading through that stale snapshot could miss a
	version committed while it waited, and collect that version's blobs.
	"""
	frappe.db.commit()
	lock(name)


def history(name: str) -> list[dict]:
	"""Every version of this Prototype, newest first.

	Read with frappe.qb, which applies no permission check. The caller
	resolves the Prototype through prototype.resolve_owned first, and that is
	the check that guards this list.

	The manifest is never returned: it is the size of the tree, and the list
	only needs to know whether one exists (`restorable`).
	"""
	table = frappe.qb.DocType(VERSION)
	rows = (
		frappe.qb.from_(table)
		.select(
			table.name,
			table.sequence,
			table.kind,
			table.restored_from,
			table.source,
			table.prompt,
			table.summary,
			table.changes,
			table.files_added,
			table.files_modified,
			table.files_deleted,
			table.creation,
			table.restorable,
		)
		.where(table.prototype == name)
		.orderby(table.sequence, order=Order.desc)
		.run(as_dict=True)
	)
	for row in rows:
		row["changes"] = _parse(row.get("changes"))
		row["restorable"] = bool(row.get("restorable"))

	return rows


# ------------------------------------------------------------------ internals


def _set_pending(name: str, changes: list[dict]) -> None:
	"""Write the pending list back to the Prototype.

	set_value, never doc.save(): the Prototype has track_changes on, and a save
	would write a core Version row for every file the agent touches.
	"""
	frappe.db.set_value(
		PROTOTYPE, name, "pending_changes", json.dumps(changes), update_modified=True
	)


def _fold(changes: list[dict], path: str, action: str) -> None:
	"""Merge one change into the list in place. One path, one entry.

	The collapse rules:
	- added then modified stays `added`
	- added then deleted removes the path (it never existed before this version)
	- modified then deleted becomes `deleted`
	- deleted then added becomes `modified`
	- otherwise the later action wins

	A path keeps the position of the first time it appears.
	"""
	for index, row in enumerate(changes):
		if row.get("path") != path:
			continue

		first = row.get("action")
		if first == ADDED and action == MODIFIED:
			return
		if first == ADDED and action == DELETED:
			changes.pop(index)
			return
		if first == MODIFIED and action == DELETED:
			row["action"] = DELETED
			return
		if first == DELETED and action == ADDED:
			row["action"] = MODIFIED
			return

		row["action"] = action
		return

	changes.append({"path": path, "action": action})


def _next_sequence(name: str) -> int:
	"""The next 1-based sequence for this Prototype.

	`commit` holds the Prototype row `for update` before it reads anything, so
	no second commit can read this same maximum.
	"""
	last = frappe.db.sql(
		"""select max(sequence) from `tabSketch Prototype Version` where prototype = %s""",
		name,
	)
	return (last[0][0] or 0) + 1


def _manifest_of(name: str, sequence: int) -> dict:
	"""The stored manifest of one version. Raises when it cannot be restored."""
	row = frappe.db.get_value(VERSION, {"prototype": name, "sequence": sequence}, "manifest")
	if row is None:
		frappe.throw(frappe._("No version {0}").format(sequence), frappe.ValidationError)

	manifest = _parse_manifest(row)
	if not manifest:
		frappe.throw(
			frappe._("Version {0} can't be restored. It was recorded before restore existed.").format(
				sequence
			),
			frappe.ValidationError,
		)

	return manifest


def diff(old: dict, new: dict) -> list[dict]:
	"""The rows that take the tree `old` to the tree `new`, sorted by path.

	Each row is {"path", "action"}, in the shape this module already stores.
	"""
	rows = []
	for path in sorted(set(old) | set(new)):
		if path not in old:
			rows.append({"path": path, "action": ADDED})
		elif path not in new:
			rows.append({"path": path, "action": DELETED})
		elif old[path] != new[path]:
			rows.append({"path": path, "action": MODIFIED})

	return rows


def _counts(changes: list[dict]) -> dict:
	return {
		"files_added": _count(changes, ADDED),
		"files_modified": _count(changes, MODIFIED),
		"files_deleted": _count(changes, DELETED),
	}


def _count(changes: list[dict], action: str) -> int:
	return sum(1 for row in changes if row.get("action") == action)


def _parse(raw) -> list:
	"""A stored changes string back as a list. Never raises."""
	if not raw:
		return []

	try:
		changes = json.loads(raw)
	except ValueError:
		return []

	return changes if isinstance(changes, list) else []


def _parse_manifest(raw) -> dict:
	"""A stored manifest string back as a dict. Never raises."""
	try:
		manifest = json.loads(raw or "")
	except ValueError:
		return {}

	return manifest if isinstance(manifest, dict) else {}
