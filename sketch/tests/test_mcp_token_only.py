# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""`/mcp` takes a Sketch Token and nothing else.

The endpoint used to accept any signed-in session, so a session cookie alone
drove the whole tool surface. The SPA never calls `/mcp`, so that capability
bought nothing, and it let any same-origin page, the Viewer included, run every
tool with the visitor's cookie. The cross-site half was already closed by
`SameSite=Lax` and by CORS being off.

The gate is two lines in two files. `sketch.auth.validate_sketch_token` sets
`TOKEN_AUTH_FLAG` when a Bearer token names the user, and
`sketch.mcp.http.McpPageRenderer.render` answers `no_credentials` without it.

Two layers of test, the same shape `test_auth_scope.py` uses:

- the hook on its own, with a faked request path. It never skips.
- the live server, the only place a real `sid` cookie meets a real renderer.

`test_mcp_errors.py` owns the error contract itself and is not repeated here.
"""

import json
import unittest
from unittest.mock import patch

import frappe
from frappe.sessions import delete_session
from frappe.tests import IntegrationTestCase

from sketch import auth
from sketch.mcp import http
from sketch.sketch.doctype.sketch_token.sketch_token import get_or_create
from sketch.tests import utils

#: One valid JSON-RPC message. Every case sends the same body, so the status is
#: about the credential and nothing else.
PING = {"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}}

#: The `frappe.local` names `LoginManager` writes over. Each one is put back,
#: or the rest of the file runs inside the fixture's session.
BORROWED_LOCALS = (
	"request",
	"cookie_manager",
	"login_manager",
	"session",
	"session_obj",
	"form_dict",
	"response",
)


class FakeRequest:
	"""The one attribute `auth._is_mcp_path` reads."""

	def __init__(self, path: str):
		self.path = path


def open_session(user: str) -> str:
	"""Start a real session for one test user. Returns its `sid`.

	The three calls `bench browse --user X --sid` makes
	(`frappe/commands/site.py:1352-1356`). Nothing cheaper works: the web
	server resumes the session from redis and the `Sessions` row, so both must
	exist before the request, and that server holds its own connection.

	A fresh session carries no `csrf_token`: it is generated on first read
	(`frappe/sessions.py:197-205`), which a boot does and this does not. So
	`validate_csrf_token` leaves the POST alone (`frappe/auth.py:86-98`) and
	the case reaches the renderer, which is what it is about.
	"""
	from frappe.auth import CookieManager, LoginManager

	borrowed = {name: getattr(frappe.local, name, None) for name in BORROWED_LOCALS}
	try:
		frappe.utils.set_request(path="/")
		# `Session` reads `sid` from `form_dict` first (`frappe/sessions.py:222`).
		# An empty one makes the resume land on Guest, whatever ran before.
		frappe.local.form_dict = frappe._dict()
		frappe.local.cookie_manager = CookieManager()
		frappe.local.login_manager = LoginManager()
		frappe.local.login_manager.login_as(user)
		sid = frappe.session.sid
	finally:
		for name, value in borrowed.items():
			setattr(frappe.local, name, value)

	frappe.db.commit()
	return sid


class TestMcpTakesTokensOnly(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.user = utils.make_user("gate", "d2tgate")
		cls.addClassCleanup(utils.drop_user, cls.user)
		cls.token = get_or_create(cls.user)
		frappe.db.commit()

		cls.sid = open_session(cls.user)
		cls.addClassCleanup(delete_session, cls.sid)

	# ------------------------------------------------- the hook on its own

	def run_hook(self, header: str, as_user: str = "Guest") -> bool:
		"""Run the hook on `/mcp` as `as_user`. Returns the flag it left.

		The flag and the session user are put back either way, so one case
		cannot change what the next one sees.
		"""
		before = frappe.session.user
		with patch.object(frappe.local, "request", FakeRequest("/mcp"), create=True):
			with patch.object(frappe, "get_request_header", lambda key, default=None: header):
				frappe.set_user(as_user)
				try:
					auth.validate_sketch_token()
					return bool(frappe.local.flags.get(auth.TOKEN_AUTH_FLAG))
				finally:
					frappe.local.flags.pop(auth.TOKEN_AUTH_FLAG, None)
					frappe.set_user(before)

	def test_a_good_token_sets_the_flag(self):
		"""The renderer reads this flag, so a missing one locks the endpoint."""
		self.assertTrue(self.run_hook(f"Bearer {self.token}"))

	def test_a_missing_header_sets_no_flag(self):
		self.assertFalse(self.run_hook(""))

	def test_a_session_that_is_already_signed_in_sets_no_flag(self):
		"""The hook leaves a cookie-authenticated request alone, so a token
		cannot swap the identity core already resolved. The flag stays unset,
		and the renderer refuses the request on it."""
		self.assertFalse(self.run_hook(f"Bearer {self.token}", as_user=self.user))

	# ---------------------------------------------------- the live server

	def post(self, headers: dict | None = None, path: str = "/mcp"):
		"""One POST to the live site with a valid JSON-RPC body."""
		return utils.request(
			"POST",
			path,
			headers={"Content-Type": "application/json", **(headers or {})},
			data=json.dumps(PING),
		)

	def cookie(self) -> dict:
		return {"Cookie": f"sid={self.sid}"}

	def bearer(self) -> dict:
		return {"Authorization": f"Bearer {self.token}"}

	def assert_refused(self, response):
		"""The documented answer for a request that carries no token."""
		status = http.ERRORS["no_credentials"][0]
		self.assertEqual(response.status_code, status, response.text[:400])
		payload = response.json()
		self.assertEqual(payload["error"], "no_credentials")
		self.assertIn("Authorization: Bearer sk_", payload["message"])
		self.assertTrue(
			response.headers.get("WWW-Authenticate", "").startswith('Bearer realm="sketch"'),
			response.headers.get("WWW-Authenticate"),
		)

	def test_the_cookie_signs_the_user_in_off_mcp(self):
		"""The control. Without it every case below passes on a dead cookie."""
		utils.require_webserver()
		response = utils.request(
			"GET", "/api/method/frappe.auth.get_logged_user", headers=self.cookie()
		)
		self.assertEqual(response.status_code, 200, response.text[:400])
		self.assertEqual(response.json()["message"], self.user)

	def test_a_cookie_alone_is_refused_on_mcp(self):
		"""The hole. A same-origin page could drive every tool with this."""
		utils.require_webserver()
		self.assert_refused(self.post(self.cookie()))

	def test_a_cookie_beside_a_token_is_refused_on_mcp(self):
		"""A browser request stays a browser request. The hook leaves a
		signed-in session alone, so the token never names the user and the
		renderer refuses. An MCP client sends no cookie."""
		utils.require_webserver()
		self.assert_refused(self.post({**self.cookie(), **self.bearer()}))

	def test_a_token_alone_still_reaches_the_tools(self):
		"""The control for the gate. A 401 here would lock out every agent."""
		utils.require_webserver()
		response = self.post(self.bearer())
		self.assertEqual(response.status_code, 200, response.text[:400])
		self.assertEqual(response.json()["id"], 1)


if __name__ == "__main__":
	unittest.main()
