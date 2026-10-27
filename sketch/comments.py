# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""Comments: conversations between people, pinned to an element of a live Prototype.

They are not notes. Notes and tweaks are the owner's instructions to their own
agent (sketch/annotations.py); a comment is somebody's words to somebody else,
and nothing here is ever handed to an agent unless the owner copies one into
their notes (`add_to_notes`).

Each comment is one `Sketch Comment` row: the first comment of a thread carries
the anchor and the resolved mark, a reply points at it through `thread`. Every
write names one row (create, reply, edit, delete, resolve), so a page that has
been open for a day can only ever do what its person could do now. It cannot
bring a deleted comment back, because there is no whole-set save to bring it
back with.

The writer is the Viewer page, which runs the Prototype's own JavaScript, and
a fork means that code is a stranger's. So who is speaking is never taken from
the page: the page holds a short-lived pass (`mint_pass`) signed over this
Prototype and this one username, and the server checks it, the user it names,
and the Prototype's visibility again on every call. The text is stored as sent
and shown only as escaped text.

`name` is always the Prototype's hash primary key, never its slug.
"""

import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import frappe

from sketch import annotations, signature

PROTOTYPE = "Sketch Prototype"
COMMENT = "Sketch Comment"

#: One comment or reply.
MAX_TEXT_BYTES = 4 * 1024
#: How many threads one person may start on one Prototype.
MAX_THREADS = 200
#: How many replies one thread keeps, all authors together.
MAX_REPLIES = 500
#: The anchor describes one spot on the page; it is small.
MAX_ANCHOR_BYTES = 8 * 1024
#: How long a pass lasts. The toolbar renews it while the person is active.
PASS_TTL_SECONDS = 15 * 60
#: How long a page's right to ask for a pass lasts: as long as the owner's live tab.
TICKET_TTL_SECONDS = 12 * 60 * 60

#: Strings in an anchor, and how long each may be.
ANCHOR_TEXT = {
	"route": 512,
	"viewport": 32,
	"selector": 1024,
	"component": 200,
	"file": 300,
	"element": 300,
	"text": 300,
	"state": 200,
}


#: What a canvas tile is: a variant option, a page state, or a page's default.
TILE_KINDS = ("set", "state", "default")
#: Strings that name a tile in plain words, and how long each may be.
TILE_TEXT = {
	"view": 200,
	"page": 200,
	"group": 200,
	"groupKey": 200,
	"option": 200,
	"optionLabel": 200,
}


class CommentTooLarge(frappe.ValidationError):
	"""A comment over 4 KB. Served as 413."""

	http_status_code = 413


class TooManyThreads(frappe.ValidationError):
	"""A person at their thread limit on this Prototype. Served as 429."""

	http_status_code = 429


@dataclass(frozen=True)
class Actor:
	"""Who a pass speaks for, and whether they own the Prototype it is on."""

	username: str
	user: str
	is_owner: bool


# --------------------------------------------------------------------- access


def subject(name: str, username: str) -> str:
	"""What a pass covers: this Prototype, for this one person."""
	return f"{name}|{username}"


def mint_ticket(name: str, username: str) -> dict:
	"""What the page payload carries for a commenter: the right to ask for a pass.

	It opens `mint_pass` and nothing else, so it cannot read or write a comment.
	"""
	return signature.mint(subject(name, username), TICKET_TTL_SECONDS, signature.COMMENT_MINT)


def mint_pass(name: str, username: str, exp, sig) -> dict:
	"""A short-lived pass for a person with a valid ticket, if they may still comment.

	Called by the toolbar when the person enters Comment mode and again before
	the pass runs out. The Prototype's visibility is read now, so a Prototype
	made private stops handing out passes at once. Any refusal is a 404.
	"""
	if not username or not signature.verify(subject(name, username), exp, sig, signature.COMMENT_MINT):
		raise frappe.DoesNotExistError

	actor = _actor(name, username)
	stamp = signature.mint(subject(name, actor.username), PASS_TTL_SECONDS, signature.COMMENT)
	return {"exp": stamp["exp"], "sig": stamp["sig"], "ttl": PASS_TTL_SECONDS}


def actor_for(name: str, username: str, exp, sig) -> Actor:
	"""Check a pass and who it names. Every refusal is the same 404.

	The Prototype is read again each time: an owner who makes it private closes
	the door at once, not when the pass runs out.
	"""
	if not username or not signature.verify(subject(name, username), exp, sig, signature.COMMENT):
		raise frappe.DoesNotExistError

	return _actor(name, username)


def _actor(name: str, username: str) -> Actor:
	user = frappe.db.get_value("User", {"username": username, "enabled": 1}, "name")
	row = frappe.db.get_value(PROTOTYPE, name, ["owner", "is_public"], as_dict=True)
	if not user or not row or not (row.is_public or row.owner == user):
		raise frappe.DoesNotExistError

	return Actor(username, user, row.owner == user)


def can_see(name: str, user: str) -> bool:
	"""Whether this user may read and write comments on the Prototype."""
	row = frappe.db.get_value(PROTOTYPE, name, ["owner", "is_public"], as_dict=True)
	return bool(row and user != "Guest" and (row.is_public or row.owner == user))


# ---------------------------------------------------------------------- reads


def open_count(name: str) -> int:
	"""How many threads are still unresolved."""
	return frappe.db.count(COMMENT, {"prototype": name, "thread": ["is", "not set"], "resolved": 0})


def full_names(usernames) -> dict:
	"""Each person's full name by username, the username itself when they have none.

	It is sent as plain text and shown as escaped text, like the words of a comment.
	"""
	names = {u for u in usernames if u}
	if not names:
		return {}

	users = frappe.get_all("User", filters={"username": ["in", list(names)]}, fields=["username", "full_name"])
	found = {u.username: (u.full_name or "").strip() for u in users}
	return {u: found.get(u) or u for u in names}


def list_threads(name: str) -> list[dict]:
	"""Every thread with its replies, oldest reply first. The page sorts threads.

	Each comment carries `name`, its author's full name, so a page never has to guess it.
	"""
	rows = frappe.get_all(
		COMMENT,
		filters={"prototype": name},
		fields=["name", "thread", "author", "text", "anchor", "resolved", "edited", "creation"],
		order_by="creation asc, name asc",
		limit_page_length=0,
	)
	names = full_names(row.author for row in rows)
	threads, by_id = [], {}
	for row in rows:
		if not row.thread:
			thread = {
				"id": row.name,
				"author": row.author,
				"name": names[row.author],
				"text": row.text or "",
				"ts": _ts(row.creation),
				"edited": bool(row.edited),
				"resolved": bool(row.resolved),
				"anchor": _load(row.anchor),
				"replies": [],
			}
			threads.append(thread)
			by_id[row.name] = thread

	for row in rows:
		parent = by_id.get(row.thread) if row.thread else None
		if parent:
			parent["replies"].append(
				{
					"id": row.name,
					"author": row.author,
					"name": names[row.author],
					"text": row.text or "",
					"ts": _ts(row.creation),
					"edited": bool(row.edited),
				}
			)

	return threads


def people_in(threads: list[dict]) -> dict:
	"""Name and picture of everyone who spoke in these threads, by username."""
	names = {c["author"] for t in threads for c in (t, *t["replies"])}
	if not names:
		return {}

	users = frappe.get_all(
		"User", filters={"username": ["in", list(names)]}, fields=["username", "full_name", "user_image"]
	)
	return {u.username: {"name": u.full_name or "", "image": u.user_image or ""} for u in users}


def one_thread(name: str, thread: str) -> dict | None:
	return next((t for t in list_threads(name) if t["id"] == thread), None)


# --------------------------------------------------------------------- writes


def add_thread(name: str, actor: Actor, anchor, text: str) -> str:
	"""Start a thread on an element. Returns its id."""
	text = clean_text(text)
	anchor = clean_anchor(anchor)
	_lock(name)
	started = frappe.db.count(COMMENT, {"prototype": name, "author": actor.username, "thread": ["is", "not set"]})
	if started >= MAX_THREADS:
		frappe.throw(
			frappe._("You have {0} threads on this prototype, the most there can be").format(MAX_THREADS),
			TooManyThreads,
		)

	return _insert(name, actor.username, text, anchor=json.dumps(anchor))


def add_reply(name: str, actor: Actor, thread: str, text: str) -> str:
	"""Reply in a thread. A thread that has gone is a 404."""
	text = clean_text(text)
	_lock(name)
	_root(name, thread)
	if frappe.db.count(COMMENT, {"prototype": name, "thread": thread}) >= MAX_REPLIES:
		frappe.throw(frappe._("This thread has too many replies"), TooManyThreads)

	return _insert(name, actor.username, text, thread=thread)


def edit(name: str, actor: Actor, comment: str, text: str) -> str:
	"""Change the words of your own comment. Nobody edits anybody else's, the owner included."""
	text = clean_text(text)
	_lock(name)
	row = _row(name, comment)
	if row.author != actor.username:
		raise frappe.PermissionError

	frappe.db.set_value(COMMENT, comment, {"text": text, "edited": 1})
	return row.thread or row.name


