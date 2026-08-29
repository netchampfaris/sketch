"""The one page that boots the Sketch SPA, and the page a Guest gets instead.

`home_page = "sketch"` in hooks.py points the site root here, and
`website_route_rules` sends `/settings` here as well.
"""

from urllib.parse import quote

import frappe
from frappe.utils import get_url

no_cache = 1

#: The template a signed-out visitor gets at the site root. It sits outside
#: `templates/pages`, so `/` stays its only address (see the file's own note).
MARKETING_TEMPLATE = "sketch/templates/marketing.html"

#: The request paths that count as the site root. `/` resolves through
#: `home_page`, and `/index` reaches the same renderer, so both are the root as
#: far as a visitor is concerned. `/settings` and `/sketch/...` are not: they
#: are deep links into the app and keep the redirect to /login.
ROOT_PATHS = ("", "/index")


def get_context():
	if frappe.session.user == "Guest":
		return _guest_context()

	csrf_token = frappe.sessions.get_csrf_token()
	frappe.db.commit()
	context = frappe._dict()
	context.boot = get_boot()
	context.boot.csrf_token = csrf_token
	return context


def _guest_context() -> frappe._dict:
	"""Answer a signed-out visitor without serving the SPA bundle.

	Two answers, decided by the path.

	The site root gets the marketing page. Every public URL used to redirect,
	so the first thing a visitor met was a login form for a product they had
	never read a sentence about (problem 8.1). Swapping `context.template` is
	enough to change the page: `TemplatePage.get_html` calls `update_context`,
	which runs this function, before `setup_template_source` reads the template
	(`frappe/website/page_renderers/template_page.py:87-100`), and
	`BaseTemplatePage.post_process_context` then copies `context.template` back
	over `self.template_path`
	(`frappe/website/page_renderers/base_template_page.py:34`).

	Every other path here is a deep link into the app: `/settings` and
	`/sketch/...`. Those still bounce to /login, and the bounce happens before
	the bundle is served. Without it a Guest downloads the whole SPA, the SPA
	calls `get_session`, that throws `PermissionError`, and only then does the
	browser move to /login. The visitor pays for a bundle they cannot use.
	"""
	request = getattr(frappe.local, "request", None)
	path = (getattr(request, "path", "/") or "/").rstrip("/")
	if path not in ROOT_PATHS:
		_redirect_to_login(request)

	return frappe._dict(
		{
			"template": MARKETING_TEMPLATE,
			"title": "Sketch",
			"description": (
				"High-fidelity frappe-ui prototypes, written by your own agent over MCP."
			),
			# One page owns the OAuth URL, so the button here only has to point
			# at it. /login also keeps a `redirect-to` when core sends a deep
			# link through it.
			"sign_in_url": "/login",
			"mcp_url": get_url("/mcp"),
		}
	)


def _redirect_to_login(request) -> None:
	"""Leave this page for /login, carrying the path the visitor asked for.

	`frappe.Redirect` is the website way to leave a `get_context`. Core reads
	`flags.redirect_location` in its exception handler and answers 301.
	"""
	back = getattr(request, "full_path", "/") if request else "/"
	# full_path keeps a bare "?" on a query-less URL. It is harmless, but the
	# login page echoes this value, so send the clean form.
	back = back.rstrip("?") or "/"

	frappe.local.flags.redirect_location = f"/login?redirect-to={quote(back, safe='')}"
	raise frappe.Redirect


def get_boot():
	return frappe._dict(
		{
			"frappe_version": frappe.__version__,
			"site_name": frappe.local.site,
		}
	)
