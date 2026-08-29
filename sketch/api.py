# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The whitelisted methods the Sketch SPA calls.

Every list read goes through `frappe.get_list`. `frappe.get_all` sets
`ignore_permissions=True` and so drops the `if_owner` rule, which shows every
user's Prototypes to every other user (spec 2, Permissions).

Every method carries type annotations, because `require_type_annotated_api_methods`
is set in hooks.py.
"""

import os
from datetime import UTC, datetime

import frappe
from frappe.utils import convert_utc_to_system_timezone, pretty_date

from sketch import prototype, prototype_files, versions
from sketch.sketch.doctype.sketch_token import sketch_token

#: The eight recipes from ui.frappe.io/recipes, plus Blank (spec 10). The trees
#: are vendored at sketch/recipes/<slug>/src/. This table only names them.
RECIPES = {
	"blank": ("Blank", "An empty app shell with one page.", "lucide-file"),
	"discussions": ("Discussions", "Threaded discussions with a reply composer.", "lucide-messages-square"),
	"compose": ("Compose", "A writing surface with a formatting toolbar.", "lucide-pen-line"),
	"deals": ("Deals", "A sales pipeline with stages and deal detail.", "lucide-handshake"),
	"tickets": ("Tickets", "A support queue with status and priority.", "lucide-life-buoy"),
	"mail": ("Mail", "An inbox with a message list and a reading pane.", "lucide-mail"),
	"files": ("Files", "A file browser with folders and a details panel.", "lucide-folder"),
	"tasks": ("Tasks", "A task board with groups and assignees.", "lucide-square-check-big"),
	"accounting": ("Accounting", "An invoice ledger with totals.", "lucide-landmark"),
}

#: Recipe order in the picker. Blank first, because it is what the dialog opens
#: on (frontend/src/components/NewPrototypeDialog.vue:71).
RECIPE_ORDER = list(RECIPES)

#: The one MCP endpoint an agent connects to (spec 8).
MCP_PATH = "/mcp"

#: Recipe files write this token wherever the Prototype's own name belongs.
#: `create_prototype` replaces it with the title the user typed, in every file
#: of every recipe, so the first page a new user opens carries their name and
#: not a placeholder (review 6.2). A recipe that does not use the token is
#: unaffected: the replace is a no-op.
#:
#: The token stays readable on its own, because `sketch/tests/test_recipes_boot.py`
#: writes each recipe tree unsubstituted and boots it. Anything that must
#: compile after the replace has to compile before it too.
TITLE_TOKEN = "__SKETCH_TITLE__"

#: Characters dropped from a title before it is substituted into a recipe file.
#: A recipe file is a Vue single-file component compiled in the browser, and the
#: token sits in template text or in an attribute. `<` and `>` open a tag, `{`
#: and `}` open an interpolation, and a quote or a backslash ends an attribute
#: early, so any of them turns a user's name into a compile error on the first
#: screen they see. Only the copy written into source is stripped. The
#: Prototype's own `title` field keeps every character.
_TITLE_UNSAFE = str.maketrans(dict.fromkeys("<>{}\"'`\\"))


def _recipes_root() -> str:
	"""Absolute path to the vendored recipe trees."""
	return frappe.get_app_path("sketch", "recipes")


def _recipe_tree(slug: str) -> list[dict]:
	"""Every file of a vendored recipe, as write_files takes them.

	Returns [] when the recipe is not on disk.
	"""
	root = os.path.join(_recipes_root(), slug)
	if not os.path.isdir(root):
		return []

	files = []
	for folder, _dirs, names in os.walk(root):
		for entry in sorted(names):
			full = os.path.join(folder, entry)
			rel = os.path.relpath(full, root).replace(os.sep, "/")
			try:
				with open(full, encoding="utf-8") as handle:
					files.append({"path": rel, "content": handle.read()})
			except (OSError, UnicodeDecodeError):
				continue

	return sorted(files, key=lambda item: item["path"])


def _title_for_source(title: str) -> str:
	"""The title as it can be pasted into a Vue single-file component.

	Drops the characters in `_TITLE_UNSAFE` and collapses whitespace, so a
	newline or a stray quote cannot break the compile of the first page the
	user opens. Falls back to "Untitled" when nothing survives, which is only
	reachable for a title made entirely of those characters.
	"""
	cleaned = " ".join((title or "").translate(_TITLE_UNSAFE).split())
	return cleaned or "Untitled"


def _apply_title(files: list[dict], title: str) -> list[dict]:
	"""Replace TITLE_TOKEN with `title` in every file of a recipe tree.

	Runs over the whole tree, not one named file, so a recipe puts the token
	wherever it needs the name: a heading, a sidebar title, a document title.
	A recipe with no token comes back unchanged.
	"""
	safe = _title_for_source(title)
	return [dict(entry, content=entry["content"].replace(TITLE_TOKEN, safe)) for entry in files]


def _content_modified(name: str, files: list[dict]) -> str:
	"""When this Prototype's files last changed, on the site clock.

	Not `Sketch Prototype.modified`. Every doc write moves that field, so
	flipping the public switch reset the card to "Updated 1 second ago" and
	jumped it to the head of the gallery, which sorted on the same field
	(review 5.7). Only an agent writing files is a change the user asked for,
	so the newest mtime in the tree is what the label and the order both read.

	`files` is the listing the caller already walked, so this costs one stat
	per file and no second walk. Returns "" when nothing can be stat'ed,
	including an empty tree.
	"""
	base = prototype_files.prototype_dir(name)
	newest = 0.0
	for row in files:
		try:
			newest = max(newest, os.stat(os.path.join(base, row["path"])).st_mtime)
		except OSError:
			continue

	if not newest:
		return ""

	# st_mtime is epoch UTC. `pretty_date` subtracts against `now_datetime()`,
	# which is the site's timezone (frappe/utils/data.py:1866), so an
	# unconverted stamp reads hours out and can print a time in the future.
	local = convert_utc_to_system_timezone(datetime.fromtimestamp(newest, tz=UTC))
	return local.strftime("%Y-%m-%d %H:%M:%S")


def _public_base() -> str:
	"""The public origin a shared link carries.

	get_url() appends webserver_port in developer mode, which a copied link
	must never hold. site_config host_name is the public host. Mirrors
	sketch.prototype.public_url, which owns the Prototype URL itself.
	"""
	base = (frappe.local.conf.host_name or frappe.local.conf.hostname or frappe.utils.get_url()).rstrip("/")
	if not base.startswith(("http://", "https://")):
		base = "https://" + base

	return base


def _username() -> str:
	"""The session user's username. Empty when it is not set."""
	return frappe.db.get_value("User", frappe.session.user, "username") or ""


