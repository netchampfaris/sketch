# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""Prototype lookup, create, slug and pin."""

import os
import re

import frappe
from frappe.utils import get_url

RUNTIMES_PATH = ("public", "runtimes")
SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def slugify(title: str) -> str:
	"""Lowercase, [a-z0-9-], no doubled or trailing hyphen. Raises if empty."""
	slug = SLUG_STRIP.sub("-", (title or "").strip().lower()).strip("-")
	if not slug:
		frappe.throw(frappe._("Title must contain a letter or a number"), frappe.ValidationError)

	return slug


def newest_pin() -> str:
	"""The newest version folder name under sketch/public/runtimes/.

	Raises frappe.ValidationError when none is built.
	"""
	root = frappe.get_app_path("sketch", *RUNTIMES_PATH)
	versions = []
	if os.path.isdir(root):
		versions = [entry for entry in os.listdir(root) if os.path.isdir(os.path.join(root, entry))]

	if not versions:
		frappe.throw(
			frappe._("No Runtime is built. Run the Runtime build before creating a Prototype."),
			frappe.ValidationError,
		)

	return max(versions, key=_version_key)


def _version_key(version: str):
	"""Sort key for a version folder. Falls back to the plain string."""
	from packaging.version import InvalidVersion, Version

	try:
		return (1, Version(version))
	except InvalidVersion:
		return (0, version)


def create(title: str) -> "frappe.model.document.Document":
	"""Create a Sketch Prototype for the session user.

	Derives a unique slug from title, sets pin to newest_pin(). Does not create
	the directory.
	"""
	doc = frappe.new_doc("Sketch Prototype")
	doc.title = (title or "").strip()
	doc.slug = _free_slug(slugify(title), frappe.session.user)
	doc.pin = newest_pin()
	doc.is_public = 0
	doc.insert()
	return doc


def _free_slug(base: str, user: str) -> str:
	"""The first slug this user does not already hold. Adds -2, -3, and so on."""
	slug = base
	suffix = 1
	while frappe.db.exists("Sketch Prototype", {"owner": user, "slug": slug}):
		suffix += 1
		slug = f"{base}-{suffix}"

	return slug


def resolve_public(username: str, slug: str):
	"""Look a Prototype up by User.username and slug with ignore_permissions.

	Returns the Document, or None. The Viewer's only lookup. Never throws for a
	missing row.
	"""
	if not username or not slug:
		return None

	user = frappe.db.get_value("User", {"username": username}, "name")
	if not user:
		return None

	name = frappe.db.get_value("Sketch Prototype", {"owner": user, "slug": slug}, "name")
	if not name:
		return None

	return frappe.get_doc("Sketch Prototype", name)


def resolve_owned(slug: str):
	"""Look a Prototype up by slug for frappe.session.user, permission-checked.

	Raises frappe.DoesNotExistError when there is no such Prototype for this
	user. Every MCP tool and SPA method resolves this way.
	"""
	user = frappe.session.user
	name = frappe.db.get_value("Sketch Prototype", {"owner": user, "slug": slug}, "name")
	if not name:
		raise frappe.DoesNotExistError(frappe._("No prototype with slug {0}").format(slug))

	doc = frappe.get_doc("Sketch Prototype", name)
	doc.check_permission("read")
	return doc


def public_url(doc) -> str:
	"""The absolute https://sketch.netchamp.dev/u/<username>/<slug> URL."""
	username = frappe.db.get_value("User", doc.owner, "username")
	# get_url() appends webserver_port in developer mode, which a shared link
	# must never carry. site_config host_name is the public host.
	base = (frappe.local.conf.host_name or frappe.local.conf.hostname or get_url()).rstrip("/")
	if not base.startswith(("http://", "https://")):
		base = "https://" + base

	return f"{base}/u/{username}/{doc.slug}"
