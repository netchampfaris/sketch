# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""Move the notes signed-in readers left (PR #14's model) into comments.

A reader's note was a row in the owner's `notes` with the reader's `author`.
Comments are their own store now, so each such row becomes the first comment of
a thread, with its anchor and its time, and leaves the notes. The owner's own
notes stay. A rerun finds no row with an `author` and does nothing.
"""

import json
from datetime import UTC, datetime

import frappe
from frappe.utils import convert_utc_to_system_timezone

ANCHOR_KEYS = (
	"route",
	"viewport",
	"selector",
	"component",
	"componentChain",
	"file",
	"element",
	"text",
	"state",
	"extras",
	"box",
	"offset",
	"rect",
)


def execute():
	from sketch import comments

	for name, raw in frappe.db.sql(
		"select name, annotations from `tabSketch Prototype` where ifnull(annotations, '') like '%\"author\"%'"
	):
		try:
			doc = json.loads(raw)
		except ValueError:
			continue

		notes = [n for n in doc.get("notes") or [] if isinstance(n, dict)]
		readers = [n for n in notes if n.get("author")]
		if not readers:
			continue

		for note in readers:
			_move(name, note, comments)

		doc["notes"] = [n for n in notes if not n.get("author")]
		frappe.db.set_value("Sketch Prototype", name, "annotations", json.dumps(doc), update_modified=False)


def _move(name: str, note: dict, comments) -> None:
	text = note.get("note")
	if not isinstance(text, str) or not text.strip():
		return

	anchor = {k: note[k] for k in ANCHOR_KEYS if k in note}
	try:
		anchor = comments.clean_anchor(anchor)
		text = comments.clean_text(text.encode()[: comments.MAX_TEXT_BYTES].decode(errors="ignore"))
	except frappe.ValidationError:
		return

	row = comments._insert(name, str(note["author"])[:140], text, anchor=json.dumps(anchor))
	made = note.get("createdAt")
	if isinstance(made, int | float) and made > 0:
		when = convert_utc_to_system_timezone(datetime.fromtimestamp(made / 1000, UTC)).replace(tzinfo=None)
		frappe.db.set_value("Sketch Comment", row, "creation", when, update_modified=False)
