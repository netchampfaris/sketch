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

from sketch import checkd, prototype, prototype_files, signature, thumbnail, thumbnails, versions
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


def _tree_stamp(name: str, files: list[dict]) -> tuple[str, str]:
	"""When this Prototype's files last changed, and the revision string.

	Two answers from one stat pass, because both callers need both and the
	tree is on disk. `files` is the listing the caller already walked, so this
	costs one stat per file and no second walk. Asking
	`prototype_files.revision()` for the second answer would walk it again.

	The first value is the timestamp on the site clock. Not
	`Sketch Prototype.modified`: every doc write moves that field, so flipping
	the public switch reset the card to "Updated 1 second ago" and jumped it to
	the head of the gallery, which sorted on the same field (review 5.7). Only
	an agent writing files is a change the user asked for, so the newest mtime
	in the tree is what the label and the order both read.

	The second is `prototype_files.revision()`'s own format, file count and
	newest mtime in nanoseconds, and it must stay that format: the thumbnail
	sidecar is written against one and compared against the other
	(`sketch/thumbnails.py`).

	Both are "" when nothing can be stat'ed, including an empty tree.
	"""
	base = prototype_files.prototype_dir(name)
	count = 0
	newest_ns = 0
	for row in files:
		try:
			stat = os.stat(os.path.join(base, row["path"]))
		except OSError:
			continue

		count += 1
		if stat.st_mtime_ns > newest_ns:
			newest_ns = stat.st_mtime_ns

	if not newest_ns:
		return "", ""

	# st_mtime is epoch UTC. `pretty_date` subtracts against `now_datetime()`,
	# which is the site's timezone (frappe/utils/data.py:1866), so an
	# unconverted stamp reads hours out and can print a time in the future.
	local = convert_utc_to_system_timezone(datetime.fromtimestamp(newest_ns / 1e9, tz=UTC))
	return local.strftime("%Y-%m-%d %H:%M:%S"), f"{count}-{newest_ns}"


def _card_image(name: str, username: str, slug: str, rev: str, owner: str) -> dict | None:
	"""The card pictures, one URL per theme, and a refresh when they are old.

	Returns None when this Prototype has never been captured. The card then
	draws its placeholder, which is the ordinary state of a Prototype whose
	agent has not run `check` with `screenshot: true` yet.

	Only the themes actually on disk are named. A dark capture that failed
	leaves `dark` absent rather than pointing at a 404, so the reader falls
	back to `light` without a request that it knows will fail.

	A stale picture is still returned. A card that blanked itself the moment a
	file changed would flicker on every agent write, and the old picture is a
	true picture of an older tree. The refresh is asked for in the background,
	and the gallery poll that follows picks up the new one.

	The URL is keyed on the capture stamp, never on `rev`. `rev` says which
	tree the picture is of, which is the staleness question above; it does not
	change when a picture is re-taken of a tree that did not move, and that is
	what Refresh preview does.

	Only the owner's own read asks for a refresh. `public_prototypes` carries
	`allow_guest`, and a POST to it commits, so the queued jobs fire: a
	stranger reading the feed used to buy one Chromium capture per stale card,
	and a tree that never mounts writes no sidecar and so stays stale for ever
	(review 3.9). `owner` is passed in, because both callers already hold it.
	A stranger still sees the picture on disk; only the capture is the owner's.
	"""
	state = thumbnails.state(name, rev)
	if state != "fresh" and frappe.session.user == owner:
		thumbnails.request_refresh(name)

	if state == "missing":
		return None

	key = thumbnails.stamp(name)
	themes = thumbnails.meta(name).get("themes") or []
	return {theme: thumbnail.url(username, slug, theme, key) for theme in themes}


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
	# Every caller here hands over a row the session user owns, and `owner` is
	# read for `_card_image`, which asks for a capture only for the owner.
	owner = doc_or_dict.get("owner")
	files = prototype_files.list_files(name)
	count = len(files)
	username = _username()
	# Falls back to `creation`, never to `modified`. `modified` is the field
	# that moves on a visibility toggle, which is the jump this stamp exists to
	# stop, and an empty tree has no mtime of its own to report.
	updated_at, rev = _tree_stamp(name, files)
	updated_at = updated_at or str(doc_or_dict.get("creation") or "")
	return {
		"name": name,
		"title": doc_or_dict.get("title"),
		"slug": slug,
		"pin": pin,
		"is_public": bool(doc_or_dict.get("is_public")),
		"file_count": count,
		# One URL per theme, or None for a Prototype nobody has checked yet.
		# The gallery draws a picture, never a live Viewer: twelve iframes meant
		# twelve Runtimes (`sketch/thumbnails.py`).
		"thumbnail": _card_image(name, username, slug, rev, owner),
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
		fields=["name", "title", "slug", "pin", "is_public", "creation", "owner"],
		order_by="creation desc",
		limit_page_length=0,
	)
	items = [_row(row) for row in rows]
	# Python's sort is stable, so the SQL order above survives as the tiebreak
	# between two Prototypes whose newest file carries the same second.
	items.sort(key=lambda item: item["modified"], reverse=True)
	return items


