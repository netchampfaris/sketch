# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""`/login` is Sketch's page, not core's.

Core's page opened with "Sign In. Welcome! Please sign in to continue." over a
"Login with GitHub" button, and never said that the same button also makes the
account. It also printed "Signups have been disabled for this website.", which
is false here: the GitHub Social Login Key carries `sign_ups = "Allow"` and
`provider_allows_signup` reads the key before Website Settings, so the button
does create accounts (review 8.2).

`sketch/www/login.html` and `sketch/www/login.py` replace it.
`TemplatePage.set_template_path` walks `reversed(frappe.get_active_apps())`
(`frappe/website/page_renderers/template_page.py:51`), so the override only
happens inside a real request. Every case here drives the live server.

The login decision itself stays in core: `get_context` calls core's, so the
OAuth URLs and the redirect for a visitor who is already signed in are
unchanged.
"""

import re
from urllib.parse import urlparse

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils.password import get_decrypted_password

from sketch.tests import utils

#: Copy that only Sketch's template has.
SKETCH_MARKS = (
	"Sketch renders frappe-ui prototypes that your own agent writes over MCP.",
	"What is Sketch?",
	'class="sk-shell"',
)

#: Core's login page, mark by mark. Every one of these used to be in the DOM.
#: `frappe/www/login.html`: the header at :109, the email field at :15, the
#: password field at :26, the forgot-password link at :37, the signup line at
#: :146.
CORE_MARKS = (
	"Welcome! Please sign in to continue.",
	'id="login_email"',
	'id="login_password"',
	"Forgot password?",
	"Signups have been disabled for this website.",
)

#: The one Social Login Key Sketch ships (`sketch/install.py`).
GITHUB = "github"

TITLE = re.compile(r"<title>(.*?)</title>", re.DOTALL)


def github_credentials() -> tuple:
	"""The GitHub key's live credentials, as core reads them."""
	if not frappe.db.exists("Social Login Key", GITHUB):
		return 0, "", ""

	enabled, client_id = frappe.db.get_value(
		"Social Login Key", GITHUB, ["enable_social_login", "client_id"]
	)
	secret = get_decrypted_password("Social Login Key", GITHUB, "client_secret", raise_exception=False)
	return enabled, client_id or "", secret or ""