def _row(doc_or_dict) -> dict:
	"""One gallery item.

	`file_count`, the description and the timestamp all come off disk, because
	no field stores them and a stored copy drifts (spec 2).

	`modified` here is the tree's stamp, not the document's field. The card and
	the gallery order both read it, so a visibility toggle no longer moves a
	card (review 5.7). Callers that need the document's own `modified` must
	read the document.
	"""
	name = doc_or_dict.get("name")
	slug = doc_or_dict.get("slug")
	pin = doc_or_dict.get("pin")
	files = prototype_files.list_files(name)
	count = len(files)
	username = _username()
	# Falls back to `creation`, never to `modified`. `modified` is the field
	# that moves on a visibility toggle, which is the jump this stamp exists to
	# stop, and an empty tree has no mtime of its own to report.
	updated_at = _content_modified(name, files) or str(doc_or_dict.get("creation") or "")
	return {
		"name": name,
		"title": doc_or_dict.get("title"),
		"slug": slug,
		"pin": pin,
		"is_public": bool(doc_or_dict.get("is_public")),
		"file_count": count,
		# The pin is deliberately out of this line. It used to lead it, which
		# made the frappe-ui version the loudest fact about a Prototype and told
		# a new user nothing they could act on (review 5.8). It stays in the
		# `pin` field above, for the surfaces that print a build detail.
		"description": f"{count} {'file' if count == 1 else 'files'}",
		"modified": updated_at,
		"updated": pretty_date(updated_at) if updated_at else "",
		"viewer_path": f"/u/{username}/{slug}",
		"public_url": f"{_public_base()}/u/{username}/{slug}",
	}


