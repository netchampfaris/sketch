# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""What is new for a person on a Prototype: variants and comments others made since they last looked.

Something is new for you when somebody else made it after you last saw it. Your own
actions are never new to you. There is no email, so these answers are all there is: the
gallery card, the Browse dot, the "New" badge on a tile, the Demo pill's dot, the unread
mark on a thread.

What a person has seen is kept on the server, per Prototype (`Sketch Seen`, written by
`mark`):

- **A variant** is seen once the person has opened its set, or its row in the Demo card.
  When it was made comes from `Sketch Variant Stamp`, written when an agent adds a file
  under `src/variants/@<username>/` (`stamp`). A file with no stamp is never new.
- **A comment thread** is seen once the person has opened it. A reply by someone else
  after that makes it unread again. The person's own comment in a thread counts as
  seeing everything before it.

Two things are news to an invited editor only, until they first open the Prototype (`opened`):
that they were invited, and that the owner made their variant the default of its set.

Who gets what (`standing`):

- A Guest gets nothing.
- The owner and invited editors get variants and comments. Nothing made before an
  editor was invited is new to them.
- A signed-in reader of a public Prototype gets comments only, and only on a Prototype
  they have commented on: nothing before their first comment is new.

A mention is a comment whose `mentions` list holds your username (`sketch.comments`).
Time is the database's own: every compared value is a naive datetime in the system time
zone, so a comparison here never mixes clocks.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta

import frappe

from sketch import sharing

PROTOTYPE = "Sketch Prototype"
COMMENT = "Sketch Comment"
SEEN = "Sketch Seen"
OPENED = ("Opened", "prototype")
STAMP = "Sketch Variant Stamp"

#: How many things one call may mark seen. A page marks a set or a thread at a time.
MAX_MARKS = 100
#: How many people a gallery card shows before "+n".
CARD_PEOPLE = 3

LONG_AGO = datetime(1970, 1, 1)


@dataclass(frozen=True)
class Standing:
	"""One person's place on one Prototype, and the moment before which nothing is new."""

	user: str
	username: str
	role: str
	since: datetime

	@property
	def sees_variants(self) -> bool:
		return self.role in ("owner", "editor")


# ------------------------------------------------------------------- stamping


def stamp(name: str, path: str) -> None:
	"""Record that an agent added this variant file just now. Other files are ignored."""
	if not (sharing.is_editor_path(path) and path.endswith(".vue")):
		return

	row = frappe.db.get_value(STAMP, {"prototype": name, "path": path}, "name")
	if row:
		# The file was deleted and added again: it is new again.
		frappe.db.set_value(STAMP, row, "creation", frappe.utils.now_datetime(), update_modified=False)
		return

	frappe.get_doc({"doctype": STAMP, "prototype": name, "path": path}).insert(ignore_permissions=True)


# -------------------------------------------------------------------- reading


def standing(name: str, user: str, rows: list | None = None) -> Standing | None:
	"""Who this person is here, or None when they get no badges at all."""
	if not user or user == "Guest" or not sharing.can_view(name, user):
		return None

	username = sharing.username_of(user)
	if not username:
		return None

	role = sharing.role_of(name, user)
	if role == "owner":
		return Standing(user, username, role, LONG_AGO)

	if role == "editor":
		since = frappe.db.get_value(sharing.EDITOR, {"prototype": name, "user": user}, "creation")
		return Standing(user, username, role, since or LONG_AGO)

	rows = rows if rows is not None else _rows(name)
	own = [r.creation for r in rows if r.author == username]
	if own:
		return Standing(user, username, "reader", min(own))

	# Named in a comment but never wrote one (they took it back, or were mentioned first): the mention is where they start.
	named = [r.creation for r in rows if username in _mentions(r)]
	return Standing(user, username, "reader", min(named) - timedelta(microseconds=1)) if named else None


def _rows(name: str) -> list:
	return frappe.get_all(
		COMMENT,
		filters={"prototype": name},
		fields=["name", "thread", "author", "creation", "mentions"],
		order_by="creation asc, name asc",
		limit_page_length=0,
	)


def _seen(name: str, user: str) -> dict:
	"""When this person last looked at each thing: {(kind, item): datetime}."""
	rows = frappe.get_all(
		SEEN, filters={"prototype": name, "user": user}, fields=["kind", "item", "seen_at"], limit_page_length=0
	)
	return {(r.kind, r.item): r.seen_at for r in rows}


def opened(name: str, user: str) -> None:
	"""This invited editor has now opened the Prototype: the invitation and any default made of their variant are no longer news."""
	if sharing.is_editor(name, user):
		_record(name, user, *OPENED, frappe.utils.now_datetime())


