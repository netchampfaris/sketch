# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""`/about` answers, signed in or not.

It replaces `/help`, which was a server-rendered symptom list: four client
config keys, three `/mcp` error codes and a claude.ai warning. The page a
stranger follows off the feed has one job, which is to get them signed in and
connected, so /about is three steps and nothing else
(`frontend/src/pages/AboutScreen.vue`).

It is a route of the SPA, not a `www` template, so the cases here check the
routing: the path resolves, and a Guest is served the bundle rather than
bounced to /login. The markup is the screen's own.

`www` routing only runs inside a real request, so every case drives the live
server.
"""

from frappe.tests import IntegrationTestCase

from sketch.tests import utils

#: Proof the SPA bundle was served. Both come from sketch/www/sketch.html.
BUNDLE_MARKS = ('id="app"', "/assets/sketch/frontend/")


class TestAboutPage(IntegrationTestCase):
	def setUp(self):
		utils.require_webserver()

	def test_the_route_resolves(self):
		"""`website_route_rules` has to name every SPA route, or a direct load
		of it is a 404 (`sketch/hooks.py`)."""
		self.assertEqual(utils.request("GET", "/about").status_code, 200)

	def test_a_guest_gets_the_page(self):
		"""A Guest must not be bounced to /login: the page explains the login.
		Half of the reason a person is stuck is that they have not signed in
		yet (review 8.1)."""
		body = utils.request("GET", "/about").text

		for mark in BUNDLE_MARKS:
			self.assertIn(mark, body)

	def test_the_old_help_route_is_gone(self):
		"""One page, not two. /help was deleted, not left as a second copy that
		drifts from this one."""
		self.assertEqual(utils.request("GET", "/help").status_code, 404)

	def test_the_login_page_points_here(self):
		"""/login is the one page left on the web template, and its bar action
		is the way to read what Sketch is before signing in."""
		self.assertIn('href="/about"', utils.request("GET", "/login").text)
