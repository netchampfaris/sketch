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

Signed-in readers of a public Prototype leave notes too (never tweaks). Their
rows sit in the same `notes` list, each stamped with the reader's `author`
username by the server. A reader writes only their own rows
(`save_comments`), and the owner's save can delete a reader's row but never
edit or forge one (`_merge_owner`).

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

#: How many notes one reader may keep on somebody else's Prototype.
MAX_COMMENTS = 50
#: The whole stored document, every reader's notes included.
MAX_STORED_BYTES = 2 * 1024 * 1024

#: Keys only the server writes on a reader's row.
AUTHOR = "author"

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


def read(name: str, for_update: bool = False) -> dict:
	"""The saved annotations, or the empty shape when there are none.

	A stored value that no longer parses reads as empty rather than breaking the
	Viewer or the agent's tool. `for_update` locks the row, so the owner and a
	reader saving at once never drop each other's rows.
	"""
	raw = frappe.db.get_value(PROTOTYPE, name, "annotations", for_update=for_update)
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
	Only `notes`, `tweaks`, `prompt`, `anchor` and `known` survive. `updated` is
	the server's to set. `known` is the reader note ids the owner's page loaded
	with (`_merge_owner`).
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

	known = data.get("known", [])
	if not isinstance(known, list) or not all(isinstance(i, str) for i in known):
		frappe.throw(frappe._("known must be a list of ids"), frappe.ValidationError)

	clean["known"] = known
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
	known = doc.pop("known")
	if seen_epoch != epoch(name):
		frappe.throw(frappe._("Annotations changed since this page loaded"), AnnotationsStale)

	stored = read(name, for_update=True)
	doc["notes"] = _merge_owner(_rows(stored.get("notes")), doc["notes"], set(known))
	doc["updated"] = _now()
	_write(name, doc)
	return doc


def comment_subject(name: str, username: str) -> str:
	"""What a COMMENT signature covers: this Prototype for this one reader."""
	return f"{name}|{username}"


def for_reader(name: str) -> dict:
	"""What a reader's page starts from: every note, and nothing else.

	The reader's toolbar shows only their own notes until they ask to see
	everyone's. Tweaks and the prompt are the owner's, so they stay out.
	"""
	return {"notes": _rows(read(name).get("notes"))}


def save_comments(name: str, author: str, raw: str, seen_epoch: int) -> dict:
	"""Replace one reader's own notes with one validated save.

	Every row is stamped with `author` here; whatever the page sent for it is
	dropped. A row reusing another author's id is dropped too, so a reader can
	never overwrite somebody else's note. Tweaks, the prompt and the anchor in
	the body are ignored: a reader only comments.

	The owner's `sent` mark survives on a row whose text has not changed.
	"""
	doc = parse(raw)
	mine = doc["notes"]
	if len(mine) > MAX_COMMENTS:
		message = frappe._("A reader may keep {0} notes at most").format(MAX_COMMENTS)
		frappe.throw(message, AnnotationsTooLarge)

	if seen_epoch != epoch(name):
		frappe.throw(frappe._("Annotations changed since this page loaded"), AnnotationsStale)

	stored = read(name, for_update=True)
	notes = _rows(stored.get("notes"))
	theirs = [n for n in notes if n.get(AUTHOR) != author]
	taken = {n.get("id") for n in theirs}
	before = {n.get("id"): n for n in notes if n.get(AUTHOR) == author}

	rows = []
	for row in mine:
		if not isinstance(row.get("id"), str) or row["id"] in taken:
			continue

		row = {k: v for k, v in row.items() if k not in (AUTHOR, "sent")}
		old = before.get(row["id"])
		if old and old.get("sent") and old.get("note") == row.get("note"):
			row["sent"] = True

		row[AUTHOR] = author
		rows.append(row)
		taken.add(row["id"])

	stored["notes"] = theirs + rows
	stored["updated"] = _now()
	if len(json.dumps(stored).encode()) > MAX_STORED_BYTES:
		frappe.throw(frappe._("Annotations are too large"), AnnotationsTooLarge)

	_write(name, stored)
	return {"notes": rows, "updated": stored["updated"]}


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


def _rows(notes) -> list[dict]:
	return [n for n in notes or [] if isinstance(n, dict)]


def _merge_owner(stored: list[dict], sent: list[dict], known: set[str]) -> list[dict]:
	"""The owner's save, with every reader's row kept as the reader wrote it.

	The owner's page holds the reader rows it loaded with (`known`) next to its
	own. A reader row it still sends is kept as stored, taking only the owner's
	`sent` mark. A known reader row it no longer sends was deleted by the owner.
	A reader row added after the page loaded is not known, so it is kept.

	A row the owner sends that is not a stored reader row is the owner's own,
	and any `author` on it is dropped: the owner cannot sign as a reader.
	"""
	readers = {n["id"]: n for n in stored if n.get(AUTHOR) and isinstance(n.get("id"), str)}
	out, seen = [], set()
	for row in sent:
		rid = row.get("id")
		if rid in readers:
			if rid in seen:
				continue

			kept = dict(readers[rid])
			kept.pop("sent", None)
			if row.get("sent"):
				kept["sent"] = True

			out.append(kept)
			seen.add(rid)
		else:
			out.append({k: v for k, v in row.items() if k != AUTHOR})

	out += [n for rid, n in readers.items() if rid not in seen and rid not in known]
	return out


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
