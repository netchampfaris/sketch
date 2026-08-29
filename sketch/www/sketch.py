"""The one page that boots the Sketch SPA, and where a Guest goes instead.

`home_page = "sketch"` in hooks.py points the site root here, and
`website_route_rules` sends `/settings` here as well.
"""

from urllib.parse import quote

import frappe

no_cache = 1

#: Where a signed-out visitor at the site root is sent. `sketch/www/feed.py`
#: renders it on the server, so a Guest can read it with no session and no
#: role.
FEED_PATH = "/feed"

#: The request paths that count as the site root. `/` resolves through
#: `home_page`, and `/index` reaches the same renderer, so both are the root as
#: far as a visitor is concerned. `/settings` and `/sketch/...` are not: they
#: are deep links into the app and keep the redirect to /login.
ROOT_PATHS = ("", "/index")


def get_context():
	if frappe.session.user == "Guest":
		# Never returns. Both answers leave this page, so nothing below runs
		# for a Guest and no Guest is handed the bundle.
		_redirect_guest()

	csrf_token = frappe.sessions.get_csrf_token()
	frappe.db.commit()
	context = frappe._dict()
	context.boot = get_boot()
	context.boot.csrf_token = csrf_token
	return context


def _redirect_guest() -> None:
	"""Send a signed-out visitor away, without serving the SPA bundle.

	Two destinations, decided by the path.

	The site root goes to /feed. Every public URL used to redirect to /login,
	so the first thing a visitor met was a login form for a product they had
	never read a sentence about (problem 8.1). The feed answers that: it says
	what Sketch is in one line, it carries the sign-in action, and it shows
	real work. It is server rendered for this reason, so a Guest reads it with
	no session and no role (`sketch/www/feed.py`).

	The status is 302, not core's default 301. A 301 on the site root is a
	permanent instruction: a browser may keep it, and the same person, now
	signed in, would be sent to /feed forever and never reach the app again.
	`frappe.Redirect` takes the status (`frappe/exceptions.py:77-79`) and
	`handle_exception` hands it to `RedirectPage`
	(`frappe/website/serve.py:29-30`).

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

	frappe.local.flags.redirect_location = FEED_PATH
	raise frappe.Redirect(302)


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