def _label_of(name: str, path: str) -> str:
	"""The `<variant name>` of an adopted file, or its file name."""
	from sketch import prototype_files

	try:
		meta = sharing.variant_meta(prototype_files.read_files(name, [path])[0]["content"])
	except frappe.ValidationError:
		meta = None

	return (meta or {}).get("name") or path.rsplit("/", 1)[-1].removesuffix(".vue")


def _invited(name: str, who: Standing, seen: dict, owner: dict | None) -> dict | None:
	"""{"by": the owner} while this editor has never opened the Prototype."""
	if who.role != "editor" or OPENED in seen or not owner:
		return None

	invite = frappe.db.get_value(sharing.EDITOR, {"prototype": name, "user": who.user}, "creation")
	return {"by": owner, "at": invite}


def _adopted(name: str, who: Standing, seen: dict, owner: dict | None) -> dict | None:
	"""{"label", "by"} for the newest variant of this editor's that the owner made the default since they last opened it."""
	from sketch import editor_variants

	if who.role != "editor" or not owner:
		return None

	looked = seen.get(OPENED)
	found = []
	for path, row in editor_variants.read_registry(name).items():
		at = row.get("at") if isinstance(row, dict) else None
		if not at or row.get("author") != who.username or not row.get("default"):
			continue

		when = frappe.utils.get_datetime(at)
		if not looked or when > looked:
			found.append((when, path))

	if not found:
		return None

	when, path = max(found)
	return {"label": _label_of(name, path), "by": owner, "at": when}


def _mentions(row) -> list[str]:
	try:
		data = json.loads(row.mentions or "[]")
	except ValueError:
		return []

	return [u for u in data if isinstance(u, str)] if isinstance(data, list) else []


def new_variants(name: str, who: Standing, seen: dict, files: list | None = None) -> list[dict]:
	"""The variants somebody else added since this person last looked: [{option, author, at}]."""
	from sketch import prototype_files

	if not who.sees_variants:
		return []

	stamps = frappe.get_all(STAMP, filters={"prototype": name}, fields=["path", "creation"], limit_page_length=0)
	fresh = []
	for row in stamps:
		author = sharing.author_of_path(row.path)
		option = row.path[len(sharing.VARIANTS_ROOT) + 1 : -len(".vue")]
		if not author or author == who.username or row.creation <= who.since:
			continue

		looked = seen.get(("Variant", option))
		if looked and looked >= row.creation:
			continue

		fresh.append((row, author, option))

	if not fresh:
		return []

	on_disk = {f["path"] for f in (files if files is not None else prototype_files.list_files(name))}
	made_by = sharing.people({author for _row, author, _option in fresh})
	found = []
	for row, author, option in fresh:
		if row.path not in on_disk or author not in made_by or not _is_variant(name, row.path):
			continue

		found.append({"option": option, "author": author, "at": row.creation})

	return found


def _is_variant(name: str, path: str) -> bool:
	"""True when the file declares a `<variant>`. Without one the Runtime shows nothing, so it is not new."""
	from sketch import prototype_files

	try:
		return bool(sharing.variant_meta(prototype_files.read_files(name, [path])[0]["content"]))
	except frappe.ValidationError:
		return False


def threads_state(rows: list, who: Standing, seen: dict) -> dict:
	"""For each thread: the comments that are unread, and whether they mention this person.

	A comment by someone else is unread when it came after the latest of: when the
	person last opened the thread, their own last comment in it, and the moment they got here.
	"""
	by_thread: dict = {}
	for row in rows:
		by_thread.setdefault(row.thread or row.name, []).append(row)

	state = {}
	for thread, items in by_thread.items():
		if not any(r.name == thread for r in items):
			continue

		floor = max(
			[who.since, seen.get(("Thread", thread)) or LONG_AGO, *(r.creation for r in items if r.author == who.username)]
		)
		others = [r for r in items if r.author != who.username]
		fresh = [r for r in others if r.creation > floor]
		hits = [r for r in fresh if who.username in _mentions(r)]
		state[thread] = {
			"unread": len(fresh),
			"mentioned": any(who.username in _mentions(r) for r in others),
			"fresh": fresh,
			"mention": hits[-1] if hits else None,
		}

	return state


def decorate(name: str, user: str, threads: list[dict]) -> list[dict]:
	"""Put `unread` (a count) and `mentioned` on each thread, for the person asking."""
	rows = _rows(name)
	who = standing(name, user, rows)
	state = threads_state(rows, who, _seen(name, user)) if who else {}
	for thread in threads:
		row = state.get(thread["id"], {})
		thread["unread"] = row.get("unread", 0)
		thread["mentioned"] = bool(row.get("mentioned"))

	return threads


# ----------------------------------------------------------------- the answers


