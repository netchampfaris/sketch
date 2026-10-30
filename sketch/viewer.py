# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The Viewer page_renderer on /u/<username>/<slug>.

There is no files endpoint. This renderer is the only door, and it carries the
Prototype source tree inside the page.

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
	prototype_theme,
	runtime_assets,
	sharing,
	signature,
	thumbnail,
	thumbnails,
	variant_order,
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
	theme client side: the person's prototype theme (`theme_pref`), the visit's
	choice for a Guest, then the browser preference (spec 12, decision 84).
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
	    valid unexpired signature             -> serve
	    signed in, commented here before it
	      was made private                    -> a short page saying so (403)
	    otherwise                             -> False, so Frappe answers 404

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
		if sharing.can_view(self.doc.name, frappe.session.user):
			return True

		if signature.verify(self.doc.name, frappe.form_dict.get("exp"), frappe.form_dict.get("sig")):
			return True

		self.former_commenter = self.is_former_commenter()
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
		if self.former_commenter:
			# No Prototype source here, so no sandbox: the page loads core's own styles and font.
			return self.build_response(private_html(self.doc.owner), 403, dict(HEADERS))

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
		body = self.sandboxed_document(document.replace(SLOT, to_json(self.payload()), 1))
		# Only the served document counts as an open. The two branches above
		# are a broken install, not a reader.
		#
		# The `sig` test comes first, and it has to. A check arrives as a Guest
		# carrying the signature, so `is_owner` is false for it, and without
		# this test every check would be counted as a stranger reading a public
		# link. Sketch drives that browser itself.
		from sketch import events

		if not frappe.form_dict.get("sig"):
			# An invited editor who opens it has seen the invitation and any default made of their variant.
			badges.opened(self.doc.name, frappe.session.user)
			# A page load is a GET, which Frappe never commits. Without this the mark is rolled back and the
			# invitation stays news for ever.
			frappe.db.commit()

		who = "check" if frappe.form_dict.get("sig") else ("owner" if self.is_owner else "public")
		events.record(events.VIEWER_OPEN, prototype=self.doc.name, detail=who)
		return self.build_response(body, 200, self.response_headers())

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

	def commenter(self) -> str:
		"""The username of a signed-in person who may comment here, else "".

		The owner, an invited editor, or a signed-in reader of a public Prototype,
		in a real browser session. A Guest has nobody to sign the comment, and a
		`check` request is nobody at all. It is only a name for the toolbar to show;
		the pass that lets the person write is minted later (`sketch.api.comment_pass`).
		"""
		reader = self.signed_in_username()
		return reader if reader and comments.can_see(self.doc.name, frappe.session.user) else ""

	def signed_in_username(self) -> str:
		"""The username of the signed-in person reading this page, in a real browser session, else ""."""
		if frappe.session.user == "Guest" or frappe.form_dict.get("sig"):
			return ""

		return frappe.db.get_value("User", frappe.session.user, "username") or ""

	def role(self) -> str:
		"""owner, editor, viewer or guest, for the page's chrome. A `check` request is a guest."""
		if frappe.form_dict.get("sig"):
			return "guest"

		return sharing.role_of(self.doc.name, frappe.session.user)

	def offers_sign_in(self) -> bool:
		"""True when a signed-out visitor to a public Prototype is shown "Sign in to comment".

		Not for a `check` request, which is a Guest too and wants no toolbar.
		"""
		return frappe.session.user == "Guest" and bool(self.doc.is_public) and not frappe.form_dict.get("sig")

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

		`annotations`, `annotations_epoch`, `annotate_exp` and `annotate_sig` feed the owner's
		toolbar and follow the same rule: live owner pages only, so a Guest and
		a `check` request carry none (sketch/annotations.py).

		A signed-in person who may comment gets `commenter` (their username) and
		`comments_open` (a count) and a ticket that can only ask for a pass. Never a
		pass and never a comment: the toolbar mints its 15 minute pass when
		Comment mode opens (`sketch.api.comment_pass`) and reads the threads with it.
		"""
		live = self.is_live()
		stamp = signature.mint(self.doc.name, LIVE_TTL_SECONDS, signature.REVISION) if live else {}
		# The toolbar's own credential, for the same page and the same TTL. A
		# separate scope, so the poll signature cannot write annotations and
		# this one cannot read the revision (sketch/signature.py).
		mark = signature.mint(self.doc.name, LIVE_TTL_SECONDS, signature.ANNOTATE) if live else {}
		reader = self.signed_in_username()
		role = self.role()
		commenter = self.commenter()
		ticket = comments.mint_ticket(self.doc.name, commenter) if commenter else {}
		# An invited editor gets Note and Tweak for their own agent: their own notes, and a signature over their name
		# that writes those and nothing else. The owner's notes never reach their page, nor theirs the owner's.
		noting = commenter if commenter and role == "editor" else ""
		if noting:
			mark = signature.mint(comments.subject(self.doc.name, noting), LIVE_TTL_SECONDS, signature.ANNOTATE)
		# Make default writes the source, so it has a scope of its own: neither
		# the poll nor the toolbar signature can change a set.
		variant = signature.mint(self.doc.name, LIVE_TTL_SECONDS, signature.VARIANT_DEFAULT) if live else {}
		# Deleting a variant is the owner's, for any, and an invited editor's, for
		# their own. The credential names the person, so the server reads who is
		# asking from it and never from the page (`sketch.api.delete_variant_signed`).
		editing = reader if role in ("owner", "editor") else ""
		delete = (
			signature.mint(comments.subject(self.doc.name, editing), LIVE_TTL_SECONDS, signature.VARIANT_EDIT)
			if editing
			else {}
		)
		# What is new for this person, and the right to say they have looked
		# (`sketch.badges`, `sketch.api.seen_mark`). Nobody else gets either.
		seen = signature.mint(comments.subject(self.doc.name, commenter), LIVE_TTL_SECONDS, signature.SEEN) if commenter else {}
		fresh = badges.page(self.doc.name, frappe.session.user) if commenter else None
		# The theme this person's prototypes open in, and the right to save it from the Prototype's own switch
		# (`sketch.prototype_theme`, `sketch.api.prototype_theme_signed`). A Guest and a `check` get neither.
		theming = signature.mint(prototype_theme.subject(reader), LIVE_TTL_SECONDS, signature.THEME) if reader else {}
		tree = prototype_files.read_tree(self.doc.name)
		adopted = sharing.read_adopted(tree)
		return {
			"files": tree,
			"role": role,
			"authors": {**sharing.authors(tree), **sharing.adopted_authors(adopted)},
			# When each variant option first appeared, so a set shows them oldest first (sketch/variant_order.py).
			"variant_seen": variant_order.first_seen(self.doc.name),
			"editor": editing,
			"edit_exp": delete.get("exp", ""),
			"edit_sig": delete.get("sig", ""),
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
			"annotate_exp": mark.get("exp", ""),
			"annotate_sig": mark.get("sig", ""),
			"commenter": commenter,
			"sign_in": self.offers_sign_in(),
			"comment_exp": ticket.get("exp", ""),
			"comment_sig": ticket.get("sig", ""),
			"comments_open": comments.open_count(self.doc.name) if commenter else 0,
			"seen_exp": seen.get("exp", ""),
			"seen_sig": seen.get("sig", ""),
			"badges": fresh,
			"variant_exp": variant.get("exp", ""),
			"variant_sig": variant.get("sig", ""),
			"theme": url_theme(),
			"theme_pref": prototype_theme.read(frappe.session.user) if reader else None,
			"theme_user": reader,
			"theme_exp": theming.get("exp", ""),
			"theme_sig": theming.get("sig", ""),
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