@frappe.whitelist(allow_guest=True)
def public_prototypes() -> list[dict]:
	"""Every public Prototype on the site, newest first. The /feed listing.

	`allow_guest`, because /feed is the front door: a signed-out visitor at `/`
	is sent there (`sketch/www/sketch.py`) and reads it with no session and no
	role. The page is a route of the SPA now, not a server-rendered template,
	so this call is the listing and there is no second copy of it in `www`.

	No page size. The old template capped the page at 24 rows and printed a
	line saying so; the page prints no count line any more, so a cap here would
	be a silent truncation. The whole set is walked to sort it in any case.

	This is the one read in this file that drops the permission check, and the
	filter is why. `list_prototypes` above keeps `get_list` because a role can
	express "the rows you own": `Sketch User` carries `if_owner`. No role
	expresses "the rows anybody made public", and the caller here is usually a
	Guest, who holds no role at all, so `get_list` would answer an empty list
	for every visitor the feed exists for.

	`is_public` is therefore the whole permission check. It is set here, it is
	never taken from the caller, and it is the only filter, so a private
	Prototype cannot reach the page. The field list carries nothing a private
	Prototype could leak through either: no file content, no token, no email.

	The order is the tree's own stamp, the same value `list_prototypes` sorts
	on and the same one each row prints as "Updated ...". Ordering on the
	document's `modified` would send a Prototype to the head of the feed for
	the flip of a switch, which is review 5.7 with a bigger audience. SQL
	cannot see an mtime, so the sort happens here. The cost is one stat per
	file of every public Prototype on the site, and the caller cannot avoid it
	by asking for fewer rows: the order needs the whole set.

	A row whose owner has no username is left out. `/u/<username>/<slug>` is
	the only address a Prototype has (`sketch/viewer.py`), so a row without one
	has no link the feed could print.
	"""
	rows = frappe.get_all(
		"Sketch Prototype",
		filters={"is_public": 1},
		fields=["name", "title", "slug", "owner", "creation"],
		order_by="creation desc",
		limit_page_length=0,
	)
	authors = _authors([row.owner for row in rows])
	items = [_public_row(row, authors[row.owner]) for row in rows if authors.get(row.owner)]
	# Python's sort is stable, so the SQL order above survives as the tiebreak
	# between two Prototypes whose newest file carries the same second.
	items.sort(key=lambda item: item["modified"], reverse=True)
	return items