def card(name: str, user: str, files: list | None = None) -> dict | None:
	"""The gallery card's line for this person, or None when nothing is new.

	{"ago": when the newest of it happened, as "2 hours ago", "variants": n, "comments": n, "by": [the first three people], "more": how many
	others, "mention": {"by": person, "thread": id} or None, "invited": {"by": person} or None,
	"adopted": {"label": option, "by": person} or None}.
	"""
	rows = _rows(name)
	who = standing(name, user, rows)
	if not who:
		return None

	seen = _seen(name, user)
	variants = new_variants(name, who, seen, files)
	state = threads_state(rows, who, seen)
	fresh = [r for s in state.values() for r in s["fresh"]]
	owner = None
	if who.role == "editor":
		handle = sharing.username_of(sharing.owner_of(name) or "")
		found = sharing.people([handle])
		owner = {"username": handle, **found[handle]} if handle in found else None

	invited = _invited(name, who, seen, owner)
	adopted = _adopted(name, who, seen, owner)
	if not variants and not fresh and not invited and not adopted:
		return None

	# Newest first, one entry per person.
	activity = sorted([(v["at"], v["author"]) for v in variants] + [(r.creation, r.author) for r in fresh], reverse=True)
	order = list(dict.fromkeys(author for _at, author in activity))
	known = sharing.people(order)
	people = [{"username": u, **known[u]} for u in order if u in known]
	mentions = [s["mention"] for s in state.values() if s["mention"]]
	mention = None
	if mentions:
		row = max(mentions, key=lambda r: r.creation)
		by = known.get(row.author)
		if by:
			mention = {"by": {"username": row.author, **by}, "thread": row.thread or row.name}

	# When the newest of it happened, for the card's " · 2 hours ago". The moments stay on the server.
	moments = [at for at, _author in activity] + [n.pop("at") for n in (invited, adopted) if n]
	newest = max((frappe.utils.get_datetime(m) for m in moments if m), default=None)

	return {
		"ago": frappe.utils.pretty_date(newest) if newest else "",
		"variants": len(variants),
		"comments": len(fresh),
		"by": people[:CARD_PEOPLE],
		"more": max(0, len(people) - CARD_PEOPLE),
		"mention": mention,
		"invited": invited,
		"adopted": adopted,
	}


def page(name: str, user: str) -> dict | None:
	"""What the Viewer needs to draw its dots and badges: the new options, and the unread threads.

	{"variants": [option, ...], "threads": [{"id", "route", "unread", "mention"}]}. None for
	a person who gets no badges.
	"""
	rows = _rows(name)
	who = standing(name, user, rows)
	if not who:
		return None

	seen = _seen(name, user)
	state = threads_state(rows, who, seen)
	unread = {t: s for t, s in state.items() if s["unread"]}
	routes = {}
	if unread:
		for r in frappe.get_all(
			COMMENT, filters={"name": ["in", list(unread)]}, fields=["name", "anchor"], limit_page_length=0
		):
			try:
				routes[r.name] = str(json.loads(r.anchor or "{}").get("route") or "")
			except (ValueError, AttributeError):
				routes[r.name] = ""

	return {
		"variants": [v["option"] for v in new_variants(name, who, seen)],
		"threads": [
			{"id": t, "route": routes.get(t, ""), "unread": s["unread"], "mention": bool(s["mention"])}
			for t, s in unread.items()
		],
	}


# -------------------------------------------------------------------- marking


def mark(name: str, user: str, variants=(), threads=()) -> int:
	"""This person has now seen these variants (option values) and threads (first comment ids).

	Anything that is not a variant or a thread of this Prototype is dropped, so a stale
	page marks nothing it should not. Returns how many were recorded.
	"""
	from sketch import editor_variants

	if not standing(name, user):
		raise frappe.DoesNotExistError

	options = [v for v in _strings(variants) if editor_variants.is_extra(v)]
	ids = _strings(threads)
	if ids:
		ids = frappe.get_all(
			COMMENT,
			filters={"prototype": name, "name": ["in", ids], "thread": ["is", "not set"]},
			pluck="name",
			limit_page_length=0,
		)

	now = frappe.utils.now_datetime()
	for kind, keys in (("Variant", options), ("Thread", ids)):
		for item in keys:
			_record(name, user, kind, item, now)

	return len(options) + len(ids)


def _strings(value) -> list[str]:
	if not isinstance(value, list | tuple):
		return []

	return list(dict.fromkeys(v for v in value if isinstance(v, str) and 0 < len(v) <= 300))[:MAX_MARKS]


def _record(name: str, user: str, kind: str, item: str, when) -> None:
	filters = {"prototype": name, "user": user, "kind": kind, "item": item}
	row = frappe.db.get_value(SEEN, filters, "name")
	if row:
		frappe.db.set_value(SEEN, row, "seen_at", when, update_modified=False)
		return

	try:
		frappe.get_doc({"doctype": SEEN, **filters, "seen_at": when}).insert(ignore_permissions=True)
	except frappe.DuplicateEntryError:
		# Two tabs marked the same thing at once.
		frappe.db.set_value(SEEN, filters, "seen_at", when, update_modified=False)
