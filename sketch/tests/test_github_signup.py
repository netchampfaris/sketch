# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""A GitHub login must be able to make a Sketch user.

Frappe builds the User for a social sign-in at `frappe/utils/oauth.py:278-310`
and never sets `username`. Core derives one with `frappe.scrub(first_name)`
(`frappe/core/doctype/user/user.py:766-768`), which writes underscores, and the
Sketch rules then refuse it. The person reads a 417 page with a traceback.

`sketch.oauth_hooks.set_username_for_social_signup` fills the field on
`before_insert`. These tests lock four things:

- the derivation, one case per rule it has to obey
- the whole insert path, built the way `oauth.py` builds it
- an existing user, whose username a later GitHub sign-in must not change

No Social Login Key record is needed. `User.set_social_login_userid` only
appends a child row, so the tests reach the same document core would insert
without the OAuth handshake.
"""

import frappe
from frappe.tests import IntegrationTestCase

from sketch import oauth_hooks
from sketch.tests import utils
from sketch.user_hooks import USERNAME_MAX_LENGTH, USERNAME_MIN_LENGTH, USERNAME_PATTERN, check_format

#: A GitHub login of 40 characters. It has to come back cut to 30.
LONG_LOGIN = "d" * 40

#: The seed and the answer, one pair per rule in the derivation.
DERIVED = (
	("FarisAnsari", "farisansari"),
	("foo-bar", "foo-bar"),
	("7ktn", "u-7ktn"),
	("", "sketch-user"),
	("Faris Ansari", "faris-ansari"),
	("Faris.Ansari_ok", "faris-ansari-ok"),
	("--foo--bar--", "foo-bar"),
	("!!!", "sketch-user"),
	("Ünïcödé", "n-c-d"),
)


class TestGithubSignup(IntegrationTestCase):
	# ------------------------------------------------------- the derivation

	def test_a_login_becomes_a_legal_name(self):
		for seed, expected in DERIVED:
			with self.subTest(seed=seed):
				self.assertEqual(oauth_hooks.derive_username(seed), expected)

	def test_a_short_login_is_padded(self):
		"""`jq` is two characters. The rules need three."""
		value = oauth_hooks.derive_username("jq")
		self.assertEqual(len(value), USERNAME_MIN_LENGTH)
		self.assertEqual(value, "jq0")
		check_format(value)

	def test_a_long_login_is_cut_to_the_maximum(self):
		value = oauth_hooks.derive_username(LONG_LOGIN)
		self.assertEqual(len(value), USERNAME_MAX_LENGTH)
		check_format(value)

	def test_every_derived_name_passes_the_sketch_rules(self):
		"""The point of the hook: no login string can make it throw."""
		seeds = [
			None,
			"",
			"   ",
			"-",
			"---",
			"7",
			"0000",
			"jq",
			LONG_LOGIN,
			"-".join(["x"] * 40),
			"Faris Ansari",
			"a" * 29 + "-b",
			"用户名",
			"a@b.com",
			"__init__",
			"UPPER CASE NAME",
		]
		for seed in seeds:
			with self.subTest(seed=seed):
				value = oauth_hooks.derive_username(seed)
				self.assertTrue(USERNAME_PATTERN.match(value), value)
				check_format(value)

	# -------------------------------------------------------- the collision

	def test_a_taken_name_gets_a_counter(self):
		taken = utils.make_user("octocat", "octocat")
		self.addCleanup(utils.drop_user, taken)

		self.assertEqual(oauth_hooks.unique_username("Octocat"), "octocat-2")

	def test_a_counter_keeps_the_name_inside_the_maximum(self):
		"""A name already at the limit must lose characters, not gain them."""
		value = oauth_hooks.with_suffix("d" * USERNAME_MAX_LENGTH, "-2")
		self.assertEqual(len(value), USERNAME_MAX_LENGTH)
		check_format(value)

	# ---------------------------------------------------- the whole path

	def test_a_github_signup_inserts(self):
		"""The document `frappe/utils/oauth.py:287-310` builds, inserted.

		The display name holds a space. That is the case that throws today,
		because `frappe.scrub` turns the space into an underscore.
		"""
		email = "d2t-ghfull@example.com"
		utils.drop_user(email)
		self.addCleanup(utils.drop_user, email)

		doc = frappe.new_doc("User")
		doc.update(
			{
				"doctype": "User",
				"first_name": "D2t Github",
				"last_name": "Signup",
				"email": email,
				"enabled": 1,
				"new_password": frappe.generate_hash(),
				"user_type": "Website User",
				"user_image": "https://avatars.githubusercontent.com/u/1",
			}
		)
		doc.set_social_login_userid("github", userid="4242", username="D2t-Github-Signup")
		doc.append("roles", {"role": utils.TEST_ROLE})
		doc.flags.ignore_permissions = True
		doc.flags.no_welcome_mail = True
		doc.insert()

		self.assertEqual(doc.username, "d2t-github-signup")
		check_format(doc.username)
		self.assertEqual(frappe.db.get_value("User", email, "username"), "d2t-github-signup")

	def test_a_github_signup_with_no_login_uses_the_display_name(self):
		"""A provider that sends no login still gives a legal username."""
		email = "d2t-ghname@example.com"
		utils.drop_user(email)
		self.addCleanup(utils.drop_user, email)

		doc = frappe.new_doc("User")
		doc.update(
			{
				"first_name": "D2t Display Name",
				"email": email,
				"enabled": 1,
				"user_type": "Website User",
			}
		)
		doc.set_social_login_userid("github", userid="4343")
		doc.append("roles", {"role": utils.TEST_ROLE})
		doc.flags.ignore_permissions = True
		doc.flags.no_welcome_mail = True
		doc.insert()

		self.assertEqual(doc.username, "d2t-display-name")

	# ------------------------------------------------- what must not change

	def test_the_hook_leaves_a_user_that_has_no_social_login(self):
		"""A Desk-created user must reach core untouched."""
		doc = frappe.new_doc("User")
		doc.first_name = "D2t No Social"
		doc.email = "d2t-ghnosocial@example.com"

		oauth_hooks.set_username_for_social_signup(doc)

		self.assertFalse(doc.username)

	def test_the_hook_leaves_a_username_that_is_already_set(self):
		doc = frappe.new_doc("User")
		doc.first_name = "D2t Already Named"
		doc.email = "d2t-ghnamed@example.com"
		doc.username = "d2tghnamed"
		doc.set_social_login_userid("github", userid="4444", username="Something-Else")

		oauth_hooks.set_username_for_social_signup(doc)

		self.assertEqual(doc.username, "d2tghnamed")

	def test_an_existing_user_keeps_the_username_after_a_github_sign_in(self):
		"""The second half of `update_oauth_user`: the row is added on save."""
		email = utils.make_user("ghold", "d2tghold")
		self.addCleanup(utils.drop_user, email)

		doc = frappe.get_doc("User", email)
		doc.set_social_login_userid("github", userid="4545", username="Totally-Other-Login")
		doc.flags.ignore_permissions = True
		doc.save()

		self.assertEqual(frappe.db.get_value("User", email, "username"), "d2tghold")