def _authors(owners: list[str]) -> dict[str, dict]:
	"""The username, name and picture of each owner, in one read.

	One query for the whole feed, not one per row. A user with no username is
	absent from the answer rather than present with an empty value, so the
	caller has one thing to test: `/u/<username>/<slug>` is the only address a
	Prototype has, so a row without one has no link the feed could print.

	The three fields are what one card draws: the handle, and the Avatar's
	image with the name behind it for the initials. Nothing else about a User
	is read here, because this answer is public.
	"""
	if not owners:
		return {}

	rows = frappe.get_all(
		"User",
		filters={"name": ("in", sorted(set(owners)))},
		fields=["name", "username", "full_name", "user_image"],
		limit_page_length=0,
	)
	return {
		row.name: {
			"username": row.username,
			"full_name": row.full_name or row.username,
			"user_image": row.user_image or "",
		}
		for row in rows
		if row.username
	}


def _public_row(row, author: dict) -> dict:
	"""One feed item.

	`_row` cannot serve here. Its username is the session user's, and on a
	feed of every owner's work that addresses the wrong Viewer.

	`author` carries the face beside the username. A feed of strangers' work
	that prints a bare handle reads as a list of paths, so the card draws the
	same Avatar the top bar draws, from the same `User.user_image` field.
	`full_name` is the Avatar's fallback: it makes the initials when a user has
	no picture.

	`file_count` is the number the card's own actions read: Export is disabled
	on an empty tree, the way it is in the gallery.

	No `pin` and no `is_public`: every row on the feed is public, and the Pin
	is a build detail that told a reader nothing they could act on
	(review 5.8).
	"""
	username = author["username"]
	files = prototype_files.list_files(row.name)
	count = len(files)
	# Falls back to `creation`, never to `modified`, for the reason
	# `public_prototypes` gives: `modified` moves on a visibility toggle, and
	# the toggle is what puts a Prototype on this page.
	updated_at, rev = _tree_stamp(row.name, files)
	updated_at = updated_at or str(row.creation or "")
	return {
		"title": row.title,
		"username": username,
		"full_name": author["full_name"],
		"user_image": author["user_image"],
		"slug": row.slug,
		"file_count": count,
		"viewer_path": f"/u/{username}/{row.slug}",
		"public_url": f"{_public_base()}/u/{username}/{row.slug}",
		# The same pictures the gallery card draws. The feed prints the light
		# one: these pages carry no theme control and core's token layer only
		# turns dark on `[data-theme="dark"]`, which nothing here sets.
		"thumbnail": _card_image(row.name, username, row.slug, rev, row.owner),
		"description": f"{count} {'file' if count == 1 else 'files'}",
		"modified": updated_at,
		"updated": pretty_date(updated_at) if updated_at else "",
	}


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
	"""The current revision of one Prototype's tree, for a caller with a session.

	`resolve_owned` is the permission check, so only the owner may read it.

	The Viewer does not call this. Its document is sandboxed into an opaque
	origin, which sends no cookie, so it calls `signed_revision` below. This
	stays for the Sketch UI, which is a plain same-origin page with a session.
	"""
	doc = prototype.resolve_owned(slug)
	return {"rev": prototype_files.revision(doc.name)}


@frappe.whitelist(allow_guest=True, methods=["GET"])
def signed_revision(name: str, exp: str = "", sig: str = "") -> dict:
	"""The current revision of one Prototype's tree, for the Viewer's poller.

	The Viewer serves every Prototype from an opaque origin (`sketch/viewer.py`
	SANDBOX), because a Prototype is JavaScript one user wrote and a fork puts
	a stranger's code inside the reader's own tree. An opaque origin sends no
	session cookie, so `prototype_revision` above cannot answer the owner's own
	tab. This one takes the short-lived signature the Viewer minted into the
	page instead, and `allow_guest` follows from that: there is no session to
	read.

	The signature is not a session. It authenticates this read and nothing
	else:

	- the scope is REVISION, which is inside the HMAC message, so the same
	  string opens no Viewer document (`sketch/signature.py`);
	- it covers one Prototype hash id, so it cannot be replayed against
	  another Prototype;
	- it expires;
	- the answer is the revision string and nothing else. No title, no owner,
	  no file.

	A bad or expired signature answers 404, which is the Viewer's own answer
	to the same question. A named error would confirm which hash ids exist.

	`Access-Control-Allow-Origin: *` because the caller's origin is "null" and
	matches no allowlist. No `Access-Control-Allow-Credentials`: the signature
	is the whole authentication, and a cookie must never widen it.
	"""
	frappe.local.response_headers["Access-Control-Allow-Origin"] = "*"
	if not signature.verify(name, exp, sig, signature.REVISION):
		raise frappe.DoesNotExistError

	return {"rev": prototype_files.revision(name)}


