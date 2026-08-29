# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""`/help` answers, signed in or not.

Sketch linked out to nothing. A `grep` over `frontend/src` found one external
URL, and it was inside a config snippet, so a user whose agent stayed quiet had
nowhere to go (review 3.12). `sketch/www/help.py` and `sketch/www/help.html`
are that page, and the account menu now points at it.

A Guest reaches it too. Half of the reason a person is stuck is that they have
not signed in yet, and a page that asks for a login before it explains the
login is the problem this sweep is fixing (review 8.1).

`www` routing only runs inside a real request, so every case drives the live
server.
"""

import frappe
from frappe.tests import IntegrationTestCase

from sketch.tests import utils

#: The three walls the page exists to name (`sketch/mcp/http.py`, ERRORS).
ERROR_NAMES = ("no_credentials", "wrong_auth_scheme", "invalid_token")


class TestHelpPage(IntegrationTestCase):
	def setUp(self):
		utils.require_webserver()

	def get_help(self, **kwargs) -> str:
		response = utils.request("GET", "/help", **kwargs)
		self.assertEqual(response.status_code, 200, response.text[:400])
		return response.text

	# --------------------------------------------------------- who gets it

	def test_a_guest_gets_the_page(self):
		"""The route used to be a 404. A Guest must not be bounced to /login:
		the page explains the login."""
		self.assertIn("Connect your agent", self.get_help())

	def test_a_signed_in_user_gets_the_page(self):
		"""The account menu points here, so the signed-in read is the one most
		people take."""
		user = utils.make_user("help", "d2thelp")
		self.addCleanup(utils.drop_user, user)

		self.assertIn("Connect your agent", self.get_help(headers=utils.api_auth_header(user)))

	def test_the_bar_offers_the_action_the_reader_can_take(self):
		"""One bar, two states, same height. A Guest is offered the way in, a
		signed-in reader the way back."""
		user = utils.make_user("helpbar", "d2thelpbar")
		self.addCleanup(utils.drop_user, user)

		guest = self.get_help()
		self.assertIn('href="/login"', guest)
		self.assertNotIn("Open Sketch", guest)

		signed_in = self.get_help(headers=utils.api_auth_header(user))
		self.assertIn("Open Sketch", signed_in)

	# ------------------------------------------------------- what it says

	def test_the_page_names_this_sites_own_endpoint(self):
		"""`get_url("/mcp")` on the site under test, never a hard-coded host.
		A reader pastes this line into their client.

		`site_config.host_name` wins inside `get_url`
		(`frappe/utils/data.py:1965-1970`), so this process and the web server
		compute the same string from one setting.
		"""
		self.assertIn(frappe.utils.get_url("/mcp"), self.get_help())

	def test_the_page_explains_every_error_the_endpoint_returns(self):
		"""The `/mcp` error contract, in words. A client that hides the JSON
		body leaves the reader with nothing else."""
		body = self.get_help()

		for name in ERROR_NAMES:
			self.assertIn(name, body)

	def test_the_page_is_the_sketch_shell(self):
		"""Same chrome as `/` and `/login`, so the three read as one product."""
		self.assertIn('class="sk-shell"', self.get_help())

	def test_the_page_holds_no_solid_button(self):
		"""The standing rule (commit 54f7fdc)."""
		self.assertNotIn('data-variant="solid"', self.get_help())

	# --------------------------------------------------- who points at it

	def test_the_marketing_page_links_to_it(self):
		"""A dead link in the footer is worse than no link. Both Guest pages
		carry one, so both are checked against the live route."""
		self.assertIn('href="/help"', utils.request("GET", "/").text)

	def test_the_login_page_links_to_it(self):
		self.assertIn('href="/help"', utils.request("GET", "/login").text)
