# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""Who gets the SPA bundle.

A signed-out visitor used to download the whole bundle on every path, watch it
call `get_session`, and only then bounce to /login. `sketch/www/sketch.py`
stops that at the server (problem B4).

Two of the SPA's routes are public now, /feed and /about, and a Guest is
served the bundle on those. That is the trade: the feed was a server-rendered
template and is a frappe-ui screen, so the page a signed-out visitor lands on
costs a bundle. Every other path keeps the guard, and the destination is
/login, with the wanted path in a cookie (`test_after_login.py`).

The site root still sends a Guest to /feed, because a visitor met a login form
for a product they had never read a sentence about (problem 8.1).

The Viewer is a different renderer and must not move. A public Prototype
belongs to whoever holds the link, signed in or not (spec 6.3).
"""

from frappe.tests import IntegrationTestCase

from sketch.tests import utils
from sketch.www import sketch as sketch_page

#: Proof the bundle was served. Both come from sketch/www/sketch.html.
BUNDLE_MARKS = ('id="app"', "/assets/sketch/frontend/")


class TestSpaAccess(IntegrationTestCase):
	def setUp(self):
		utils.require_webserver()

	def test_a_guest_at_the_root_goes_to_the_feed(self):
		"""The root sends a visitor to a page, not to a login form.

		This test asserted a 301 to /login, and then the marketing page body,
		before /feed took the front door (problem 8.1).

		302, not 301. A browser may keep a 301 on the site root, and the same
		person, signed in, would be sent to /feed for good.
		"""
		response = utils.request("GET", "/")

		self.assertEqual(response.status_code, 302)
		self.assertEqual(response.headers["Location"], "/feed")

	def test_a_guest_at_index_goes_to_the_same_place(self):
		"""`/index` reaches the same renderer, so it must answer the same."""
		response = utils.request("GET", "/index")

		self.assertEqual(response.status_code, 302)
		self.assertEqual(response.headers["Location"], "/feed")

	def test_a_guest_on_a_private_path_goes_to_a_bare_login(self):
		"""No query on the URL. `sketch/tests/test_after_login.py` says why:
		core resolves a `redirect-to` against the Host header, and the tunnel
		rewrites that Host, so the visitor comes back on a name no browser can
		reach."""
		response = utils.request("GET", "/settings")

		self.assertEqual(response.status_code, 301)
		self.assertEqual(response.headers["Location"], "/login")

	def test_a_guest_keeps_the_page_they_asked_for(self):
		"""The bounce carries the path back in a cookie, so the SPA returns
		them to it after they sign in. This case reads the header off the
		wire, because the cookie only reaches a browser when core flushes it
		on the redirect response (`frappe/app.py` `process_response`)."""
		response = utils.request("GET", "/settings")

		self.assertEqual(response.cookies.get(sketch_page.AFTER_LOGIN_COOKIE), "/settings")

	def test_a_guest_never_downloads_the_bundle_on_a_private_path(self):
		"""The point of the guard. No answer to a Guest on a path that needs a
		session may carry the SPA.

		Both Guest paths are read, because the two take different exits from
		`get_context`.
		"""
		for path in ("/", "/settings"):
			response = utils.request("GET", path)

			for mark in BUNDLE_MARKS:
				self.assertNotIn(mark, response.text, f"{path} carried {mark}")

	def test_a_guest_does_download_the_bundle_on_a_public_route(self):
		"""`sketch/www/sketch.py` PUBLIC_PATHS, and the same paths in
		`hooks.py` `website_route_rules`. Either one missing is a 404 or a
		redirect for the page the front door points at."""
		for path in ("/feed", "/about"):
			response = utils.request("GET", path)

			self.assertEqual(response.status_code, 200, path)
			for mark in BUNDLE_MARKS:
				self.assertIn(mark, response.text, f"{path} lost {mark}")

	def test_the_viewer_still_serves_a_stranger(self):
		"""Do not break this. A public link works with no session."""
		utils.require_runtime()
		user = utils.make_user("spa", "d2tspa")
		self.addCleanup(utils.drop_user, user)

		doc = utils.make_prototype(
			user,
			"d2t-spa-public",
			files={"src/App.vue": "<template><h1>hello</h1></template>\n"},
			is_public=True,
		)
		self.addCleanup(utils.drop_prototype, doc.name)

		path = f"/u/{utils.username_of(user)}/{doc.slug}"
		response = utils.request("GET", path)

		self.assertEqual(response.status_code, 200)
