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

import frappe
from frappe.utils import pretty_date

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

#: Recipe order in the picker. Blank first, because it is the fallback.
RECIPE_ORDER = list(RECIPES)

#: The one MCP endpoint an agent connects to (spec 8).
MCP_PATH = "/mcp"

#: Used when sketch/recipes/blank/ is not vendored yet. It keeps creation
#: working, and every other recipe still comes from disk.
BLANK_TREE = {
	"src/App.vue": """<script setup lang="ts">
import { DesktopShell, Sidebar, SidebarHeader, SidebarItem, SidebarSection } from 'frappe-ui'
</script>

<template>
  <div class="h-screen w-full bg-surface-base text-ink-gray-9">
    <DesktopShell>
      <template #sidebar>
        <Sidebar width="14rem" class="border-r">
          <SidebarHeader title="Blank" subtitle="Prototype" />
          <div class="min-h-0 flex-1 overflow-y-auto px-2 pt-0.5 pb-10">
            <SidebarSection>
              <SidebarItem to="/" icon="lucide-home" label="Home" />
            </SidebarSection>
          </div>
        </Sidebar>
      </template>
      <router-view />
    </DesktopShell>
  </div>
</template>
""",
	"src/router.ts": """// The Runtime creates the router in hash mode. A Prototype exports routes only.
import type { RouteRecordRaw } from 'vue-router'
import Home from './pages/Home.vue'

const routes: RouteRecordRaw[] = [{ path: '/', name: 'Home', component: Home }]

export default routes
""",
	"src/pages/Home.vue": """<script setup lang="ts">
import { Button, PageHeader } from 'frappe-ui'
</script>

<template>
  <PageHeader>
    <h1 class="text-lg font-semibold text-ink-gray-8">Home</h1>
  </PageHeader>
  <div class="px-5 pt-6 pb-10">
    <p class="text-p-base text-ink-gray-7">
      This prototype is empty. Ask your agent to build something here.
    </p>
    <Button class="mt-4" variant="solid" theme="gray" label="Primary action" />
  </div>
</template>
""",
}


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

	`file_count` and the description come off disk, because no field stores
	them and a stored copy drifts (spec 2).
	"""
	name = doc_or_dict.get("name")
	slug = doc_or_dict.get("slug")
	pin = doc_or_dict.get("pin")
	count = len(prototype_files.list_files(name))
	username = _username()
	return {
		"name": name,
		"title": doc_or_dict.get("title"),
		"slug": slug,
		"pin": pin,
		"is_public": bool(doc_or_dict.get("is_public")),
		"file_count": count,
		"description": f"{count} {'file' if count == 1 else 'files'} · frappe-ui {pin}",
		"modified": str(doc_or_dict.get("modified") or ""),
		"updated": pretty_date(doc_or_dict.get("modified")) if doc_or_dict.get("modified") else "",
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
	return {
		"user": user,
		"username": username or "",
		"full_name": full_name or user,
		"user_image": user_image or "",
		"has_token": bool(frappe.db.exists("Sketch Token", {"user": user})),
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
	"""
	rows = frappe.get_list(
		"Sketch Prototype",
		filters={"owner": frappe.session.user},
		fields=["name", "title", "slug", "pin", "is_public", "modified"],
		order_by="modified desc",
		limit_page_length=0,
	)
	return [_row(row) for row in rows]


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
	always works: it falls back to a built-in tree.
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
				"available": slug in on_disk or slug == "blank",
			}
		)

	return recipes


@frappe.whitelist(methods=["POST"])
def create_prototype(title: str, recipe: str = "blank") -> dict:
	"""Create a Prototype and write the chosen Recipe into its directory."""
	recipe = (recipe or "blank").strip().lower()
	if recipe not in RECIPES and recipe not in _recipe_tree_slugs():
		frappe.throw(frappe._("No recipe named {0}").format(recipe), frappe.ValidationError)

	files = _recipe_tree(recipe)
	if not files and recipe == "blank":
		files = [{"path": path, "content": content} for path, content in BLANK_TREE.items()]

	doc = prototype.create(title)
	if files:
		prototype_files.write_files(doc.name, files)

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
	"""The user's token and the MCP endpoint. One user, one token."""
	return {
		"token": sketch_token.get_or_create(frappe.session.user),
		"endpoint": _public_base() + MCP_PATH,
	}


@frappe.whitelist(methods=["POST"])
def regenerate_agent_token() -> dict:
	"""Write a new token over the old one. A write, never a delete."""
	return {
		"token": sketch_token.regenerate(frappe.session.user),
		"endpoint": _public_base() + MCP_PATH,
	}
