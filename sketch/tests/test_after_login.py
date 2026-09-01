# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""Where a Guest is sent, and how the path they wanted survives the trip.

Sketch used to bounce a Guest to `/login?redirect-to=<path>`. Core's
`sanitize_redirect` (`frappe/www/login.py`) makes that value absolute with the
Host header, not `conf.host_name`. The Cloudflare tunnel rewrites the Host to
`sketch.localhost`, so the path became `http://sketch.localhost/<path>`. Core
put that URL in the OAuth state (`frappe/utils/oauth.py`), and
`redirect_post_login` preferred it over `frappe.utils.get_url()`. The visitor
landed on a name no browser can reach.

So Sketch sends no `redirect-to` at all. The login URL is bare, and the wanted
path rides in the `sketch_after_login` cookie, which only Sketch reads:
`sketch/www/sketch.py` writes it, `frontend/src/App.vue` reads it once at boot.

The cookie holds a same-site relative path or nothing. Both sides check, and
these cases are the server side.
"""

from types import SimpleNamespace

import frappe
from frappe.auth import CookieManager
from frappe.tests import IntegrationTestCase

from sketch.www import sketch as sketch_page

#: Paths that must never reach the cookie. Each one is a way to name another
#: host, or to break the Set-Cookie header.
UNSAFE_PATHS = (
	"//evil.example/steal",
	"///evil.example",
	"/\\evil.example",
	"https://evil.example/steal",
	"settings",
	"/settings\nSet-Cookie: sid=1",
)


class TestAfterLoginCookie(IntegrationTestCase):
	def setUp(self):
		# `frappe.local.cookie_manager` belongs to a live request
		# (`frappe/auth.py`), and a test has no bound request. Lend one, and
		# put back whatever was there.
		self.addCleanup(
			self.restore_cookie_manager,
			hasattr(frappe.local, "cookie_manager"),
			getattr(frappe.local, "cookie_manager", None),
		)
		self.cookies = CookieManager()
		frappe.local.cookie_manager = self.cookies

	def restore_cookie_manager(self, existed: bool, before) -> None:
		if existed:
			frappe.local.cookie_manager = before
		elif hasattr(frappe.local, "cookie_manager"):
			del frappe.local.cookie_manager

	# ------------------------------------------------------------- probes

	def bounce(self, full_path: str) -> str:
		"""Run the guard for one request path. Returns the redirect target.

		`_redirect_to_login` always raises, the way a `get_context` leaves a
		page. Core reads `flags.redirect_location` in its exception handler.
		"""
		frappe.local.flags.redirect_location = None
		with self.assertRaises(frappe.Redirect):
			sketch_page._redirect_to_login(SimpleNamespace(full_path=full_path))

		return frappe.local.flags.redirect_location

	def cookie(self):
		"""The after-login cookie the guard wrote, or None."""
		return self.cookies.cookies.get(sketch_page.AFTER_LOGIN_COOKIE)

	# --------------------------------------------------------- the target

	def test_the_login_url_is_bare(self):
		"""Exactly `/login`. Any query at all is the old bug: core resolves
		`redirect-to` against the Host header, and the tunnel rewrites that
		Host, so the visitor comes back on an unreachable name."""
		self.assertEqual(self.bounce("/settings?"), "/login")

	def test_the_login_url_never_says_redirect_to(self):
		"""The string itself, on every path a Guest can ask for."""
		for path in ("/settings?", "/sketch/settings?", "/?", "/feed?tab=all"):
			self.assertNotIn("redirect-to", self.bounce(path), path)

	def test_the_login_url_carries_no_query_at_all(self):
		"""Not a renamed parameter either. Nothing rides on the URL."""
		self.assertNotIn("?", self.bounce("/settings?tab=agent"))

	# --------------------------------------------------------- the cookie

	def test_the_wanted_path_goes_into_the_cookie(self):
		self.bounce("/settings?")

		self.assertEqual(self.cookie()["value"], "/settings")

	def test_a_bare_question_mark_is_dropped(self):
		"""`full_path` keeps a `?` on a query-less URL. The cookie holds the
		path the visitor typed, so the SPA can compare it with a route."""
		self.bounce("/settings?")

		self.assertNotIn("?", self.cookie()["value"])

	def test_a_real_query_string_is_kept(self):
		"""A deep link with a query is still the page they asked for."""
		self.bounce("/settings?tab=agent")

		self.assertEqual(self.cookie()["value"], "/settings?tab=agent")

	def test_the_cookie_outlives_one_trip_through_github(self):
		"""Ten minutes, and no longer. A stale path must not move a later
		visit."""
		self.bounce("/settings?")

		self.assertEqual(self.cookie()["max_age"], sketch_page.AFTER_LOGIN_MAX_AGE)
		self.assertEqual(sketch_page.AFTER_LOGIN_MAX_AGE, 600)

	def test_the_spa_can_read_the_cookie(self):
		"""`App.vue` reads it in JavaScript, so httponly must stay off.
		SameSite=Lax lets it ride the top-level GET back from GitHub."""
		self.bounce("/settings?")

		self.assertFalse(self.cookie()["httponly"])
		self.assertEqual(self.cookie()["samesite"], "Lax")

	# --------------------------------------------------------- the refusal

	def test_an_unsafe_path_stores_nothing(self):
		"""Dropped, never repaired. The visitor still reaches /login, and
		after sign-in core sends them to the home page."""
		for path in UNSAFE_PATHS:
			with self.subTest(path=path):
				self.cookies.cookies.clear()

				self.assertEqual(self.bounce(path), "/login")
				self.assertIsNone(self.cookie())

	def test_is_safe_path_takes_only_a_same_site_path(self):
		"""The reader in `frontend/src/store.ts` applies the same rule."""
		for path in ("/", "/settings", "/feed?tab=all", "/u/name/slug"):
			self.assertTrue(sketch_page.is_safe_path(path), path)

		# An empty path is refused too. It never reaches the cookie, because
		# `_redirect_to_login` reads it as the site root first.
		for path in (*UNSAFE_PATHS, ""):
			self.assertFalse(sketch_page.is_safe_path(path), path)

	def test_a_missing_cookie_manager_does_not_break_the_bounce(self):
		"""The redirect is the job. The cookie is the nicety, and a caller
		outside a request has no cookie manager to write it with."""
		del frappe.local.cookie_manager

		self.assertEqual(self.bounce("/settings?"), "/login")