@frappe.whitelist(allow_guest=True)
def list_prototype_files(slug: str, username: str = "") -> list[dict]:
	"""Every file in one Prototype's tree, as {"path", "size"}, sorted by path.

	The Files browser opens on this. It is a stat walk, so it stays cheap for a
	tree of any size, and it carries no source: a browser reads one file at a
	time, through `read_prototype_file`.

	`prototype.resolve_readable` is the permission check. Without `username` it
	is the owner's own tree, which is the gallery's read and is unchanged. With
	one it is the Prototype at `/u/<username>/<slug>`, and `is_public` is the
	check. `allow_guest` follows from that: /feed is read with no session, and
	the card there carries this browser.
	"""
	doc = prototype.resolve_readable(slug, username)
	return prototype_files.list_files(doc.name)


@frappe.whitelist(allow_guest=True)
def read_prototype_file(slug: str, path: str, username: str = "") -> dict:
	"""One file of a Prototype, as source the browser prints.

	`prototype.resolve_readable` is the permission check, and
	`prototype_files.safe_join` is the path guard. The client names the file,
	so both have to run: the first says whose tree it is, the second says the
	path stays inside it.

	Answers {"path", "size", "content", "truncated"}. Raises for a missing
	file, and for a file that is not UTF-8 text.
	"""
	doc = prototype.resolve_readable(slug, username)
	return prototype_files.read_text(doc.name, path)


@frappe.whitelist(allow_guest=True)
def export_prototype(slug: str, username: str = "") -> None:
	"""Send the whole tree as one zip, named after the Prototype.

	`prototype.resolve_readable` is the permission check. A public Prototype is
	public to take as well as to look at: the feed card offers this beside its
	Files browser, so what a stranger can read one file at a time they can also
	take in one file.

	The answer is a file, not a value, so this fills the download slots
	`frappe.utils.response.as_raw` reads and returns nothing. The mimetype
	comes off the filename.
	"""
	doc = prototype.resolve_readable(slug, username)
	frappe.response["filename"] = f"{doc.slug}.zip"
	frappe.response["filecontent"] = prototype_files.zip_bytes(doc.name, doc.slug)
	frappe.response["type"] = "download"


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


@frappe.whitelist(methods=["POST"])
def fork_prototype(username: str, slug: str) -> dict:
	"""Copy somebody's public Prototype into the caller's own gallery.

	The one write on /feed. A reader who likes what an agent wrote there wants
	to keep going from it, and until now the only route was Export, unzip, and
	ask their own agent to paste the tree back in.

	`prototype.resolve_readable` is the permission check, and `username` is
	required here: a fork is always of a card on the feed, and `is_public` is
	what that check reads. No `allow_guest`, unlike the reads beside it. A fork
	makes a document owned by the caller, so the caller has to be somebody.

	The copy is the tree and the Pin, and nothing else.

	- The title is the source's. Two people may hold the same title, and the
	  new slug is freed per owner (`prototype._free_slug`), so the fork gets
	  its own address under the caller's own username.
	- The Pin is the source's, not `newest_pin()`. The tree was written against
	  that Runtime, and a fork that renders differently from the card it was
	  taken from is not a copy.
	- `is_public` is 0. Publishing is the new owner's decision, never inherited.
	- No version row and no thumbnail. A Prototype from a Recipe carries
	  neither either, and the first `check` writes both.

	Answers the new gallery row, so the caller can draw it without a re-read.
	"""
	source = prototype.resolve_readable(slug, (username or "").strip())
	tree = prototype_files.read_tree(source.name)

	doc = prototype.create(source.title)
	if source.pin and source.pin != doc.pin:
		doc.pin = source.pin
		doc.save()

	_copy_tree(doc.name, tree)
	return _row(doc.as_dict())


