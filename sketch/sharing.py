# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""Who may do what on a Prototype: the owner, invited editors, and everyone else.

The owner invites people by Sketch username (`invite`). An invited editor:

- sees the Prototype under "Shared with me", and reaches it while it is private;
- reads and comments, like anyone signed in who may see it;
- has an agent that can add variants and delete its own, writing only under its
  own folder, `src/variants/@<username>/` (`check_paths`).

An editor never changes the owner's files, notes, tweaks or defaults, and never
sees the owner's notes. Those stay with the owner (decision 29).

## Who made a variant

A variant's author is the folder it sits in. The server lets an editor's token
write that one folder and no other, so a file under `@arohi/` was written by
Arohi's token (or by the owner's agent, which can write anywhere and is trusted
with the whole tree). The file's contents are never read for a name. The page
gets the author's name and picture from the User row (`authors`), so a file
cannot claim a different person, and a folder that matches no user shows no
label and is not merged.

## Adopted variants

"Make default" on an editor's option moves the file into the owner's own tree,
`src/variants/adopted/`, and records who made it in `src/variants/adopted.json`.
That registry is written by the server only. An editor can reach neither the
folder nor the file, so it cannot forge or erase an attribution.
"""

import json
import posixpath
import re

import frappe

PROTOTYPE = "Sketch Prototype"
EDITOR = "Sketch Prototype Editor"

#: The most people one Prototype can be shared with.
MAX_EDITORS = 50

#: Where editors write: one folder each, named after their username.
VARIANTS_ROOT = "src/variants"
EDITOR_PREFIX = f"{VARIANTS_ROOT}/@"
ADOPTED_DIR = f"{VARIANTS_ROOT}/adopted/"
ADOPTED_FILE = f"{VARIANTS_ROOT}/adopted.json"

#: What an editor may write. Source only: no CSS, so an editor's styles can never
#: leak onto the owner's page.
EDITOR_EXTENSIONS = (".vue", ".ts", ".js")

#: How much one editor may keep in their folder. The tree has quotas of its own
#: (`prototype_files.MAX_TREE_FILES`), and without these one editor could spend them all.
MAX_EDITOR_FILES = 30
MAX_EDITOR_BYTES = 400_000

USERNAME = re.compile(r"[a-z][a-z0-9-]{2,29}")
FOLDER = re.compile(r"src/variants/@([a-z0-9-]+)/")
VARIANT_TAG = re.compile(r"<variant\b([^>]*?)/?>", re.IGNORECASE)
ATTR = re.compile(r"""([a-zA-Z-]+)\s*=\s*(?:"([^"]*)"|'([^']*)')""")
MAX_NAME = 60


# ---------------------------------------------------------------------- access


def owner_of(name: str) -> str | None:
	return frappe.db.get_value(PROTOTYPE, name, "owner")


def is_editor(name: str, user: str) -> bool:
	"""True when this user is invited to the Prototype."""
	if not user or user == "Guest":
		return False

	return bool(frappe.db.exists(EDITOR, {"prototype": name, "user": user}))


def can_view(name: str, user: str) -> bool:
	"""May this user see the Prototype and comment on it? A Guest may view a public one.

	Private means the owner and the people invited, nobody else (decision 30).
	"""
	row = frappe.db.get_value(PROTOTYPE, name, ["owner", "is_public"], as_dict=True)
	if not row:
		return False

	if row.is_public:
		return True

	return user != "Guest" and (row.owner == user or is_editor(name, user))


def role_of(name: str, user: str) -> str:
	"""owner, editor, viewer (signed in, no standing), guest, or "" for a Prototype that is gone."""
	row = frappe.db.get_value(PROTOTYPE, name, ["owner"], as_dict=True)
	if not row:
		return ""

	if user == "Guest":
		return "guest"

	if row.owner == user:
		return "owner"

	return "editor" if is_editor(name, user) else "viewer"


def username_of(user: str) -> str:
	return frappe.db.get_value("User", user, "username") or ""


def person(user: str) -> dict:
	"""How a person shows in a list: username, full name, picture."""
	row = frappe.db.get_value("User", user, ["username", "full_name", "user_image"], as_dict=True) or {}
	username = row.get("username") or ""
	return {
		"user": user,
		"username": username,
		"full_name": (row.get("full_name") or "").strip() or username or user,
		"user_image": row.get("user_image") or "",
	}


