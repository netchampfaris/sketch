# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The version log of one Prototype: what changed, and the prompt that asked.

`name` is always the Prototype's hash primary key (doc.name), never its slug.
A slug is unique per owner only, so two users can both hold `dashboard`.

A write tool notes its change and records nothing. The note lands in the
Prototype's `pending_changes` list, folded by path. The agent calls `commit`
once at the end of the user request. That writes one Sketch Prototype Version
row from the whole pending list and clears it, so one request makes one
version however many tool calls it took. A Version stores the prompt, the time
and the file names. It stores no file content, so there is no revert.
"""

import json

import frappe

ADDED = "added"
MODIFIED = "modified"
DELETED = "deleted"

PROTOTYPE = "Sketch Prototype"
VERSION = "Sketch Prototype Version"


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


def commit(doc, prompt: str, summary: str | None = None):
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

	# Hold the Prototype row until this transaction ends. Two commits on one
	# Prototype then queue here, so they cannot read the same pending list or
	# the same maximum sequence and write two rows for one request.
	frappe.db.get_value(PROTOTYPE, doc.name, "name", for_update=True)

	changes = pending(doc.name)
	if not changes:
		return None

	version = frappe.new_doc(VERSION)
	version.prototype = doc.name
	version.sequence = _next_sequence(doc.name)
	version.prompt = prompt
	version.summary = summary
	version.changes = json.dumps(changes)
	version.files_added = _count(changes, ADDED)
	version.files_modified = _count(changes, MODIFIED)
	version.files_deleted = _count(changes, DELETED)
	# The Version belongs to the person who owns the Prototype, so the
	# `if_owner` rules let that person read the history.
	version.owner = doc.owner
	version.insert(ignore_permissions=True)

	_set_pending(doc.name, [])
	return version


def history(name: str) -> list[dict]:
	"""Every version of this Prototype, newest first.

	Read with frappe.get_all, which applies no permission check. The caller
	resolves the Prototype through prototype.resolve_owned first, and that is
	the check that guards this list.
	"""
	rows = frappe.get_all(
		VERSION,
		filters={"prototype": name},
		fields=[
			"name",
			"sequence",
			"prompt",
			"summary",
			"changes",
			"files_added",
			"files_modified",
			"files_deleted",
			"creation",
		],
		order_by="sequence desc",
	)
	for row in rows:
		row["changes"] = _parse(row.get("changes"))

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