def _copy_tree(name: str, tree: dict[str, str]) -> None:
	"""Write a whole source tree into an empty Prototype, in batches.

	`prototype_files.MAX_BATCH_FILES` bounds the work one MCP request buys. A
	fork is not an MCP request: the source tree already passed every quota,
	and a tree may hold `MAX_TREE_FILES` (500) files, five times the batch
	cap. Without the slicing here a Prototype over 100 files could be read and
	exported but never forked.

	The per-file and whole-tree quotas still run, once per batch, because
	every batch goes through `write_files` as usual.
	"""
	items = sorted(tree.items())
	step = prototype_files.MAX_BATCH_FILES
	for start in range(0, len(items), step):
		prototype_files.write_files(
			name, [{"path": path, "content": content} for path, content in items[start : start + step]]
		)


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
def refresh_preview(slug: str) -> dict:
	"""Re-take this Prototype's card pictures now, and answer with the new row.

	The card is normally taken during the `check` the agent runs at the end of
	a request, and re-taken in the background when it goes stale
	(`_card_image`). This is the manual door for the two cases neither of those
	covers: a Prototype whose agent has not checked it since the pictures
	existed, and one whose background refresh could not run because checkd or
	the worker was down.

	It runs the browser inline rather than queueing, which is the point: the
	user asked for this one and is watching the card. It costs about two
	seconds, and it fails loudly, because a queued job that dies leaves the
	same stale picture with nothing said.

	One run per account at a time (`checkd.claim_slot`). The browser runs on
	the web worker, so without the claim one account fires this from many tabs
	and holds every worker on the site for the checkd deadline (review 3.6).
	The claim is taken after `resolve_owned`, so a slug the caller does not own
	costs no cooldown. `checkd.run` gives it back; the `finally` here covers
	the path where `capture` finds no tree and opens no browser at all.

	The reply is the whole row, so the caller can draw the new picture without
	a second read. Its URL is new even when no file changed: the stamp is the
	capture's, not the tree's (`sketch/thumbnails.py` `store`).
	"""
	doc = prototype.resolve_owned(slug)
	checkd.claim_slot()
	try:
		written = thumbnails.capture(doc.name)
	finally:
		checkd.release_slot()

	if not written:
		# `capture` returns nothing for a tree that did not mount, and leaves
		# the last good picture alone. Say which of the two happened, because
		# "nothing changed" and "your code is broken" ask for different next
		# steps from the user.
		frappe.throw(
			frappe._("The prototype did not render, so there is no new picture. Run check to see why.")
		)

	return _row(doc.as_dict())


@frappe.whitelist(methods=["POST"])
def delete_prototype(slug: str) -> dict:
	"""Delete a Prototype. `on_trash` removes its directory."""
	doc = prototype.resolve_owned(slug)
	name = doc.name
	frappe.delete_doc("Sketch Prototype", name)
	return {"name": name}


@frappe.whitelist(methods=["POST"])
def get_agent_token() -> dict:
	"""The user's token, the MCP endpoint, and when an agent last used it.

	POST only, so it takes a CSRF token. A GET answers any same-origin
	document that carries the session cookie, and the Viewer serves
	attacker-authored JavaScript on this origin. The CSP sandbox in
	`sketch/viewer.py` is the fix; this closes the sharpest exit as well
	(review 3.2). The Settings screen posts (`frontend/src/store.ts`).

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
