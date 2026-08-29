# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""Who gets the SPA bundle.

A signed-out visitor used to download the whole bundle, watch it call
`get_session`, and only then bounce to /login. `sketch/www/sketch.py` now
stops that at the server (problem B4).

The site root answers a Guest with the marketing page instead of a redirect
(problem 8.1). It is the one path that does. A deep link such as /settings is
still a bounce, and either answer keeps the bundle away from a Guest, which is
what B4 asked for.

The Viewer is a different renderer and must not move. A public Prototype
belongs to whoever holds the link, signed in or not (spec 6.3).
"""

from frappe.tests import IntegrationTestCase

from sketch.tests import utils

#: Proof the bundle was served. Both come from sketch/www/sketch.html.
BUNDLE_MARKS = ('id="app"', "/assets/sketch/frontend/")


class TestSpaAccess(IntegrationTestCase):
	def setUp(self):
		utils.require_webserver()

	def test_a_guest_at_the_root_gets_the_marketing_page(self):
		"""The root reads as a product page, not as a login form.

		This test asserted a 301 to /login until problem 8.1. A visitor was
		asked for a GitHub account before a single sentence said what Sketch
		does, so `_guest_context` now swaps `context.template` for the
		marketing page on the root paths only.
		"""
		response = utils.request("GET", "/")

		self.assertEqual(response.status_code, 200)
		# The sign-in route stays reachable from the page. It is the only way
		# in, so a marketing page that loses it is worse than the redirect was.
		self.assertIn('href="/login"', response.text)
		self.assertIn("Sketch has no editor", response.text)

	def test_a_guest_at_index_gets_the_same_page(self):
		"""`/index` reaches the same renderer, so it must not bounce either."""
		response = utils.request("GET", "/index")

		self.assertEqual(response.status_code, 200)
		self.assertIn("Sketch has no editor", response.text)

	def test_a_guest_keeps_the_page_they_asked_for(self):
		"""The bounce carries the path back, so login returns them to it."""
		response = utils.request("GET", "/settings")

		self.assertEqual(response.status_code, 301)
		self.assertEqual(response.headers["Location"], "/login?redirect-to=%2Fsettings")

	def test_a_guest_never_downloads_the_bundle(self):
		"""The point of the guard. The marketing body must carry no SPA."""
		response = utils.request("GET", "/")

		for mark in BUNDLE_MARKS:
			self.assertNotIn(mark, response.text)

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