@frappe.whitelist()
def get_session() -> dict:
	"""The signed-in user, plus what the Settings screen needs to render."""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(frappe._("Sign in to use Sketch"), frappe.PermissionError)

	full_name, username, user_image = frappe.db.get_value(
		"User", user, ["full_name", "username", "user_image"]
	)
	# One read for both answers. The shell shows the connection state on the
	# first screen, and it must not call get_agent_token to learn it:
	# get_or_create mints a token, which rendering a screen must never do.
	row = frappe.db.get_value("Sketch Token", {"user": user}, ["name", "last_used"], as_dict=True)
	last_used = str(row.last_used) if row and row.last_used else None
	return {
		"user": user,
		"username": username or "",
		"full_name": full_name or user,
		"user_image": user_image or "",
		"has_token": bool(row),
		"last_used": last_used,
		"last_used_pretty": pretty_date(last_used) if last_used else None,
		"mcp_endpoint": _public_base() + MCP_PATH,
		"logout_url": "/api/method/logout",
	}


@frappe.whitelist()
def list_prototypes() -> list[dict]:
	"""Every Prototype this user owns, newest first.

	The owner filter is explicit, and not left to the `if_owner` permission
	rule. `if_owner` is per role: `Sketch User` carries it, `System Manager`
	does not. Without the filter a System Manager sees all 32 Prototypes on the
	site, and then the Viewer answers 404 for each one it does not own, because
	the Viewer serves the owner or a public Prototype and nobody else.

	`frappe.get_all` would also drop the permission check, so keep `get_list`.

	The order is the tree's stamp, the same one the card prints. Ordering on
	the document's `modified` meant a visibility toggle sent a card to the top
	and moved every other card under the pointer (review 5.7). SQL cannot see
	an mtime, so the sort happens here.
	"""
	rows = frappe.get_list(
		"Sketch Prototype",
		filters={"owner": frappe.session.user},
		fields=["name", "title", "slug", "pin", "is_public", "creation"],
		order_by="creation desc",
		limit_page_length=0,
	)
	items = [_row(row) for row in rows]
	# Python's sort is stable, so the SQL order above survives as the tiebreak
	# between two Prototypes whose newest file carries the same second.
	items.sort(key=lambda item: item["modified"], reverse=True)
	return items


@frappe.whitelist()
def list_versions(slug: str) -> list[dict]:
	"""The version history of one Prototype, newest first.

	`resolve_owned` is the permission check. `versions.history` reads with
	`frappe.get_all`, so it must never take a slug from the client.

	Each row carries both time fields the card uses: `creation` is the absolute
	timestamp for the hover title, `created` is the relative line the UI shows.
	"""
	doc = prototype.resolve_owned(slug)
	rows = []
	for row in versions.history(doc.name):
		rows.append(
			{
				"name": row.get("name"),
				"sequence": row.get("sequence"),
				"prompt": row.get("prompt") or "",
				"summary": row.get("summary") or "",
				"changes": row.get("changes") or [],
				"files_added": row.get("files_added") or 0,
				"files_modified": row.get("files_modified") or 0,
				"files_deleted": row.get("files_deleted") or 0,
				"creation": str(row.get("creation") or ""),
				"created": pretty_date(row.get("creation")) if row.get("creation") else "",
			}
		)

	return rows


@frappe.whitelist()
def prototype_revision(slug: str) -> dict:
	"""The current revision of one Prototype's tree, for the Viewer's poller.

	`resolve_owned` is the permission check, so only the owner may poll. The
	Viewer reloads itself when the revision it reads differs from the one it
	started with.
	"""
	doc = prototype.resolve_owned(slug)
	return {"rev": prototype_files.revision(doc.name)}


