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

from sketch import prototype, prototype_files, runtime_assets, signature

#: The literal build.sh stamps into each per-Pin viewer.html (contract 4).
SLOT = "SKETCH_DATA"

#: Spec 6.4. Frappe sets neither, so without them any site could embed a
#: Prototype, and a browser could serve a stale tree.
HEADERS = {
	"Cache-Control": "no-store",
	"Content-Security-Policy": "frame-ancestors 'self'",
	"Content-Type": "text/html; charset=utf-8",
}

#: The sandbox every caller gets, prefixed to the CSP above. It drops the
#: document into an opaque origin: no cookies, no same-origin read, no access
#: to the SPA csrf_token. A Prototype is JavaScript one user wrote, and without
#: this it runs on the app origin with the reader's session, which is enough to
#: read that session's agent token.
#:
#: The three tokens are what the shipped code needs, measured in Chromium:
#:
#: - allow-scripts: boot.js compiles each file through `new Function`.
#: - allow-forms: without it the form submission algorithm returns before the
#:   submit event, so a `<form @submit.prevent>` handler never runs.
#: - allow-popups: without it a `target="_blank"` link is blocked. The popup
#:   inherits the sandbox, so it opens in an opaque origin too.
#:
#: allow-same-origin must never join them. It hands the app origin back and
#: undoes the whole control.
SANDBOX = "sandbox allow-scripts allow-forms allow-popups"

#: The prefix build.sh stamps into every absolute URL in viewer.html, up to but
#: not including the Pin. `sandboxed_document` moves them off it.
ASSET_PREFIX = "/assets/sketch/runtimes/"

