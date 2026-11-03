# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The Viewer page_renderer on /u/<username>/<slug>.

The Viewer is two documents. /u/<username>/<slug> is the shell: Sketch's own
page on Sketch's origin, with the reader's session, drawing the toolbar,
comments, notes, the Demo pill and the tile menus. It holds no Prototype
source. It frames the same URL with ?frame=1, which is the Prototype itself,
sandboxed into an opaque origin and holding nothing that can act as anyone.
`check` opens the frame's document directly, with a short-lived signed URL
(?exp&sig), because it comes in as a Guest.

There is no files endpoint. The frame's document is the only door, and it
carries the Prototype source tree inside the page.

It reads the pinned Runtime's own viewer.html from disk and substitutes one
slot (spec 6.1), plus the static <title> for the link preview tags. It does not rebuild the document from manifest.json: that
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
from frappe.website.page_renderers.template_page import TemplatePage

from sketch import (
	annotations,
	badges,
	comments,
	prototype,
	prototype_files,
	runtime_assets,
	sharing,
	signature,
	thumbnail,
	thumbnails,
)

#: The literal build.sh stamps into each per-Pin viewer.html (contract 4).
SLOT = "SKETCH_DATA"

#: The static title every Runtime's viewer.html ships. `head_html` replaces it.
TITLE = "<title>Prototype</title>"

#: The size checkd captures a Thumbnail at (checkd/check-lib.mjs VIEWPORT).
THUMBNAIL_SIZE = (1280, 800)

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

THEMES = ("light", "dark")

#: The shell runs Sketch's own code on Sketch's origin with the reader's session, so it is never
#: sandboxed and never framed. It may frame one thing: the Prototype, from this origin.
SHELL_HEADERS = {
	"Cache-Control": "no-store",
	"Content-Security-Policy": "frame-ancestors 'none'; frame-src 'self'; object-src 'none'; base-uri 'self'",
	"Content-Type": "text/html; charset=utf-8",
}

#: The shell's page, as the frontend build writes it (frontend/viewer.html). It sits beside the SPA's
#: bundle in public/frontend, because that folder ships in prebuilt assets and a templates path does not.
SHELL_HTML = ("public", "frontend", "viewer.html")