def editors(name: str) -> list[dict]:
	"""Everyone invited to this Prototype, in the order they were invited."""
	users = frappe.get_all(
		EDITOR, filters={"prototype": name}, pluck="user", order_by="creation asc, name asc", limit_page_length=0
	)
	return [person(user) for user in users]


def shared_with(user: str) -> list[str]:
	"""The Prototype ids this user is invited to, newest invitation first."""
	if not user or user == "Guest":
		return []

	return frappe.get_all(
		EDITOR, filters={"user": user}, pluck="prototype", order_by="creation desc", limit_page_length=0
	)


# --------------------------------------------------------------------- invites


def find_user(username: str) -> str | None:
	"""The enabled user with exactly this Sketch username, or None. No search, no partial match."""
	username = (username or "").strip().lstrip("@").lower()
	if not USERNAME.fullmatch(username):
		return None

	return frappe.db.get_value("User", {"username": username, "enabled": 1}, "name")


def invite(doc, username: str) -> dict:
	"""Invite a person by their exact username. Returns the person.

	The caller has checked that the session user owns `doc`. Raises
	frappe.ValidationError with a message for the Share dialog to print.
	"""
	typed = (username or "").strip().lstrip("@")
	user = find_user(typed)
	if not user or user in ("Administrator", "Guest"):
		frappe.throw(frappe._("No Sketch user called “{0}”").format(typed[:60]), frappe.ValidationError)

	if user == doc.owner:
		frappe.throw(frappe._("That's you"), frappe.ValidationError)

	who = person(user)
	if is_editor(doc.name, user):
		frappe.throw(
			frappe._("{0} is already an editor").format(who["full_name"]), frappe.ValidationError
		)

	if frappe.db.count(EDITOR, {"prototype": doc.name}) >= MAX_EDITORS:
		frappe.throw(
			frappe._("A prototype can be shared with {0} people at most").format(MAX_EDITORS),
			frappe.ValidationError,
		)

	frappe.get_doc({"doctype": EDITOR, "prototype": doc.name, "user": user}).insert(ignore_permissions=True)
	return who


def remove(doc, username: str) -> dict:
	"""Take an editor off a Prototype. Their variants stay, and so does their folder. Returns the person."""
	user = find_user(username) or frappe.db.get_value("User", {"username": (username or "").strip()}, "name")
	row = user and frappe.db.get_value(EDITOR, {"prototype": doc.name, "user": user}, "name")
	if not row:
		raise frappe.DoesNotExistError(frappe._("That person is not an editor"))

	who = person(user)
	frappe.delete_doc(EDITOR, row, ignore_permissions=True, force=True)
	return who


# ----------------------------------------------------------------------- paths


def normal(path) -> str:
	"""A path as the tree names it: slashes forward, `.` segments gone."""
	if not isinstance(path, str):
		return ""

	return posixpath.normpath(path.strip().replace("\\", "/"))


def folder(username: str) -> str:
	return f"{EDITOR_PREFIX}{username}/"


def author_of_path(path: str) -> str | None:
	"""The username whose folder holds this path, or None for the owner's own files."""
	match = FOLDER.match(normal(path))
	return match.group(1) if match else None


def is_editor_path(path: str) -> bool:
	return author_of_path(path) is not None


def check_paths(name: str, username: str, paths: list[str]) -> None:
	"""Refuse any path outside the editor's own folder. Raises PermissionError.

	Every write tool of an editor's agent calls this before it touches disk. The
	rule is on the normalised path, so `src/variants/@arohi/../../App.vue` and a
	neighbour's folder both fail. `prototype_files.safe_join` still runs after it.
	"""
	root = folder(username)
	for path in paths:
		clean = normal(path)
		if not clean.startswith(root) or clean == root:
			frappe.throw(
				frappe._("You can add files under {0} only. {1} belongs to the owner.").format(root, path),
				frappe.PermissionError,
			)

		if not clean.endswith(EDITOR_EXTENSIONS):
			frappe.throw(
				frappe._("{0}: a variant is a .vue, .ts or .js file.").format(path), frappe.ValidationError
			)

		if "\x00" in clean:
			frappe.throw(frappe._("Path must not contain a null byte"), frappe.ValidationError)