#: How long the owner's live reload credential lasts.
#:
#: The page holds it for as long as the tab is open, and a working session runs
#: for hours, so the 60 second `check` signature would leave the tab dead after
#: a minute. It buys one thing: the revision number of the Prototype the same
#: page already carries in full (`sketch.api.signed_revision`).
LIVE_TTL_SECONDS = 12 * 60 * 60

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

	def response_headers(self) -> dict:
		"""The response headers for this caller. can_render() ran first.

		Not `headers`: BaseRenderer.__init__ sets `self.headers = None`, and an
		instance attribute shadows a method of the same name.

		Every caller gets the sandbox, the owner as well. Ownership says who
		holds the tree, never who wrote the code in it:
		`sketch.api.fork_prototype` copies another user's public tree, word for
		word, into a Prototype the caller owns. An owner exemption therefore
		hands a stranger's JavaScript the app origin and the reader's session,
		which is the whole attack the sandbox exists to stop. One rule for
		every caller is one rule to check.

		The owner keeps live reload. The poller authenticates with the
		signature `payload` mints, not with the cookie an opaque origin will
		not send (`sketch.api.signed_revision`).
		"""
		headers = dict(HEADERS)
		headers["Content-Security-Policy"] = f"{SANDBOX}; {HEADERS['Content-Security-Policy']}"

		return headers

	def sandboxed_document(self, document: str) -> str:
		"""The Runtime document with its own URLs moved off /assets.

		An opaque origin makes every http URL cross-origin, and a module script
		and an @font-face request are both fetched in CORS mode, so boot.js and
		Inter both need Access-Control-Allow-Origin. /assets is
		SharedDataMiddleware in development and nginx in production, so no hook
		of this app can put that header on it. `sketch/runtime_assets.py`
		serves the same bytes with it.

		Every caller reads the Runtime this way, because every caller is
		sandboxed (`response_headers`).
		"""
		return document.replace(
			f"{ASSET_PREFIX}{self.doc.pin}/", runtime_assets.url_prefix(self.doc.pin)
		)

	def render(self):
		"""The pinned Runtime document, with the tree in the data slot."""
		# The two error branches below carry no Prototype source and run no
		# script, so the sandbox changes nothing a reader sees. They still take
		# the same headers as the document: one rule for the whole renderer is
		# one rule to check.
		path = runtime_html_path(self.doc.pin)
		if not path or not os.path.isfile(path):
			# Trap 11. Never a blank iframe.
			return self.build_response(missing_runtime_html(self.doc.pin), 500, self.response_headers())

		with open(path, encoding="utf-8") as handle:
			document = handle.read()

		count = document.count(SLOT)
		if count != 1:
			# Contract 4. One occurrence, or the substitution lands somewhere
			# else and the page breaks in a way that is hard to read.
			return self.build_response(bad_slot_html(self.doc.pin, count), 500, self.response_headers())

		body = self.sandboxed_document(document.replace(SLOT, to_json(self.payload()), 1))
		# Only the served document counts as an open. The two branches above
		# are a broken install, not a reader.
		#
		# The `sig` test comes first, and it has to. A check arrives as a Guest
		# carrying the signature, so `is_owner` is false for it, and without
		# this test every check would be counted as a stranger reading a public
		# link. Sketch drives that browser itself.
		from sketch import events

		who = "check" if frappe.form_dict.get("sig") else ("owner" if self.is_owner else "public")
		events.record(events.VIEWER_OPEN, prototype=self.doc.name, detail=who)
		return self.build_response(body, 200, self.response_headers())

	def is_live(self) -> bool:
		"""True when this page may poll sketch.api.signed_revision.

		"May", not "does". The renderer cannot tell a top-level tab from the
		gallery's card iframe, so the last word belongs to the page: only a
		top-level document starts the poller, and only it prints the line that
		promises a reload (runtime/viewer/boot.js, reloadsItself).

		Only the owner, in a real browser session, gets that far. Two other
		callers reach the same document and must not poll:

		- `check`. It comes in as Guest with the signature `can_render` reads
		  from form_dict, so the `sig` parameter marks it. Its report carries
		  every console error the page raised, and a poll would add noise to
		  every check.
		- a Guest on a public Prototype. A reader who does not own the tree has
		  nothing to wait for: no agent is writing to it.

		Only a live page is minted a credential, so only a live page can poll
		at all (`payload`).
		"""
		if not self.is_owner or frappe.session.user == "Guest":
			return False

		return not frappe.form_dict.get("sig")

	def payload(self) -> dict:
		"""The data slot contents (contract 4).

		`rev` is the poller's baseline, read here rather than at the first
		poll. The first poll lands about two seconds after the page loads, and
		a write inside that window used to become the baseline, so the page
		never reloaded. That window is exactly when the agent writes.

		It is a stat walk, so only a live page pays for it. A Guest and a
		`check` request get "" and never call revision(). The owner's own card
		preview still pays for a baseline its iframe never polls with, which is
		one stat walk per card and the price of one honest `live` flag here.

		`exp` and `sig` are how the poller authenticates. The document sits in
		an opaque origin, so its requests carry no session cookie, and the
		signature takes the cookie's place for this one read
		(`sketch.api.signed_revision`). Its scope is REVISION, so it opens the
		number and never this document.

		The page runs a stranger's code whenever the tree was forked, and that
		code reads the payload. It learns the revision counter of a tree it
		already holds in full, one line above. Nothing else: the signature
		covers this hash id, so it says nothing about any other Prototype.
		"""
		live = self.is_live()
		stamp = signature.mint(self.doc.name, LIVE_TTL_SECONDS, signature.REVISION) if live else {}
		return {
			"files": prototype_files.read_tree(self.doc.name),
			"name": self.doc.name,
			"title": self.doc.title,
			"slug": self.doc.slug,
			"pin": self.doc.pin,
			"is_public": bool(self.doc.is_public),
			"is_owner": self.is_owner,
			"live": live,
			"rev": prototype_files.revision(self.doc.name) if live else "",
			"exp": stamp.get("exp", ""),
			"sig": stamp.get("sig", ""),
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