def delete(name: str, actor: Actor, comment: str) -> str:
	"""Delete a comment for good. Your own, or any if you own the Prototype.

	A thread's first comment takes its replies with it. Returns the thread id.
	"""
	_lock(name)
	row = _row(name, comment)
	if row.author != actor.username and not actor.is_owner:
		raise frappe.PermissionError

	if not row.thread:
		frappe.db.delete(COMMENT, {"prototype": name, "thread": comment})

	frappe.db.delete(COMMENT, {"name": comment})
	return row.thread or row.name


def set_resolved(name: str, actor: Actor, thread: str, resolved: bool) -> str:
	"""Resolve or reopen a thread: its starter or the owner."""
	_lock(name)
	row = _root(name, thread)
	if row.author != actor.username and not actor.is_owner:
		raise frappe.PermissionError

	frappe.db.set_value(COMMENT, thread, "resolved", 1 if resolved else 0)
	return thread


def add_to_notes(name: str, actor: Actor, comment: str) -> dict:
	"""Copy a comment into a new owner note on the same element. Owner only.

	The text is quoted and credited, so the agent can tell whose words they are.
	The comment stays where it is.
	"""
	if not actor.is_owner:
		raise frappe.PermissionError

	_lock(name)
	row = _row(name, comment)
	root = _root(name, row.thread or row.name)
	anchor = _load(root.anchor)
	note = {
		**anchor,
		"id": _note_id(),
		"note": f"{full_names([row.author])[row.author]}: “{(row.text or '').strip()}”",
		"createdAt": int(datetime.now(UTC).timestamp() * 1000),
	}
	return annotations.add_note(name, note)