@frappe.whitelist()
def list_recipes() -> list[dict]:
	"""The Recipes the picker offers.

	Reads the vendored trees off disk. A recipe with no tree is still listed,
	marked `available: false`, so the picker never silently loses one. Blank
	carries no exception: it is a vendored tree like the other eight, and
	`create_prototype` refuses any recipe that is not on disk.
	"""
	root = _recipes_root()
	on_disk = set()
	if os.path.isdir(root):
		on_disk = {entry for entry in os.listdir(root) if os.path.isdir(os.path.join(root, entry))}

	slugs = RECIPE_ORDER + sorted(on_disk - set(RECIPE_ORDER))
	recipes = []
	for slug in slugs:
		label, description, icon = RECIPES.get(slug, (slug.replace("-", " ").title(), "", "lucide-file"))
		recipes.append(
			{
				"slug": slug,
				"label": label,
				"description": description,
				"icon": icon,
				"available": slug in on_disk,
			}
		)

	return recipes


@frappe.whitelist(methods=["POST"])
def create_prototype(title: str, recipe: str = "blank") -> dict:
	"""Create a Prototype and write the chosen Recipe into its directory.

	The tree is written with TITLE_TOKEN replaced by the Prototype's title, so
	the first page carries the name the user just typed. `doc.title` is used
	and not the argument, because `prototype.create` strips it.

	Every recipe comes off disk, `blank` included. `blank` used to have a
	second tree inlined here as a fallback, and the two then disagreed about
	the first screen: the inlined one had a DesktopShell and a one-item
	sidebar, the vendored one at sketch/recipes/blank/src/App.vue is a bare
	RouterView. The vendored tree is the one users saw, so the copy is gone.
	"""
	recipe = (recipe or "blank").strip().lower()
	if recipe not in RECIPES and recipe not in _recipe_tree_slugs():
		frappe.throw(frappe._("No recipe named {0}").format(recipe), frappe.ValidationError)

	files = _recipe_tree(recipe)
	if not files:
		# Named in RECIPES but not vendored. The check runs before
		# `prototype.create`, so a broken install leaves no empty Prototype
		# behind and the user reads why instead of a blank first screen.
		frappe.throw(frappe._("The {0} recipe is not installed").format(recipe), frappe.ValidationError)

	doc = prototype.create(title)
	prototype_files.write_files(doc.name, _apply_title(files, doc.title))

	return _row(doc.as_dict())


def _recipe_tree_slugs() -> set:
	"""Recipe folder names on disk."""
	root = _recipes_root()
	if not os.path.isdir(root):
		return set()

	return {entry for entry in os.listdir(root) if os.path.isdir(os.path.join(root, entry))}


@frappe.whitelist(methods=["POST"])
def rename_prototype(slug: str, title: str) -> dict:
	"""Change the display title. The slug and the public URL never move."""
	title = (title or "").strip()
	if not title:
		frappe.throw(frappe._("Title is required"), frappe.ValidationError)

	doc = prototype.resolve_owned(slug)
	doc.title = title
	doc.save()
	return _row(doc.as_dict())


@frappe.whitelist(methods=["POST"])
def set_public(slug: str, is_public: bool) -> dict:
	"""Turn the public link on or off."""
	doc = prototype.resolve_owned(slug)
	doc.is_public = 1 if is_public else 0
	doc.save()
	return _row(doc.as_dict())


@frappe.whitelist(methods=["POST"])
def delete_prototype(slug: str) -> dict:
	"""Delete a Prototype. `on_trash` removes its directory."""
	doc = prototype.resolve_owned(slug)
	name = doc.name
	frappe.delete_doc("Sketch Prototype", name)
	return {"name": name}


@frappe.whitelist()
def get_agent_token() -> dict:
	"""The user's token, the MCP endpoint, and when an agent last used it.

	`last_used` is read after get_or_create, so a token minted on this call
	reports null. `sketch.auth` stamps the field on a good `/mcp` request.
	"""
	token = sketch_token.get_or_create(frappe.session.user)
	last_used = frappe.db.get_value("Sketch Token", {"user": frappe.session.user}, "last_used")
	last_used = str(last_used) if last_used else None
	return {
		"token": token,
		"endpoint": _public_base() + MCP_PATH,
		"last_used": last_used,
		"last_used_pretty": pretty_date(last_used) if last_used else None,
	}


@frappe.whitelist(methods=["POST"])
def regenerate_agent_token() -> dict:
	"""Write a new token over the old one. A write, never a delete."""
	return {
		"token": sketch_token.regenerate(frappe.session.user),
		"endpoint": _public_base() + MCP_PATH,
	}
