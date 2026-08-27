# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""Trap 8: a Sketch Token opens `/mcp` and nothing else.

Signup is open to anyone, so a token that reached more than `/mcp` would hand
every new account the rest of the site: Desk, the REST API, every other user's
web pages. That one path check is the whole security argument for `Sketch
Token` over Frappe's `api_key`.

Two layers of test:

- `validate_sketch_token` on its own, with a faked request path. It runs
  without a web server, so this layer never skips.
- The live server, which is the only place the hook runs the way it ships.
"""

import unittest
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from sketch import auth
from sketch.sketch.doctype.sketch_token.sketch_token import get_or_create
from sketch.tests import utils

#: Every path a token must not open. `/mcp` is the one that is missing.
FORBIDDEN_PATHS = (
	"/api/method/frappe.ping",
	"/api/method/frappe.auth.get_logged_user",
	"/api/method/frappe.client.get_list",
	"/api/resource/User",
	"/app",
	"/app/user",
	"/",
	"/u/someone/some-slug",
	"/sketch",
	"/mcp/extra",
	"/mcpx",
	"/api/method/sketch.api.list_prototypes",
)


class FakeRequest:
	"""The one attribute `auth._is_mcp_path` reads."""

	def __init__(self, path: str):
		self.path = path


class TestAuthTokenScope(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.user = utils.make_user("token", "d2ttoken")
		cls.addClassCleanup(utils.drop_user, cls.user)
		cls.token = get_or_create(cls.user)
		frappe.db.commit()

	# ------------------------------------------------- the function on its own

	def as_guest(self, path: str, header: str) -> str:
		"""Run the hook as Guest on `path`. Returns the session user after it.

		The session user is put back either way, so one case cannot change what
		the next one sees.
		"""
		before = frappe.session.user
		with patch.object(frappe.local, "request", FakeRequest(path), create=True):
			with patch.object(frappe, "get_request_header", lambda key, default=None: header):
				frappe.set_user("Guest")
				try:
					auth.validate_sketch_token()
					return frappe.session.user
				finally:
					frappe.set_user(before)

	def resolve_on(self, path: str) -> str:
		"""Run the hook with this user's real token on `path`."""
		return self.as_guest(path, f"Bearer {self.token}")

	def test_the_hook_refuses_every_path_but_mcp(self):
		for path in FORBIDDEN_PATHS:
			with self.subTest(path=path):
				self.assertEqual(
					self.resolve_on(path),
					"Guest",
					f"a Sketch Token authenticated on {path}",
				)

	def test_the_hook_accepts_mcp(self):
		"""The control. Without it the test above passes on a dead hook."""
		for path in ("/mcp", "/mcp/"):
			with self.subTest(path=path):
				self.assertEqual(self.resolve_on(path), self.user)

	def test_the_hook_ignores_a_wrong_token(self):
		self.assertEqual(self.as_guest("/mcp", "Bearer sk_not-a-real-token"), "Guest")

	def test_the_hook_ignores_a_header_that_is_not_a_sketch_token(self):
		for header in ("", "token abc:def", "Basic Zm9vOmJhcg==", "Bearer ", f"Bearer x{self.token}"):
			with self.subTest(header=header):
				self.assertEqual(self.as_guest("/mcp", header), "Guest")

	# ------------------------------------------------------ the live server

	def bearer(self) -> dict:
		return {"Authorization": f"Bearer {self.token}"}

	def test_the_live_server_refuses_the_token_off_mcp(self):
		"""Core raises AuthenticationError for a header nothing authenticated."""
		utils.require_webserver()
		for path in FORBIDDEN_PATHS:
			with self.subTest(path=path):
				response = utils.request("GET", path, headers=self.bearer())
				self.assertEqual(
					response.status_code,
					401,
					f"{path} answered {response.status_code} to a Sketch Token",
				)

	def test_the_live_server_never_names_the_user_off_mcp(self):
		"""The direct read: the token must not log anyone in outside /mcp."""
		utils.require_webserver()
		response = utils.request(
			"GET", "/api/method/frappe.auth.get_logged_user", headers=self.bearer()
		)
		self.assertEqual(response.status_code, 401)
		self.assertNotIn(self.user, response.text)

	def test_the_live_server_accepts_the_token_on_mcp(self):
		"""The control, over HTTP. A 401 here would hide every failure above."""
		utils.require_webserver()
		response = utils.request(
			"POST",
			"/mcp",
			headers={**self.bearer(), "Content-Type": "application/json"},
			json={"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}},
		)
		self.assertEqual(response.status_code, 200, response.text[:400])
		self.assertEqual(response.json()["id"], 1)

	def test_the_live_server_refuses_mcp_without_a_token(self):
		utils.require_webserver()
		response = utils.request(
			"POST",
			"/mcp",
			headers={"Content-Type": "application/json"},
			json={"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}},
		)
		self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
	unittest.main()