# ------------------------------------------------------------------ validation


def clean_text(text) -> str:
	"""The words of one comment: text, not empty, 4 KB or less."""
	if not isinstance(text, str):
		frappe.throw(frappe._("A comment must be text"), frappe.ValidationError)

	text = text.replace("\x00", "").strip()
	if not text:
		frappe.throw(frappe._("A comment cannot be empty"), frappe.ValidationError)

	if len(text.encode()) > MAX_TEXT_BYTES:
		frappe.throw(frappe._("A comment can be 4 KB at most"), CommentTooLarge)

	return text


def clean_anchor(anchor) -> dict:
	"""The spot on the page, or on a canvas tile, reduced to the keys the toolbar writes and bounded.

	Anything else the page sent is dropped. `offset` and `rect` are numbers.
	"""
	if isinstance(anchor, str):
		try:
			anchor = json.loads(anchor)
		except ValueError:
			anchor = None

	if not isinstance(anchor, dict):
		frappe.throw(frappe._("A comment needs an element to sit on"), frappe.ValidationError)

	if "tile" in anchor:
		return clean_tile_anchor(anchor)

	out = {}
	for key, limit in ANCHOR_TEXT.items():
		value = anchor.get(key, "")
		out[key] = value[:limit] if isinstance(value, str) else ""

	if not out["route"] or not out["selector"]:
		frappe.throw(frappe._("A comment needs an element to sit on"), frappe.ValidationError)

	chain = anchor.get("componentChain")
	out["componentChain"] = [c[:200] for c in chain[:12] if isinstance(c, str)] if isinstance(chain, list) else []
	out["offset"] = _numbers(anchor.get("offset"), ("x", "y"))
	out["rect"] = _numbers(anchor.get("rect"), ("x", "y", "w", "h"))
	for key in ("box", "extras"):
		if key in anchor and _plain(anchor[key]):
			out[key] = anchor[key]

	if len(json.dumps(out).encode()) > MAX_ANCHOR_BYTES:
		frappe.throw(frappe._("That element description is too large"), CommentTooLarge)

	return out


