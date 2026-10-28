# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The notes and tweaks an owner leaves on a live Prototype.

The Viewer's toolbar (runtime/annotate) keeps them in memory and saves the whole
set here, so the owner's agent can read them over MCP and a reload loses nothing.
They live in one hidden Long Text field on the Prototype, the way
`pending_changes` does: `{notes, tweaks, prompt, anchor?, updated}`.

The writer is a page that runs the Prototype's own JavaScript, and a fork means
that code is a stranger's. So everything here treats the saved rows as data
written from an untrusted place: the size and the shape are checked, and unknown
keys are dropped. What the rows say is for the agent to weigh, never to obey
(sketch/mcp/tools.py `get_annotations`).

An invited editor has notes and tweaks too, for their own agent, which turns
them into variants under the editor's own folder. They are kept on the
editor's invitation row (`Sketch Prototype Editor.annotations`), so the owner
never reads an editor's and an editor never reads the owner's (decision 29,
both ways). Every function here takes `editor`, the invited user, and reads or
writes that person's alone; without it, the owner's.

Other people's comments live elsewhere (sketch/comments.py). Nothing here reads,
writes or clears them, so the agent never meets a comment unless the owner copies
one into their notes.

`name` is always the Prototype's hash primary key, never its slug.
"""

import json
from datetime import UTC, datetime

import frappe

PROTOTYPE = "Sketch Prototype"
EDITOR = "Sketch Prototype Editor"

#: A whole save, as sent. A note or tweak is small, so this is far above real use.
MAX_BYTES = 256 * 1024
#: The prompt is a convenience copy of the rows, so it is capped on its own.
MAX_PROMPT_BYTES = 64 * 1024

ANCHORS = ("top-left", "top-center", "top-right", "bottom-left", "bottom-center", "bottom-right")


class AnnotationsTooLarge(frappe.ValidationError):
	"""A save over MAX_BYTES. Served as 413, so the caller can tell it from a bad shape."""

	http_status_code = 413


class AnnotationsStale(frappe.ValidationError):
	"""A save from a page loaded before the agent last cleared. Served as 409.

	Without it a tab left open (or asleep) through a clear would write the cleared
	rows back with its next change, and the agent would apply them twice.
	"""

	http_status_code = 409


def empty() -> dict:
	return {"notes": [], "tweaks": [], "prompt": "", "updated": ""}


def subject(name: str, username: str) -> str:
	"""What an editor's notes signature covers: this Prototype, for this one person."""
	return f"{name}|{username}"


def read(name: str, for_update: bool = False, editor: str | None = None) -> dict:
	"""The saved annotations, or the empty shape when there are none.

	A stored value that no longer parses reads as empty rather than breaking the
	Viewer or the agent's tool. `for_update` locks the row, so the owner and a
	reader saving at once never drop each other's rows.
	"""
	raw = _get(name, "annotations", editor, for_update)
	if not raw:
		return empty()

	try:
		data = json.loads(raw)
	except ValueError:
		return empty()

	return data if isinstance(data, dict) else empty()


def parse(raw: str) -> dict:
	"""Check one save and return the clean document. Raises when it is not one.

	The size is checked before the parse, so an oversize body costs nothing.
	Only `notes`, `tweaks`, `prompt` and `anchor` survive. `updated` is the
	server's to set.
	"""
	raw = raw or ""
	if len(raw.encode()) > MAX_BYTES:
		frappe.throw(frappe._("Annotations are too large"), AnnotationsTooLarge)

	try:
		data = json.loads(raw)
	except ValueError:
		frappe.throw(frappe._("Annotations must be JSON"), frappe.ValidationError)

	if not isinstance(data, dict):
		frappe.throw(frappe._("Annotations must be an object"), frappe.ValidationError)

	clean = {}
	for key in ("notes", "tweaks"):
		rows = data.get(key, [])
		if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
			frappe.throw(frappe._("{0} must be a list of objects").format(key), frappe.ValidationError)

		clean[key] = rows

	prompt = data.get("prompt", "")
	if not isinstance(prompt, str) or len(prompt.encode()) > MAX_PROMPT_BYTES:
		frappe.throw(frappe._("prompt must be text of 64 KB or less"), frappe.ValidationError)

	clean["prompt"] = prompt

	anchor = data.get("anchor")
	if anchor is not None:
		if anchor not in ANCHORS:
			frappe.throw(frappe._("anchor is not a toolbar corner"), frappe.ValidationError)

		clean["anchor"] = anchor

	return clean