#: The literal frontend/viewer.html carries once, for the shell's boot JSON.
SHELL_SLOT = "SKETCH_SHELL"


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
	    caller is an invited editor           -> serve
	    valid unexpired `check` signature     -> serve
	    signed in, commented here before it
	      was made private                    -> a short page saying so (403)
	    otherwise                             -> False, so Frappe answers 404

	The same ladder runs for the shell and for its frame (?frame=1), so the
	frame's own request is checked again with the reader's cookie.

	A bad or expired signature is not an error. It falls through, so a stale
	link to a public Prototype still works and a private one still answers 404.
	The answer is 404, never 403, for everyone but a former commenter: a 403
	confirms the URL exists, and that person has already seen it (decision 46).
	"""

	def __init__(self, path=None, http_status_code=None):
		super().__init__(path=path, http_status_code=http_status_code)
		self.doc = None
		self.username = ""
		self.is_owner = False
		self.former_commenter = False
		self.mode = "shell"

	def request_mode(self) -> str:
		"""Which response this request gets.

		check  the Guest `check` request (?exp&sig): the Prototype's document, with no chrome
		frame  ?frame=1, the shell's iframe: the Prototype and nothing that can act as anyone
		shell  everything else: Sketch's page around the iframe
		"""
		if frappe.form_dict.get("sig"):
			return "check"

		return "frame" if frappe.form_dict.get("frame") == "1" else "shell"

	def can_render(self) -> bool:
		"""True only when this path is a Prototype the caller may see."""
		if self.path.startswith("u/"):
			# A guest's 404 must not prevent the owner from opening this URL.
			frappe.local.no_cache = True

		parts = self.path.split("/")
		if len(parts) != 3 or parts[0] != "u" or not parts[1] or not parts[2]:
			return False

		self.doc = prototype.resolve_public(parts[1], parts[2])
		if not self.doc:
			return False

		self.username = parts[1]
		self.is_owner = frappe.session.user == self.doc.owner
		self.mode = self.request_mode()
		if sharing.can_view(self.doc.name, frappe.session.user):
			return True

		if signature.verify(self.doc.name, frappe.form_dict.get("exp"), frappe.form_dict.get("sig")):
			return True

		# The frame is never a person's page: the shell around it has already said "made private".
		self.former_commenter = self.mode != "frame" and self.is_former_commenter()
		return self.former_commenter

	def is_former_commenter(self) -> bool:
		"""True for a signed-in person who commented here while it was public and cannot open it now."""
		if frappe.session.user == "Guest" or self.doc.is_public:
			return False

		username = sharing.username_of(frappe.session.user)
		return bool(username) and bool(frappe.db.exists(comments.COMMENT, {"prototype": self.doc.name, "author": username}))

	def response_headers(self) -> dict:
		"""The response headers for this caller. can_render() ran first.

		Not `headers`: BaseRenderer.__init__ sets `self.headers = None`, and an
		instance attribute shadows a method of the same name.

		This is the Prototype's document (the frame, and `check`). Every
		caller gets the sandbox, the owner as well. Ownership says who holds
		the tree, never who wrote the code in it: `sketch.api.fork_prototype`
		copies another user's public tree, word for word, into a Prototype the
		caller owns. An owner exemption therefore hands a stranger's JavaScript
		the app origin and the reader's session, which is the whole attack the
		sandbox exists to stop. One rule for every caller is one rule to check.

		The shell around it is Sketch's own code and takes SHELL_HEADERS instead.
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
		"""The shell, or the pinned Runtime document with the tree in the data slot."""
		if self.former_commenter:
			# No Prototype source here, so no sandbox: the page loads core's own styles and font.
			return self.build_response(private_html(self.doc.owner), 403, dict(HEADERS))

		if self.mode == "shell":
			return self.render_shell()

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

		document = document.replace(TITLE, self.head_html(), 1)
		body = self.sandboxed_document(document.replace(SLOT, to_json(self.frame_payload()), 1))
		if self.mode == "check":
			# Sketch drives that browser itself: an event for the counts, and no reader's badges.
			self.count_open()

		# The frame is not counted: the shell counted this open, and the frame is the same reader a moment later.
		return self.build_response(body, 200, self.response_headers())

	def count_open(self) -> None:
		"""Record one open of this Prototype: the reader's badges and the Viewer event.

		The `sig` test comes first, and it has to. A check arrives as a Guest
		carrying the signature, so `is_owner` is false for it, and without this
		test every check would be counted as a stranger reading a public link.
		"""
		from sketch import events

		if not frappe.form_dict.get("sig"):
			# An invited editor who opens it has seen the invitation and any default made of their variant.
			badges.opened(self.doc.name, frappe.session.user)
			# A page load is a GET, which Frappe never commits. Without this the mark is rolled back and the
			# invitation stays news for ever.
			frappe.db.commit()

		who = "check" if frappe.form_dict.get("sig") else ("owner" if self.is_owner else "public")
		events.record(events.VIEWER_OPEN, prototype=self.doc.name, detail=who)

	def render_shell(self):
		"""Sketch's own page around the Prototype's iframe.

		It carries no Prototype source, so it needs no Runtime and no sandbox: everything in it is
		Sketch's code. The iframe loads this URL with ?frame=1, which `can_render` checks again.
		"""
		path = frappe.get_app_path("sketch", *SHELL_HTML)
		if not os.path.isfile(path):
			return self.build_response(missing_shell_html(), 500, dict(SHELL_HEADERS))

		with open(path, encoding="utf-8") as handle:
			document = handle.read()

		count = document.count(SHELL_SLOT)
		if count != 1:
			return self.build_response(bad_shell_html(count), 500, dict(SHELL_HEADERS))

		document = document.replace(TITLE, self.head_html(), 1)
		body = document.replace(SHELL_SLOT, to_json(self.shell_payload()), 1)
		self.count_open()
		return self.build_response(body, 200, dict(SHELL_HEADERS))

	def head_html(self) -> str:
		"""The <title> and the Open Graph tags a link preview reads.

		A crawler runs no script, so boot.js setting the title is too late for
		it. The image is the light Thumbnail, and only on a public Prototype:
		the crawler is a Guest, and a Guest gets 404 from a private picture.
		"""
		author = frappe.db.get_value("User", self.doc.owner, "full_name") or self.username
		url = f"{prototype.site_url()}/u/{self.username}/{self.doc.slug}"
		properties = {
			"og:type": "website",
			"og:site_name": "Sketch",
			"og:title": self.doc.title,
			"og:description": f"A prototype by {author}, built with frappe-ui on Sketch.",
			"og:url": url,
		}
		image = self.preview_image_url()
		if image:
			properties.update(
				{
					"og:image": image,
					"og:image:width": str(THUMBNAIL_SIZE[0]),
					"og:image:height": str(THUMBNAIL_SIZE[1]),
					"og:image:alt": self.doc.title,
				}
			)

		tags = [
			f"<title>{escape_html(self.doc.title)}</title>",
			meta_tag("name", "description", properties["og:description"]),
			meta_tag("name", "twitter:card", "summary_large_image" if image else "summary"),
		]
		tags += [meta_tag("property", key, value) for key, value in properties.items()]
		return "\n    ".join(tags)

	def preview_image_url(self) -> str | None:
		"""The absolute URL of the light Thumbnail, or None when a crawler cannot read one."""
		if not self.doc.is_public or "light" not in thumbnails.meta(self.doc.name).get("themes", []):
			return None

		path = thumbnail.url(self.username, self.doc.slug, "light", thumbnails.stamp(self.doc.name))
		return f"{prototype.site_url()}{path}"

	def is_live(self) -> bool:
		"""True when the shell reloads the frame as the agent writes: the owner, signed in.

		A reader who does not own the tree has nothing to wait for: no agent is
		writing to it. The shell polls `sketch.api.prototype_revision` with the
		session, and `shell_payload` reads the baseline `rev` for it.
		"""
		return self.is_owner and frappe.session.user != "Guest"

	def commenter(self) -> str:
		"""The username of a signed-in person who may comment here, else "".

		The owner, or anyone signed in who may see the Prototype. A Guest has
		nobody to sign the comment.
		"""
		if frappe.session.user == "Guest":
			return ""

		if not comments.can_see(self.doc.name, frappe.session.user):
			return ""

		return frappe.db.get_value("User", frappe.session.user, "username") or ""

	def offers_sign_in(self) -> bool:
		"""True when a signed-out visitor to a public Prototype is shown "Sign in to comment"."""
		return frappe.session.user == "Guest" and bool(self.doc.is_public)

	def frame_payload(self) -> dict:
		"""The data slot (contract 4) of the shell's iframe and of `check`: the Prototype and nothing else.

		The frame runs the Prototype's code, which may be a stranger's (a fork), so it holds nothing
		that can act as anyone or say who is reading: no signature of any scope, no notes, no
		badges, no role and no revision. Everything that acts or shows a person's data lives in the
		shell (`shell_payload`), on Sketch's origin, behind the session.

		`chrome` is "shell" in the shell's frame, where the agent talks to the shell, and "off" for
		`check`, which shows the design alone.
		"""
		tree = prototype_files.read_tree(self.doc.name)
		adopted = sharing.read_adopted(tree)
		return {
			"files": tree,
			"name": self.doc.name,
			"title": self.doc.title,
			"slug": self.doc.slug,
			"pin": self.doc.pin,
			"authors": {**sharing.authors(tree), **sharing.adopted_authors(adopted)},
			"theme": url_theme(),
			"chrome": "off" if self.mode == "check" else "shell",
		}

	def shell_payload(self) -> dict:
		"""The shell's boot JSON: who is reading and what their chrome needs. Never the tree.

		The shell is Sketch's page on Sketch's origin, so it holds the reader's session and the
		CSRF token its writes send. The owner's poller reads `rev` as its baseline and asks
		`sketch.api.prototype_revision` with the session from then on. It is read here rather than
		at the first poll: the first poll lands about two seconds after the page loads, a write
		inside that window used to become the baseline, and that window is exactly when the agent
		writes.

		`annotations` are the owner's own notes and tweaks, or an invited editor's own; nobody
		else gets any (sketch/annotations.py). The two never mix (decision 29).
		"""
		role = sharing.role_of(self.doc.name, frappe.session.user)
		signed_in = frappe.session.user != "Guest"
		commenter = self.commenter()
		noting = bool(commenter) and role == "editor"
		live = self.is_live()
		csrf_token = frappe.sessions.get_csrf_token() if signed_in else ""
		if signed_in:
			# A GET is never committed, and a token that is not saved fails the first write.
			frappe.db.commit()

		return {
			"name": self.doc.name,
			"title": self.doc.title,
			"slug": self.doc.slug,
			"owner_username": self.username,
			"role": role,
			"me": sharing.person(frappe.session.user) if signed_in else None,
			"is_public": bool(self.doc.is_public),
			"sign_in": self.offers_sign_in(),
			"comments_open": comments.open_count(self.doc.name) if commenter else 0,
			"badges": badges.page(self.doc.name, frappe.session.user) if commenter else None,
			"annotations": annotations.read(self.doc.name, editor=frappe.session.user)
			if noting
			else annotations.read(self.doc.name)
			if live
			else None,
			"annotations_epoch": annotations.epoch(self.doc.name, frappe.session.user)
			if noting
			else annotations.epoch(self.doc.name)
			if live
			else 0,
			"rev": prototype_files.revision(self.doc.name) if live else "",
			"csrf_token": csrf_token,
			"theme": url_theme(),
			"frame_src": f"/u/{self.username}/{self.doc.slug}?frame=1",
		}