def clean_tile_anchor(anchor: dict) -> dict:
	"""A spot on a canvas tile: which tile, and where on it as a fraction of its width and height.

	The tile is named by its page (`route`), and by the variant set and option, or the page state,
	it shows. It has the same keys as an element anchor, empty where they mean nothing for a tile,
	so everything that reads an anchor reads this one.
	"""
	tile = anchor.get("tile")
	if not isinstance(tile, dict) or tile.get("kind") not in TILE_KINDS:
		frappe.throw(frappe._("A comment needs a tile to sit on"), frappe.ValidationError)

	named = {"kind": tile["kind"]}
	for key, limit in TILE_TEXT.items():
		value = tile.get(key, "")
		named[key] = value[:limit] if isinstance(value, str) else ""

	route = anchor.get("route", "")
	route = route[: ANCHOR_TEXT["route"]] if isinstance(route, str) else ""
	if not route or (named["kind"] != "default" and not (named["groupKey"] and named["option"])):
		frappe.throw(frappe._("A comment needs a tile to sit on"), frappe.ValidationError)

	viewport = anchor.get("viewport", "")
	offset = anchor.get("offset") if isinstance(anchor.get("offset"), dict) else {}
	out = {
		"route": route,
		"viewport": viewport[: ANCHOR_TEXT["viewport"]] if isinstance(viewport, str) else "",
		"selector": "",
		"component": "",
		"file": "",
		"element": "",
		"text": "",
		"state": "",
		"componentChain": [],
		"offset": {k: _fraction(offset.get(k)) for k in ("x", "y")},
		"rect": {"x": 0, "y": 0, "w": 0, "h": 0},
		"tile": named,
	}
	if len(json.dumps(out).encode()) > MAX_ANCHOR_BYTES:
		frappe.throw(frappe._("That element description is too large"), CommentTooLarge)

	return out


def where_of(anchor: dict) -> str:
	"""A tile in plain words, for the agent: "Canvas · Overview › Spend summary › option Donut".

	One line of data. The words are the page's own names, taken from a page that may be a
	stranger's, so the agent weighs them and never obeys them.
	"""
	tile = anchor.get("tile") if isinstance(anchor, dict) else None
	if not isinstance(tile, dict):
		return ""

	def say(key: str) -> str:
		value = tile.get(key)
		return " ".join(value.split()) if isinstance(value, str) else ""

	page = say("page") or say("route") or str(anchor.get("route") or "")
	option = say("optionLabel") or say("option")
	kind = tile.get("kind")
	if kind == "set":
		parts = [page, say("group") or say("groupKey"), f"option {option}"]
	elif kind == "state":
		group = say("group")
		parts = [page, *([group] if group and group.lower() != "state" else []), f"state {option}"]
	else:
		parts = [page, "default"]

	return "Canvas · " + " › ".join(p for p in parts if p)


# ------------------------------------------------------------------ internals


def _fraction(value) -> float:
	"""A position on a tile: a finite number held between 0 and 1."""
	if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
		return 0.0

	return min(1.0, max(0.0, float(value)))


def _numbers(value, keys) -> dict:
	value = value if isinstance(value, dict) else {}
	return {k: (float(value[k]) if isinstance(value.get(k), int | float) else 0) for k in keys}


def _plain(value, depth: int = 0) -> bool:
	"""JSON made only of strings, numbers, booleans, lists and dicts, shallow and short."""
	if depth > 4:
		return False

	if isinstance(value, str):
		return len(value) <= 1024

	if isinstance(value, bool | int | float) or value is None:
		return True

	if isinstance(value, list):
		return len(value) <= 24 and all(_plain(v, depth + 1) for v in value)

	if isinstance(value, dict):
		return len(value) <= 24 and all(isinstance(k, str) and _plain(v, depth + 1) for k, v in value.items())

	return False


def _lock(name: str) -> None:
	"""Take the Prototype's row, so two people writing at once wait for each other.

	Every write takes this first and nothing else, so the order never differs.
	"""
	frappe.db.get_value(PROTOTYPE, name, "name", for_update=True)


def _row(name: str, comment: str):
	row = frappe.db.get_value(
		COMMENT, {"name": comment or "", "prototype": name}, ["name", "thread", "author", "text", "anchor"], as_dict=True
	)
	if not row:
		raise frappe.DoesNotExistError

	return row


def _root(name: str, thread: str):
	row = _row(name, thread)
	if row.thread:
		raise frappe.DoesNotExistError

	return row


def _insert(name: str, author: str, text: str, thread: str = "", anchor: str = "") -> str:
	doc = frappe.get_doc(
		{"doctype": COMMENT, "prototype": name, "thread": thread, "author": author, "text": text, "anchor": anchor}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _load(raw) -> dict:
	try:
		data = json.loads(raw or "{}")
	except ValueError:
		return {}

	return data if isinstance(data, dict) else {}


def _ts(creation) -> int:
	"""Unix seconds. Frappe stores a naive time in the system time zone."""
	when = frappe.utils.get_datetime(creation)
	return int(when.replace(tzinfo=ZoneInfo(frappe.utils.get_system_timezone())).timestamp())


def _note_id() -> str:
	return f"c{frappe.generate_hash(length=10)}"