def save(name: str, raw: str, seen_epoch: int, editor: str | None = None) -> dict:
	"""Replace the saved annotations with one validated save.

	set_value with update_modified off: the toolbar saves after every change, and
	a save is not an edit of the Prototype. It also leaves the live-reload
	revision alone, so saving never reloads the page that saved.

	`seen_epoch` is the epoch the page loaded with; a page older than the last
	clear is refused (AnnotationsStale) and reloads instead.
	"""
	doc = parse(raw)
	# The lock first, then the epoch: a clear that commits while this waits for
	# the lock is seen, so a stale page can never write cleared rows back.
	read(name, for_update=True, editor=editor)
	if seen_epoch != epoch(name, editor):
		frappe.throw(frappe._("Annotations changed since this page loaded"), AnnotationsStale)

	doc["notes"] = [{k: v for k, v in n.items() if k != "author"} for n in doc["notes"]]
	doc["updated"] = _now()
	_write(name, doc, editor)
	return doc


def clear(name: str, ids: list[str] | None = None, editor: str | None = None) -> dict:
	"""Remove the listed note and tweak ids, or every one when `ids` is None.

	An empty list removes nothing: "clear these" with none listed must never
	mean "clear all".

	A tweak is named by its own id or by the `group` its multi-select edit shares.
	Returns {"notes": removed, "tweaks": removed}.

	The saved prompt is written from the rows by the page, and the server cannot
	rebuild it, so a partial clear drops it and the page writes a new one when it
	reloads. The reload is asked for through the epoch: this is the one write that
	moves the revision, because it is the one the open Viewer has to see.
	"""
	doc = read(name, for_update=True, editor=editor)
	notes = [n for n in doc.get("notes") or [] if isinstance(n, dict)]
	tweaks = [t for t in doc.get("tweaks") or [] if isinstance(t, dict)]

	if ids is None:
		keep_notes, keep_tweaks = [], []
	else:
		wanted = {i for i in ids if isinstance(i, str)}
		keep_notes = [n for n in notes if n.get("id") not in wanted]
		keep_tweaks = [t for t in tweaks if t.get("id") not in wanted and t.get("group") not in wanted]

	removed = {"notes": len(notes) - len(keep_notes), "tweaks": len(tweaks) - len(keep_tweaks)}
	if not (removed["notes"] or removed["tweaks"]):
		return removed

	doc["notes"], doc["tweaks"] = keep_notes, keep_tweaks
	doc["prompt"] = ""
	doc["updated"] = _now()
	_write(name, doc, editor)
	_bump_epoch(name, editor)
	return removed


def epoch(name: str, editor: str | None = None) -> int:
	"""How many times the agent has cleared annotations. The owner's is part of the revision."""
	return int(_get(name, "annotations_epoch", editor) or 0)


# ------------------------------------------------------------------ internals


def _rows(notes) -> list[dict]:
	return [n for n in notes or [] if isinstance(n, dict)]


def _invite(name: str, editor: str) -> str:
	"""The editor's invitation row. One that is not invited has none, and nothing of theirs is read or written."""
	row = frappe.db.get_value(EDITOR, {"prototype": name, "user": editor}, "name")
	if not row:
		raise frappe.DoesNotExistError

	return row


def _get(name: str, field: str, editor: str | None, for_update: bool = False):
	if editor:
		return frappe.db.get_value(EDITOR, _invite(name, editor), field, for_update=for_update)

	return frappe.db.get_value(PROTOTYPE, name, field, for_update=for_update)


def _write(name: str, doc: dict, editor: str | None = None) -> None:
	if editor:
		frappe.db.set_value(EDITOR, _invite(name, editor), "annotations", json.dumps(doc), update_modified=False)
		return

	frappe.db.set_value(PROTOTYPE, name, "annotations", json.dumps(doc), update_modified=False)


def _bump_epoch(name: str, editor: str | None = None) -> None:
	# One UPDATE, so two clears at once both count.
	table = frappe.qb.DocType(EDITOR if editor else PROTOTYPE)
	key = _invite(name, editor) if editor else name
	(
		frappe.qb.update(table)
		.set(table.annotations_epoch, table.annotations_epoch + 1)
		.where(table.name == key)
		.run()
	)


def _now() -> str:
	return datetime.now(UTC).isoformat(timespec="seconds")
