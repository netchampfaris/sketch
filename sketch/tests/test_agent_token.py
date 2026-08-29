# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The token the Settings screen shows must be the token that works.

`get_agent_token` mints the row on first read, and it is a GET. Core rolls a
GET back (`frappe/app.py:404-407`): it commits only for an unsafe HTTP method
or when `flags.commit` is set. So the screen used to show a token that never
landed, the next read minted a different one, and nothing the user pasted
could authenticate.

Only a real request reproduces that, so every case here drives the live
server. An in-process call shares the test's own transaction and passes either
way.
"""

import json

from frappe.tests import IntegrationTestCase

from sketch.tests import utils

TOKEN_METHOD = "/api/v2/method/sketch.api.get_agent_token"
SESSION_METHOD = "/api/v2/method/sketch.api.get_session"


class TestAgentTokenPersists(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_webserver()
		# A brand new account, so the first read is the one that mints.
		cls.user = utils.make_user("tok", "d2ttok")
		cls.addClassCleanup(utils.drop_user, cls.user)
		cls.auth = utils.api_auth_header(cls.user)

	def read(self, path: str) -> dict:
		response = utils.request("GET", path, headers=self.auth)
		self.assertEqual(response.status_code, 200, response.text[:400])
		return response.json()["data"]

	def test_the_token_survives_the_read_that_minted_it(self):
		"""Two reads, one token. The first read used to be rolled back."""
		first = self.read(TOKEN_METHOD)["token"]
		second = self.read(TOKEN_METHOD)["token"]

		self.assertTrue(first.startswith("sk_"))
		self.assertEqual(first, second)

	def test_the_minted_token_opens_mcp(self):
		"""The point of the screen. A copied token must authenticate."""
		token = self.read(TOKEN_METHOD)["token"]

		response = utils.request(
			"POST",
			"/mcp",
			headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
			data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}}),
		)

		self.assertEqual(response.status_code, 200, response.text[:400])
		self.assertEqual(response.json()["result"], {})

	def test_the_session_sees_the_token_the_screen_showed(self):
		"""`has_token` used to stay false however often the screen was opened."""
		self.read(TOKEN_METHOD)

		self.assertTrue(self.read(SESSION_METHOD)["has_token"])
