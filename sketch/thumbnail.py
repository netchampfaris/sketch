# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The card image page_renderer on /t/<username>/<slug>/<theme>.png.

The one door to a thumbnail. `sketch/thumbnails.py` writes them under
`private/files`, which no web request can reach, so this renderer is what turns
a private file into an `<img src>` for the two callers that may see it.

It runs the Viewer's access ladder minus the signature (spec 6.3):

    path is not a thumbnail path            -> False, so Frappe answers 404
    is_public                               -> serve
    caller is the owner                     -> serve
    otherwise                               -> False, so Frappe answers 404

No signature step. A signature exists so `check` can open a private Prototype
as a Guest, and nothing headless asks for a card image.

A Prototype with no picture yet answers 404, not a placeholder image. The card
draws the placeholder, in its own markup and its own theme, and a 404 is how it
learns to. `check` has not run on a brand new Prototype, so this is the
ordinary case and not an error.
"""

import frappe
from frappe.website.page_renderers.base_renderer import BaseRenderer

from sketch import prototype, thumbnails

#: A year. The URL carries the capture stamp (`sketch/thumbnails.py` `stamp`),
#: so the bytes at one URL never change and the browser never has to ask again.
#: Every capture writes a new stamp, which is a new URL.
IMMUTABLE = "max-age=31536000, immutable"


class SketchThumbnailRenderer(BaseRenderer):
	"""Serves one theme's card image of one Prototype."""

	def __init__(self, path=None, http_status_code=None):
		super().__init__(path=path, http_status_code=http_status_code)
		self.doc = None
		self.theme = ""

	def can_render(self) -> bool:
		"""True only when this path is a picture the caller may see."""
		parts = self.path.split("/")
		if len(parts) != 4 or parts[0] != "t" or not parts[1] or not parts[2]:
			return False

		leaf = parts[3]
		if not leaf.endswith(".png"):
			return False

		self.theme = leaf[: -len(".png")]
		if self.theme not in thumbnails.THEMES:
			return False

		self.doc = prototype.resolve_public(parts[1], parts[2])
		if not self.doc:
			return False

		return bool(self.doc.is_public) or frappe.session.user == self.doc.owner

	def render(self):
		"""The PNG, or a 404 for a Prototype that has not been captured yet."""
		data = thumbnails.read(self.doc.name, self.theme)
		if data is None:
			# An empty body, because the caller is an <img>. A missing picture
			# is not a page and there is nobody to read a sentence about it.
			return self.build_response(b"", 404, {"Cache-Control": "no-store"})

		return self.build_response(data, 200, {"Cache-Control": self.cache_control()})

	def cache_control(self) -> str:
		"""How long this picture may be held, and by whom.

		`private` for a Prototype only its owner may see: a shared cache that
		stored it would hand it to the next caller without the ladder above
		running. `public` for one anybody may see, so the feed is cheap for
		everyone.

		Either way it is only cacheable with a stamp in the URL. Without one
		the same URL would answer with different bytes after a capture, and a
		year-long cache would pin the first ones.
		"""
		if not frappe.form_dict.get("rev"):
			return "no-cache"

		scope = "public" if self.doc.is_public else "private"
		return f"{scope}, {IMMUTABLE}"


def url(username: str, slug: str, theme: str, stamp: str) -> str:
	"""The path a card puts in `src`. Relative, so it works on any hostname.

	`stamp` is `thumbnails.stamp()`, which is new on every capture. It is a
	cache key and nothing else: the renderer never reads it to pick a file, so
	a stale or absent stamp serves the current picture rather than an old one.
	"""
	suffix = f"?rev={stamp}" if stamp else ""
	return f"/t/{username}/{slug}/{theme}.png{suffix}"
