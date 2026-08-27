# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The Viewer page_renderer on /u/<username>/<slug>.

There is no files endpoint. This renderer is the only door, and it carries the
Prototype source tree inside the page.

It reads the pinned Runtime's own viewer.html from disk and substitutes one
slot (spec 6.1). It does not rebuild the document from manifest.json: that
would make one document serve every Pin and re-derive the import map the build
already wrote correctly.

It decides "may you see this" and nothing else (spec 6.5). Every fact about the
tree is the Viewer's to report, because `check` reads the Viewer.
"""

import json
import os

import frappe
from frappe.utils import escape_html
from frappe.website.page_renderers.base_renderer import BaseRenderer

from sketch import prototype, prototype_files, signature

#: The literal build.sh stamps into each per-Pin viewer.html (contract 4).
SLOT = "SKETCH_DATA"

#: Spec 6.4. Frappe sets neither, so without them any site could embed a
#: Prototype, and a browser could serve a stale tree.
HEADERS = {
	"Cache-Control": "no-store",
	"Content-Security-Policy": "frame-ancestors 'self'",
	"Content-Type": "text/html; charset=utf-8",
}

THEMES = ("light", "dark")


def to_json(payload) -> str:
	"""JSON for an inline <script> block.

	Escapes "<" as \\u003c, and ">" and "&" with it. Every Vue SFC with a script
	block ends with "</script>", which closes the JSON block early and breaks
	the Viewer on the most ordinary file a Prototype can hold. frappe.as_json
	does not do this (trap 1).
	"""
	text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
	return text.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")


def runtime_html_path(pin: str) -> str | None:
	"""Absolute path to the pinned Runtime's viewer.html.

	None when pin is empty or steps outside the runtimes folder.
	"""
	if not pin or "/" in pin or "\\" in pin or pin.startswith("."):
		return None

	return frappe.get_app_path("sketch", "public", "runtimes", pin, "viewer.html")


def url_theme() -> str | None:
	"""The theme URL parameter, when it is light or dark.

	Anything else, including "system", is None. The Viewer then resolves the
	theme client side, from localStorage and then the browser preference
	(spec 12). The renderer never writes localStorage and never sends "system".
	"""
	value = (frappe.form_dict.get("theme") or "").strip().lower()
	return value if value in THEMES else None


class SketchViewerRenderer(BaseRenderer):
	"""Serves a Prototype at /u/<username>/<slug>.

	can_render() runs the auth ladder (spec 6.3):

	    path does not resolve to a Prototype  -> False, so Frappe answers 404
	    is_public                             -> serve
	    caller is the owner                   -> serve
	    valid unexpired signature             -> serve
	    otherwise                             -> False, so Frappe answers 404

	A bad or expired signature is not an error. It falls through, so a stale
	link to a public Prototype still works and a private one still answers 404.
	The answer is always 404, never 403: a 403 confirms the URL exists.
	"""

	def __init__(self, path=None, http_status_code=None):
		super().__init__(path=path, http_status_code=http_status_code)
		self.doc = None
		self.is_owner = False

	def can_render(self) -> bool:
		"""True only when this path is a Prototype the caller may see."""
		parts = self.path.split("/")
		if len(parts) != 3 or parts[0] != "u" or not parts[1] or not parts[2]:
			return False

		self.doc = prototype.resolve_public(parts[1], parts[2])
		if not self.doc:
			return False

		self.is_owner = frappe.session.user == self.doc.owner
		if self.doc.is_public or self.is_owner:
			return True

		return signature.verify(self.doc.name, frappe.form_dict.get("exp"), frappe.form_dict.get("sig"))

	def render(self):
		"""The pinned Runtime document, with the tree in the data slot."""
		path = runtime_html_path(self.doc.pin)
		if not path or not os.path.isfile(path):
			# Trap 11. Never a blank iframe.
			return self.build_response(missing_runtime_html(self.doc.pin), 500, dict(HEADERS))

		with open(path, encoding="utf-8") as handle:
			document = handle.read()

		count = document.count(SLOT)
		if count != 1:
			# Contract 4. One occurrence, or the substitution lands somewhere
			# else and the page breaks in a way that is hard to read.
			return self.build_response(bad_slot_html(self.doc.pin, count), 500, dict(HEADERS))

		return self.build_response(document.replace(SLOT, to_json(self.payload()), 1), 200, dict(HEADERS))

	def payload(self) -> dict:
		"""The data slot contents (contract 4)."""
		return {
			"files": prototype_files.read_tree(self.doc.name),
			"name": self.doc.name,
			"title": self.doc.title,
			"slug": self.doc.slug,
			"pin": self.doc.pin,
			"is_public": bool(self.doc.is_public),
			"is_owner": self.is_owner,
			"theme": url_theme(),
		}


def missing_runtime_html(pin: str) -> str:
	"""The readable 500 body for a Pin with no folder on disk (spec 5.12)."""
	return _error_html(
		"Runtime not found",
		f"This prototype is pinned to Runtime {escape_html(pin or '(empty)')}, "
		"which is not built on this server.",
		"Build the Runtime, or repin the prototype to a version that is on disk.",
	)


def bad_slot_html(pin: str, count: int) -> str:
	"""The readable 500 body for a Runtime document with a broken data slot."""
	return _error_html(
		"Runtime data slot is broken",
		f"viewer.html for Runtime {escape_html(pin or '(empty)')} holds the "
		f"data slot {count} times. It must hold it once.",
		"Rebuild the Runtime.",
	)


def _error_html(title: str, detail: str, action: str) -> str:
	"""A plain page a person can read. No Runtime, so no Runtime assets."""
	return (
		"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
		"<meta name='viewport' content='width=device-width, initial-scale=1'>"
		f"<title>{title}</title></head>"
		'<body style="margin:0;padding:2rem;font:14px/1.6 ui-sans-serif,system-ui,sans-serif">'
		f"<h1 style='font-size:1rem;margin:0 0 .5rem'>{title}</h1>"
		f"<p style='margin:0 0 .5rem'>{detail}</p>"
		f"<p style='margin:0;color:#666'>{action}</p>"
		"</body></html>"
	)
