# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""A dead token must stop reporting a live agent.

`regenerate` wrote the new secret and left `last_used` where it was. Settings
reads that field and prints "Last agent request: 2 minutes ago"
(`frontend/src/pages/SettingsScreen.vue`), so the one screen a user opens to
fix a broken connection told them the connection was fine. Every agent holding
the old token gets a 401 from `sketch.auth` the moment the row is rewritten
(review 2.3).

`regenerate` now clears the field with the same save
(`sketch/sketch/doctype/sketch_token/sketch_token.py:69-86`). The next good
`/mcp` request stamps it again.

The row is rewritten, never deleted. `Sketch Token` is named by its `user`
field, and the `if_owner` rules read `owner`, so a delete-and-insert would take
the row's identity with it.
"""

import frappe
from frappe.tests import IntegrationTestCase, set_user
from frappe.utils import add_to_date, now_datetime

from sketch import api
from sketch.sketch.doctype.sketch_token import sketch_token
from sketch.tests import utils


class TestTokenRegenerate(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.user = utils.make_user("regen", "d2tregen")
		cls.addClassCleanup(utils.drop_user, cls.user)

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		super().tearDownClass()

	def setUp(self):
		"""One token, used two minutes ago. That is the state the screen shows
		as connected."""
		self.token = sketch_token.get_or_create(self.user)
		frappe.db.set_value("Sketch Token", self.user, "last_used", add_to_date(now_datetime(), minutes=-2))
		frappe.db.commit()

	def last_used(self):
		return frappe.db.get_value("Sketch Token", self.user, "last_used")

	def session(self) -> dict:
		with set_user(self.user):
			return api.get_session()

	# -------------------------------------------------------- the clearing

	def test_the_fixture_starts_out_connected(self):
		"""Without this every case below passes on a field that was already
		empty."""
		self.assertIsNotNone(self.last_used())
		self.assertIsNotNone(self.session()["last_used"])

	def test_regenerating_clears_the_connection_stamp(self):
		"""The regression itself."""
		sketch_token.regenerate(self.user)

		self.assertIsNone(self.last_used())

	def test_settings_stops_claiming_an_agent_is_connected(self):
		"""The surface the user reads. `get_session` feeds the Settings line,
		and both of its fields have to go quiet together: the pretty string is
		what is printed, the raw one is what the screen branches on."""
		sketch_token.regenerate(self.user)

		state = self.session()
		self.assertIsNone(state["last_used"])
		self.assertIsNone(state["last_used_pretty"])

	def test_the_screen_still_knows_a_token_exists(self):
		"""Only the connection state is cleared. `has_token` drives the block
		that shows the token, and clearing it would hide the new one."""
		sketch_token.regenerate(self.user)

		self.assertTrue(self.session()["has_token"])

	def test_the_whitelisted_method_clears_it_too(self):
		"""`regenerate_agent_token` is what the button calls. The test above
		reaches past it."""
		with set_user(self.user):
			api.regenerate_agent_token()

		self.assertIsNone(self.last_used())

	# ---------------------------------------------------- the token itself

	def test_regenerating_writes_a_new_secret(self):
		fresh = sketch_token.regenerate(self.user)

		self.assertTrue(fresh.startswith(sketch_token.TOKEN_PREFIX))
		self.assertNotEqual(fresh, self.token)
		self.assertEqual(sketch_token.get_token(self.user), fresh)

	def test_the_old_token_authenticates_nobody(self):
		"""Why the stamp is stale: the agent that set it is locked out."""
		fresh = sketch_token.regenerate(self.user)

		self.assertIsNone(sketch_token.resolve(self.token))
		self.assertEqual(sketch_token.resolve(fresh), self.user)

	def test_the_row_is_rewritten_and_never_replaced(self):
		"""A write, never a delete. The row is named by its `user` field and
		the `if_owner` rules read `owner`, so a fresh row would change both."""
		before = frappe.db.get_value("Sketch Token", self.user, ["name", "owner", "creation"], as_dict=True)

		sketch_token.regenerate(self.user)

		after = frappe.db.get_value("Sketch Token", self.user, ["name", "owner", "creation"], as_dict=True)
		self.assertEqual(after, before)

	def test_a_user_with_no_token_gets_one_with_no_stamp(self):
		"""Regenerate on an account that never connected. It mints, and the
		new row reports no agent."""
		other = utils.make_user("regennew", "d2tregennew")
		self.addCleanup(utils.drop_user, other)

		fresh = sketch_token.regenerate(other)

		self.assertTrue(fresh.startswith(sketch_token.TOKEN_PREFIX))
		self.assertIsNone(frappe.db.get_value("Sketch Token", other, "last_used"))