def meta_tag(attribute: str, key: str, content: str) -> str:
	"""One <meta> tag, with the content escaped for an attribute value."""
	return f'<meta {attribute}="{key}" content="{escape_html(content)}" />'


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


def missing_shell_html() -> str:
	"""The readable 500 body when the frontend build has not written the shell's page."""
	return _error_html(
		"Viewer shell not built",
		"The page that holds a prototype is not built on this server.",
		"Build the frontend.",
	)


def bad_shell_html(count: int) -> str:
	"""The readable 500 body for a shell page with a broken boot slot."""
	return _error_html(
		"Viewer shell slot is broken",
		f"viewer.html holds the shell slot {count} times. It must hold it once.",
		"Rebuild the frontend.",
	)


def private_html(owner: str) -> str:
	"""What a person who commented before the owner made the Prototype private is shown instead of a bare 404."""
	name = (frappe.db.get_value("User", owner, "full_name") or "").split()
	who = name[0] if name else sharing.username_of(owner) or "The owner"
	page = PrivatePage(f"{who} made this prototype private", f"Ask {who} for access if you need it.")
	return page.get_html()


class PrivatePage(TemplatePage):
	"""Core's "Page not found" look for the made-private page: the same template shell, with its own words.

	The template sits in `sketch/templates`, outside `www` and `templates/pages`, so no URL reaches it.
	"""

	def __init__(self, heading: str, detail: str):
		super().__init__(path="private-prototype", http_status_code=403)
		self.heading = heading
		self.detail = detail

	def set_template_path(self):
		self.app = "sketch"
		self.app_path = frappe.get_app_path("sketch")
		self.file_dir = "templates"
		self.template_path = os.path.join("templates", "private_prototype.html")
		self.basepath = os.path.join(self.app_path, "templates")
		self.filename = os.path.basename(self.template_path)
		self.name = "private_prototype"
		self.basename = os.path.join(self.basepath, self.name)

	def init_context(self):
		super().init_context()
		# Not `title`: core stamps the site name onto that one.
		self.context.heading = self.heading
		self.context.detail = self.detail
		self.context.no_cache = 1


def _error_html(title: str, detail: str, action: str = "") -> str:
	"""A plain page a person can read. No Runtime, so no Runtime assets."""
	note = f"<p style='margin:0;color:#666'>{action}</p>" if action else ""
	return (
		"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
		"<meta name='viewport' content='width=device-width, initial-scale=1'>"
		f"<title>{title}</title></head>"
		'<body style="margin:0;padding:2rem;font:14px/1.6 ui-sans-serif,system-ui,sans-serif">'
		f"<h1 style='font-size:1rem;margin:0 0 .5rem'>{title}</h1>"
		f"<p style='margin:0 0 .5rem'>{detail}</p>"
		f"{note}"
		"</body></html>"
	)