def check_quota(name: str, username: str, entries: list[dict]) -> None:
	"""One editor's folder holds a few small files. `entries` are {"path", "content"} about to be written."""
	from sketch import prototype_files

	root = folder(username)
	sizes = {
		row["path"]: row["size"] for row in prototype_files.list_files(name) if row["path"].startswith(root)
	}
	for entry in entries:
		content = entry.get("content")
		if isinstance(content, str):
			sizes[normal(entry.get("path"))] = len(content.encode("utf-8"))

	if len(sizes) > MAX_EDITOR_FILES:
		frappe.throw(
			frappe._("Your folder holds at most {0} files. Delete one before you add another.").format(
				MAX_EDITOR_FILES
			),
			frappe.ValidationError,
		)

	if sum(sizes.values()) > MAX_EDITOR_BYTES:
		frappe.throw(
			frappe._("Your folder holds at most {0} KB.").format(MAX_EDITOR_BYTES // 1000),
			frappe.ValidationError,
		)


# -------------------------------------------------------------------- variants


def variant_meta(source: str) -> dict | None:
	"""What a `.vue` file's `<variant>` tag declares, or None when it has none.

	`<variant set="KPI strip" name="Compact" />` adds an option to the owner's
	`<Variants name="KPI strip">`. `<variant component="src/components/KpiStrip.vue"
	name="Compact" />` starts a set around that component, the original being
	option 1. Raises frappe.ValidationError for a tag that cannot work, so the
	editor's agent hears about it when it writes the file.
	"""
	match = VARIANT_TAG.search(source or "")
	if not match:
		return None

	attrs = {m.group(1).lower(): (m.group(2) if m.group(2) is not None else m.group(3)).strip() for m in ATTR.finditer(match.group(1))}
	name = attrs.get("name", "")
	target_set = attrs.get("set", "")
	component = attrs.get("component", "")
	if not name or len(name) > MAX_NAME:
		frappe.throw(
			frappe._('<variant> needs name="…", the option\'s label, up to {0} characters.').format(MAX_NAME),
			frappe.ValidationError,
		)

	if bool(target_set) == bool(component):
		frappe.throw(
			frappe._('<variant> needs exactly one of set="…" (a <Variants> set) or component="…" (a file).'),
			frappe.ValidationError,
		)

	if component and not (component.startswith("src/") and component.endswith(".vue")):
		frappe.throw(
			frappe._('<variant component="…"> is the full path of a .vue file, such as src/components/KpiStrip.vue.'),
			frappe.ValidationError,
		)

	return {"name": name, "set": target_set, "component": component}


def check_sources(entries: list[dict]) -> None:
	"""Validate the `<variant>` tag of every .vue an editor writes."""
	for entry in entries:
		content = entry.get("content")
		if isinstance(content, str) and normal(entry.get("path")).endswith(".vue"):
			variant_meta(content)


# --------------------------------------------------------------------- adopted


def read_adopted(tree: dict) -> dict:
	"""The registry in a tree ({path: source}): {file: {"author", "default"}}."""
	try:
		data = json.loads(tree.get(ADOPTED_FILE) or "{}")
	except ValueError:
		return {}

	return data if isinstance(data, dict) else {}


def authors(tree_paths) -> dict:
	"""Name and picture for every author the tree names, by username.

	Looked up from the User rows, never from the files: a folder for a person who
	does not exist gets no entry, and its variants are not merged.
	"""
	names = set()
	for path in tree_paths:
		who = author_of_path(path)
		if who:
			names.add(who)

	return people(names)


def people(usernames) -> dict:
	usernames = {u for u in usernames if u}
	if not usernames:
		return {}

	rows = frappe.get_all(
		"User",
		filters={"username": ["in", list(usernames)], "enabled": 1},
		fields=["username", "full_name", "user_image"],
	)
	return {
		row.username: {"name": (row.full_name or "").strip() or row.username, "image": row.user_image or ""}
		for row in rows
	}


def adopted_authors(registry: dict) -> dict:
	return people({v.get("author") for v in registry.values() if isinstance(v, dict)})
