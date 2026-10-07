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

`name` is always the Prototype's hash primary key, never its slug.
"""

import json
from datetime import UTC, datetime

import frappe

PROTOTYPE = "Sketch Prototype"

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


def read(name: str) -> dict:
	"""The saved annotations, or the empty shape when there are none.

	A stored value that no longer parses reads as empty rather than breaking the
	Viewer or the agent's tool.
	"""
	raw = frappe.db.get_value(PROTOTYPE, name, "annotations")
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


def save(name: str, raw: str, seen_epoch: int) -> dict:
	"""Replace the saved annotations with one validated save.

	set_value with update_modified off: the toolbar saves after every change, and
	a save is not an edit of the Prototype. It also leaves the live-reload
	revision alone, so saving never reloads the page that saved.

	`seen_epoch` is the epoch the page loaded with; a page older than the last
	clear is refused (AnnotationsStale) and reloads instead.
	"""
	doc = parse(raw)
	if seen_epoch != epoch(name):
		frappe.throw(frappe._("Annotations changed since this page loaded"), AnnotationsStale)

	doc["updated"] = _now()
	_write(name, doc)
	return doc


def clear(name: str, ids: list[str] | None = None) -> dict:
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
	doc = read(name)
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
	_write(name, doc)
	_bump_epoch(name)
	return removed


def epoch(name: str) -> int:
	"""How many times the agent has cleared annotations. Part of the revision."""
	return int(frappe.db.get_value(PROTOTYPE, name, "annotations_epoch") or 0)


# ------------------------------------------------------------------ internals


def _write(name: str, doc: dict) -> None:
	frappe.db.set_value(PROTOTYPE, name, "annotations", json.dumps(doc), update_modified=False)


def _bump_epoch(name: str) -> None:
	# One UPDATE, so two clears at once both count.
	table = frappe.qb.DocType(PROTOTYPE)
	(
		frappe.qb.update(table)
		.set(table.annotations_epoch, table.annotations_epoch + 1)
		.where(table.name == name)
		.run()
	)


def _now() -> str:
	return datetime.now(UTC).isoformat(timespec="seconds")