class TestLoginPage(IntegrationTestCase):
	def setUp(self):
		utils.require_webserver()

	def get_login(self, **kwargs):
		response = utils.request("GET", "/login", **kwargs)
		self.assertEqual(response.status_code, 200, response.text[:400])
		return response.text

	# ---------------------------------------------------------- the page

	def test_a_guest_gets_the_page(self):
		"""The one route a signed-out visitor is sent to. It must answer, and
		it must answer with a page, not a redirect."""
		self.assertIn('class="sk-shell"', self.get_login())

	def test_the_page_says_what_sketch_is(self):
		"""One line about the product, before the button. Core's page said
		nothing about what the visitor is signing in to."""
		body = self.get_login()

		for mark in SKETCH_MARKS:
			self.assertIn(mark, body)

	def test_no_core_login_markup_is_left_in_the_dom(self):
		"""`disable_user_pass_login` is 1, so none of core's fields could ever
		be submitted, and the signup line is untrue on this site. Hidden is not
		enough: a page reader and a password manager both read the DOM."""
		body = self.get_login()

		for mark in CORE_MARKS:
			self.assertNotIn(mark, body, f"core's login page still prints {mark!r}")

	def test_the_title_is_sentence_case(self):
		"""Every other header in Sketch is sentence case (review 8.3). Core's
		was "Login"."""
		match = TITLE.search(self.get_login())
		self.assertIsNotNone(match, "the page has no title")
		self.assertIn("Sign in", match.group(1))
		self.assertNotIn("Login", match.group(1))

	def test_the_page_holds_no_solid_button(self):
		"""The standing rule (commit 54f7fdc). Core's login buttons carry
		`data-variant="solid"`, and inheriting one of them would put the only
		solid button in Sketch on the first screen a visitor sees."""
		self.assertNotIn('data-variant="solid"', self.get_login())

	def test_the_page_offers_a_way_back_out(self):
		"""A visitor who is not ready to sign in has somewhere to go. The
		marketing page is the only other Guest route."""
		self.assertIn('href="/"', self.get_login())

	# ------------------------------------------------------ the provider

	def test_the_button_says_it_also_makes_the_account(self):
		"""The label is "Continue with GitHub", not "Login with GitHub". It
		signs an existing account in and creates a new one, and "Login" is not
		a verb in this app: the account menu says "Log out" (review 8.3)."""
		self.lend_github_credentials()

		body = self.get_login()

		self.assertIn("Continue with GitHub", body)
		self.assertNotIn("Login with GitHub", body)

	def test_the_button_goes_to_the_providers_authorize_url(self):
		"""The label is Sketch's; the href is core's, unchanged."""
		self.lend_github_credentials()

		self.assertIn("github.com/login/oauth/authorize", self.get_login())

	def test_a_configured_provider_hides_the_not_set_up_block(self):
		"""One state at a time. Both would read as a broken page."""
		self.lend_github_credentials()

		self.assertNotIn("Sign-in is not set up yet", self.get_login())

	def test_a_site_with_no_credentials_says_so(self):
		"""The honest empty state. Core drops a provider with no credentials
		(`frappe/www/login.py:70-92`), and an empty card under the heading reads
		as a page that failed to load."""
		enabled, client_id, secret = github_credentials()
		if enabled and client_id and secret:
			self.skipTest("this site has GitHub credentials, so the empty state cannot be reached")

		body = self.get_login()

		self.assertIn("Sign-in is not set up yet", body)
		self.assertNotIn("Continue with", body)

	# ------------------------------------------- what core still decides

	def test_a_signed_in_visitor_is_sent_where_they_were_going(self):
		"""`get_context` calls core's, so both the redirect and the
		`redirect-to` handling are core's, unchanged. Losing them would leave a
		signed-in user staring at a sign-in button, and would break the bounce
		that `sketch/www/sketch.py` sends a Guest through."""
		user = utils.make_user("login", "d2tlogin")
		self.addCleanup(utils.drop_user, user)

		response = utils.request(
			"GET", "/login?redirect-to=%2Fsettings", headers=utils.api_auth_header(user)
		)

		self.assertIn(response.status_code, (301, 302, 303, 307))
		# Core resolves the target against the request host before it
		# redirects (`sanitize_redirect`, `frappe/www/login.py:203-225`), so
		# the header is an absolute URL and never the bare path that was
		# asked for. Read it apart: the host proves the redirect stays on
		# this site, the path proves it kept where the visitor was going.
		location = urlparse(response.headers["Location"])
		self.assertEqual(location.netloc, utils.site_host())
		self.assertEqual(location.path, "/settings")

	# --------------------------------------------------------- fixtures

	def lend_github_credentials(self) -> None:
		"""Give the GitHub key a client id and secret for one case.

		`sketch/install.py` creates the key disabled and never writes a
		credential, so a fresh site has no provider and the button cannot be
		asserted at all. The values are fake: nothing here reaches GitHub, and
		the template only prints a label and an href.

		The write is committed, because the web server holds its own database
		connection. The restore is registered before the write, so it runs even
		when the request that follows fails.
		"""
		if not frappe.db.exists("Social Login Key", GITHUB):
			self.skipTest("this site has no GitHub Social Login Key; run sketch's install")

		before = github_credentials()
		self.addCleanup(self.restore_github_credentials, before)
		self.write_github_credentials(1, "d2t-client-id", "d2t-client-secret")

	def restore_github_credentials(self, before: tuple) -> None:
		self.write_github_credentials(*before)

	def write_github_credentials(self, enabled, client_id: str, secret: str) -> None:
		doc = frappe.get_doc("Social Login Key", GITHUB)
		# The flag goes down first in the restore direction: `validate` refuses
		# an enabled key with no credential
		# (`frappe/integrations/doctype/social_login_key/social_login_key.py:88-93`).
		doc.enable_social_login = enabled
		doc.client_id = client_id
		doc.client_secret = secret
		doc.save(ignore_permissions=True)
		frappe.db.commit()
