# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The version log of one Prototype: what changed, and the prompt that asked.

`name` is always the Prototype's hash primary key (doc.name), never its slug.
A slug is unique per owner only, so two users can both hold `dashboard`.

Every write tool sends the user's prompt with the change, and `record` files
that change under the prompt at once. There is no pending state and no second
call. One user request writes one Sketch Prototype Version row, because the
second and third change of that request carry the same prompt and fold into
the row the first one made. A Version stores the prompt, the time and the file
names. It stores no file content, so there is no revert.
"""

import json
from datetime import timedelta

import frappe
from frappe.utils import get_datetime, now_datetime

ADDED = "added"
MODIFIED = "modified"
DELETED = "deleted"

PROTOTYPE = "Sketch Prototype"
VERSION = "Sketch Prototype Version"

# One user request can call write_files, then edit_file, then delete_file, and
# all of that is one version. A change joins the newest version when the prompt
# matches word for word and that version is younger than this window. The
# window stops the same message, sent again weeks later, from joining the old
# version instead of starting a new one.
MERGE_WINDOW = timedelta(minutes=30)


def record(doc, prompt: str, changes: list[dict], summary: str | None = None):
	"""Fold these changes into the version for this prompt. Returns the version doc.

	`changes` is a list of {"path", "action"}, with the action one of ADDED,
	MODIFIED or DELETED. Returns None when the list holds no usable change.
	Raises frappe.ValidationError when the prompt is blank. The prompt is
	stored verbatim: no trim of inner whitespace, no truncation, no HTML strip.

	The caller resolves the Prototype through prototype.resolve_owned first,
	which is permission-checked, so the row is written with ignore_permissions
	and the Prototype's owner.
	"""
	if not (prompt or "").strip():
		frappe.throw(frappe._("A version needs the user prompt"), frappe.ValidationError)

	changes = [row for row in (changes or []) if isinstance(row, dict) and row.get("path")]
	if not changes:
		return None

	# Hold the Prototype row until this transaction ends. Two tool calls on one
	# Prototype then queue here, so they cannot read the same newest version or
	# the same maximum sequence and write two rows for one request.
	frappe.db.get_value(PROTOTYPE, doc.name, "name", for_update=True)

	latest = _latest(doc.name)
	if latest and _joins(latest, prompt):
		return _append(latest, changes, summary)

	return _insert(doc, prompt, changes, summary)


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


def _latest(name: str) -> dict | None:
	"""The newest version of this Prototype, or None. Highest sequence wins."""
	rows = frappe.get_all(
		VERSION,
		filters={"prototype": name},
		fields=["name", "sequence", "prompt", "changes", "creation"],
		order_by="sequence desc",
		limit=1,
	)
	return rows[0] if rows else None


def _joins(latest: dict, prompt: str) -> bool:
	"""Whether a change under this prompt belongs in the newest version.

	The compare is character for character, so the stored prompt must be raw.
	`ignore_xss_filter` on the `prompt` field is what makes it raw: without it
	`_sanitize_content` runs `sanitize_html` on any prompt that holds `<` or
	`>`, the stored text stops matching the sent text, and one user request
	writes one version per tool call. `summary` carries the flag for the same
	reason. Neither field is ever rendered as HTML. The SPA history dialog
	prints both through Vue interpolation (`{{ version.prompt }}` in
	frontend/src/components/PrototypeHistoryDialog.vue), which escapes them.
	"""
	if latest.get("prompt") != prompt:
		return False

	return now_datetime() - get_datetime(latest.get("creation")) <= MERGE_WINDOW


def _append(latest: dict, changes: list[dict], summary: str | None):
	"""Fold the changes into the version that is already there."""
	folded = _parse(latest.get("changes"))
	for row in changes:
		_fold(folded, row.get("path"), row.get("action"))

	update = {
		"changes": json.dumps(folded),
		"files_added": _count(folded, ADDED),
		"files_modified": _count(folded, MODIFIED),
		"files_deleted": _count(folded, DELETED),
	}
	if summary:
		update["summary"] = summary

	# set_value, never doc.save(): this row is rewritten once per file the
	# agent touches, and a save would run the whole validate and hook stack
	# each time for four columns.
	frappe.db.set_value(VERSION, latest["name"], update)
	return frappe.get_doc(VERSION, latest["name"])


def _insert(doc, prompt: str, changes: list[dict], summary: str | None):
	"""Start a new version at the next sequence."""
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
	return version


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

	`record` holds the Prototype row `for update` before it reads anything, so
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
