# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The Runtime file page_renderer on /sketch-runtime/<pin>/<file>.

It serves the same bytes as /assets/sketch/runtimes/<pin>/<file>, and exists
for one header: `Access-Control-Allow-Origin`.

Why that is needed
------------------

`sketch/viewer.py` sends a sandboxed Prototype into an opaque origin. In an
opaque origin every http(s) URL is cross-origin, including a URL on the site
the document came from. Two of the Runtime's own requests are made in CORS
mode and so need the header:

- the module script `<script type="module" src=".../boot.js">`, and every
  module it imports through the import map (vue, frappe-ui, the compiler),
- the `@font-face` request for Inter.var.woff2 inside frappe-ui.css.

/assets is not served by Frappe's WSGI app. It is `SharedDataMiddleware` in
development and nginx in production, so no app hook can add a header to it.
Measured in Chromium: without this route a sandboxed Viewer prints

    Access to script at '.../boot.js' from origin 'null' has been blocked by
    CORS policy: No 'Access-Control-Allow-Origin' header is present

and window.__sketch is never defined, so every check times out and every
public visitor sees a blank page.

Why it is not a new exposure
----------------------------

Every file it can reach is already public at /assets. It adds no path the web
could not read, and it reads nothing outside the pinned Runtime folder.
"""

import os

import frappe
from frappe.website.page_renderers.base_renderer import BaseRenderer

#: The first path segment this renderer answers.
PREFIX = "sketch-runtime"

#: A year. A Pin's folder never changes: a rebuild is a new Pin, which is a new
#: URL. The same rule /assets gets from nginx, so a sandboxed viewer fetches
#: the Runtime once and not on every page load.
IMMUTABLE = "public, max-age=31536000, immutable"

#: The file kinds a Runtime folder holds, and the type each is served with.
#: Anything else answers 404, so viewer.html is never served raw with its data
#: slot unfilled.
TYPES = {
	".css": "text/css; charset=utf-8",
	".js": "text/javascript; charset=utf-8",
	".json": "application/json; charset=utf-8",
	".png": "image/png",
	".svg": "image/svg+xml",
	".woff": "font/woff",
	".woff2": "font/woff2",
}


def runtimes_root() -> str:
	"""The folder every Runtime Pin lives under."""
	return frappe.get_app_path("sketch", "public", "runtimes")


def asset_path(pin: str, filename: str) -> str | None:
	"""Absolute path to one file of one Pin, or None when it is not one.

	The name is checked, and then the resolved path is checked against the
	root as well. The first stops the ordinary traversal, the second stops one
	through a symlink someone drops into the folder.
	"""
	for part in (pin, filename):
		# A NUL is rejected here with the separators, and not left to the
		# resolver. os.path.realpath raises ValueError on an embedded NUL, and
		# this route answers an unauthenticated request, so a name that holds
		# one would be a 500 for anybody who asks for it.
		if not part or part.startswith(".") or "/" in part or "\\" in part or "\0" in part:
			return None

	if os.path.splitext(filename)[1].lower() not in TYPES:
		return None

	root = os.path.realpath(runtimes_root())
	path = os.path.realpath(os.path.join(root, pin, filename))
	if not path.startswith(root + os.sep) or not os.path.isfile(path):
		return None

	return path


def url_prefix(pin: str) -> str:
	"""The path this renderer answers for one Pin, with a trailing slash.

	`sketch/viewer.py` rewrites the Runtime's own absolute URLs onto it.
	"""
	return f"/{PREFIX}/{pin}/"


class SketchRuntimeRenderer(BaseRenderer):
	"""Serves one file of one pinned Runtime, readable from an opaque origin."""

	def __init__(self, path=None, http_status_code=None):
		super().__init__(path=path, http_status_code=http_status_code)
		self.file_path = None
		self.content_type = ""

	def can_render(self) -> bool:
		"""True only when this path is a file inside a built Runtime."""
		parts = self.path.split("/")
		if len(parts) != 3 or parts[0] != PREFIX:
			return False

		self.file_path = asset_path(parts[1], parts[2])
		if not self.file_path:
			return False

		self.content_type = TYPES[os.path.splitext(parts[2])[1].lower()]
		return True

	def render(self):
		"""The file's bytes, with the header the opaque origin needs."""
		with open(self.file_path, "rb") as handle:
			data = handle.read()

		return self.build_response(
			data,
			200,
			{
				# "*" and no Allow-Credentials: the answer is the same public
				# build for everybody, and it must never be varied by a cookie.
				"Access-Control-Allow-Origin": "*",
				"Cache-Control": IMMUTABLE,
				"Content-Type": self.content_type,
				"X-Content-Type-Options": "nosniff",
			},
		)
