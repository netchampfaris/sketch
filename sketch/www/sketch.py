"""The one page that boots the Sketch SPA, and where a Guest goes instead.

`home_page = "sketch"` in hooks.py points the site root here, and
`website_route_rules` sends `/settings`, `/feed` and `/about` here as well.
"""

import frappe

no_cache = 1

#: Where a signed-out visitor at the site root is sent. It is a route of the
#: SPA (`frontend/src/router.ts`), served through this same page.
FEED_PATH = "/feed"

#: The SPA routes a Guest is served, rather than redirected away from.
#:
#: /feed is the front door and /about is the page it links to, and neither
#: needs a session: `sketch.api.public_prototypes` carries `allow_guest`, and
#: /about is prose. Both are routes of the SPA, so a Guest on one of them does
#: download the bundle. That is the trade this page used to refuse (problem
#: B4): the feed was a server-rendered template, and it is a frappe-ui screen
#: now, with the same card, the same Files browser and the same Export the
#: gallery has.
#:
#: `website_route_rules` in hooks.py has to name each one as well, or a direct
#: load of it is a 404.
PUBLIC_PATHS = ("/feed", "/about")

#: The request paths that count as the site root. `/` resolves through
#: `home_page`, and `/index` reaches the same renderer, so both are the root as
#: far as a visitor is concerned. `/settings` and `/sketch/...` are not: they
#: are deep links into the app and keep the redirect to /login.
ROOT_PATHS = ("", "/index")

#: Where a Guest on a private path is sent. No query string.
LOGIN_PATH = "/login"

#: The cookie that carries the path the visitor asked for, across /login.
#:
#: `/login?redirect-to=<path>` cannot do this job here. Core's
#: `sanitize_redirect` (`frappe/www/login.py`) makes the value absolute with
#: the Host header, not `conf.host_name`. The Cloudflare tunnel rewrites that
#: Host to `sketch.localhost`, so the path becomes
#: `http://sketch.localhost/<path>`. Core then puts that URL in the OAuth
#: state (`frappe/utils/oauth.py`), and `redirect_post_login` prefers it over
#: `frappe.utils.get_url()`. The visitor lands on a name a browser cannot
#: reach. The value never leaves Sketch this way, so no core code rewrites it.
#:
#: `frontend/src/store.ts` writes the same cookie, and `App.vue` reads it once
#: at boot.
AFTER_LOGIN_COOKIE = "sketch_after_login"

#: How long the cookie lives, in seconds. Long enough for one trip through
#: GitHub, short enough that an abandoned sign-in moves no later visit.
AFTER_LOGIN_MAX_AGE = 600


def get_context():
	if frappe.session.user == "Guest":
		# Returns only for a path in PUBLIC_PATHS. Every other Guest leaves
		# this page, so no Guest is handed the bundle for a screen that needs
		# a session.
		_redirect_guest()

	csrf_token = frappe.sessions.get_csrf_token()
	frappe.db.commit()
	context = frappe._dict()
	context.boot = get_boot()
	context.boot.csrf_token = csrf_token
	return context


def _redirect_guest() -> None:
	"""Decide what a signed-out visitor gets: the bundle, /feed, or /login.

	Three answers, decided by the path.

	A path in PUBLIC_PATHS is served. /feed and /about are SPA routes a Guest
	may read, so this returns and the bundle goes out with no session.

	The site root goes to /feed. Every public URL used to redirect to /login,
	so the first thing a visitor met was a login form for a product they had
	never read a sentence about (problem 8.1). The feed answers that: it says
	what Sketch is in one line, it carries the sign-in action, and it shows
	real work.

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
	if path in PUBLIC_PATHS:
		return

	if path not in ROOT_PATHS:
		_redirect_to_login(request)

	frappe.local.flags.redirect_location = FEED_PATH
	raise frappe.Redirect(302)


def _redirect_to_login(request) -> None:
	"""Leave this page for /login, and put the wanted path in a cookie.

	The redirect carries no query. See AFTER_LOGIN_COOKIE for why a
	`redirect-to` parameter sends the visitor to the wrong host.

	`frappe.Redirect` is the website way to leave a `get_context`. Core reads
	`flags.redirect_location` in its exception handler and answers 301.
	"""
	back = getattr(request, "full_path", "/") if request else "/"
	# full_path keeps a bare "?" on a query-less URL. Drop it, so the cookie
	# holds the path the visitor typed.
	back = back.rstrip("?") or "/"

	_remember_path(back)

	frappe.local.flags.redirect_location = LOGIN_PATH
	raise frappe.Redirect


def _remember_path(path: str) -> None:
	"""Store the path to come back to, or store nothing.

	An unsafe path is dropped without a word. The visitor still reaches
	/login, and after sign-in core sends them to the home page.

	`CookieManager.set_cookie` (`frappe/auth.py`) takes no path argument.
	Werkzeug writes `Path=/`, which is what this cookie needs: it is set on
	the SPA page and read on another one. `httponly` stays off, because the
	SPA reads it in JavaScript. `secure` follows the request scheme.
	"""
	cookie_manager = getattr(frappe.local, "cookie_manager", None)
	if cookie_manager is None or not is_safe_path(path):
		return

	cookie_manager.set_cookie(
		AFTER_LOGIN_COOKIE,
		path,
		max_age=AFTER_LOGIN_MAX_AGE,
		httponly=False,
		samesite="Lax",
	)


def is_safe_path(path: str) -> bool:
	"""True for a relative path that stays on this site.

	One leading slash, and no second one. `//evil.example/x` is a
	scheme-relative URL and a browser reads it as another host. Some browsers
	read a backslash as a slash, so `/\\evil.example` is the same trap. A
	control character can cut a header short, so it is refused as well.

	Anything that fails here is dropped, never repaired.
	"""
	if not path or not path.startswith("/") or path.startswith(("//", "/\\")):
		return False

	return all(character >= " " and character != "\x7f" for character in path)


def get_boot():
	return frappe._dict(
		{
			"frappe_version": frappe.__version__,
			"site_name": frappe.local.site,
		}
	)
