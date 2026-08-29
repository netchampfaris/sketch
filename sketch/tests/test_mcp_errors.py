# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The `/mcp` error contract: every failure is JSON that names the fix.

Problems E1, E2, E4, E5, E6, E7, E8, E9 and C4. A wrong token used to return an
8 KB HTML "Session Expired" page with a Python traceback on it. An agent reads
JSON, so each failure now carries `error`, `message` and `settings_url`, and
each 401 carries a `WWW-Authenticate` header that does not start an OAuth flow
Sketch cannot serve.

Every case here drives the live server. The contract is made of a raise in
`sketch.auth`, a renderer in `sketch.mcp.http`, a `before_request` hook, an
`after_request` hook, and core's own response pipeline, and only a real request
runs all five.

`test_auth_scope.py` owns the scope of a Sketch Token and `test_mcp_era.py`
owns the JSON-RPC bodies. Neither is repeated here.
"""

import json
import unittest

import frappe
from frappe.tests import IntegrationTestCase, set_user

from sketch import api
from sketch.mcp import http, rpc
from sketch.sketch.doctype.sketch_token.sketch_token import get_or_create
from sketch.tests import utils

#: The four failures the contract names, and the account each one needs.
FAILURES = ("no_credentials", "wrong_auth_scheme", "invalid_token", "no_access")

#: Paths a Sketch failure must never answer. The raise is scoped to `/mcp`, and
#: that scope is the whole security argument for Sketch Token (trap 8).
OFF_MCP_PATHS = (
	"/api/method/frappe.ping",
	"/api/method/frappe.auth.get_logged_user",
	"/api/resource/User",
	"/app",
	"/",
)


class TestMcpErrorContract(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.user = utils.make_user("err", "d2terr")
		cls.addClassCleanup(utils.drop_user, cls.user)
		cls.token = get_or_create(cls.user)

		# A signed-up account with a token but no Sketch User role. It is the
		# only way to reach the 403: the token authenticates, the permission
		# check then refuses.
		cls.stranger = utils.make_user("errnorole", "d2terrnorole")
		cls.addClassCleanup(utils.drop_user, cls.stranger)
		frappe.db.delete("Has Role", {"parent": cls.stranger, "role": utils.TEST_ROLE})
		# A direct row delete leaves the user's roles in redis, which the web
		# server reads. Clear it, or the 403 case authenticates and passes.
		frappe.clear_cache(user=cls.stranger)
		cls.stranger_token = get_or_create(cls.stranger)

		# The web server reads its own connection, so both tokens must be on
		# disk before any HTTP case runs.
		frappe.db.commit()

	# ------------------------------------------------------------- helpers

	def post(self, headers: dict | None = None, path: str = "/mcp"):
		"""One POST to `/mcp` with a valid JSON-RPC body."""
		return utils.request(
			"POST",
			path,
			headers={"Content-Type": "application/json", **(headers or {})},
			data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}}),
		)

	def failure(self, case: str):
		"""The live response for one `FAILURES` case."""
		headers = {
			"no_credentials": {},
			"wrong_auth_scheme": {"Authorization": "Basic abc"},
			"invalid_token": {"Authorization": "Bearer sk_wrong"},
			"no_access": {"Authorization": f"Bearer {self.stranger_token}"},
		}[case]
		return self.post(headers)

	# -------------------------------------------------------- E1, E2: JSON

	def test_a_wrong_token_answers_json_and_not_html(self):
		"""E1. The HTML page was 8,583 bytes and an agent could not read it."""
		utils.require_webserver()
		response = self.failure("invalid_token")
		self.assertEqual(response.status_code, 401, response.text[:400])
		self.assertTrue(response.headers.get("Content-Type", "").startswith("application/json"))
		self.assertEqual(response.json()["error"], "invalid_token")

	def test_a_wrong_token_leaks_no_traceback(self):
		"""E2. The raise bypasses core's error page, so nothing leaks.

		`developer_mode` must be on for the case to mean anything: with it off
		core hides the traceback anyway and the case proves nothing.
		"""
		utils.require_webserver()
		if not frappe.conf.developer_mode:
			raise unittest.SkipTest("developer_mode is off, so a leak cannot be shown")

		body = self.failure("invalid_token").text
		self.assertNotIn("<html", body.lower())
		self.assertNotIn("Traceback", body)
		self.assertNotIn("frappe/app.py", body)
		self.assertLess(len(body), 1024, "the body grew back into a page")

	# -------------------------------------------------- E4, E5: naming the fix

	def test_the_guest_401_names_the_authorization_header(self):
		"""E4. A body that says "authentication required" names no fix."""
		utils.require_webserver()
		payload = self.failure("no_credentials").json()
		self.assertEqual(payload["error"], "no_credentials")
		self.assertIn("Authorization: Bearer sk_", payload["message"])

	def test_a_wrong_scheme_reads_differently_from_no_header(self):
		"""E5. A wrong header name used to look exactly like a missing one."""
		utils.require_webserver()
		guest = self.failure("no_credentials").json()
		scheme = self.failure("wrong_auth_scheme").json()
		self.assertEqual(scheme["error"], "wrong_auth_scheme")
		self.assertNotEqual(guest["error"], scheme["error"])
		self.assertNotEqual(guest["message"], scheme["message"])
		self.assertIn("Bearer scheme only", scheme["message"])

	def test_every_failure_body_carries_the_contract_keys(self):
		utils.require_webserver()
		for case in FAILURES:
			with self.subTest(case=case):
				response = self.failure(case)
				self.assertEqual(response.status_code, http.ERRORS[case][0], response.text[:400])
				self.assertTrue(response.headers.get("Content-Type", "").startswith("application/json"))
				payload = response.json()
				self.assertEqual(sorted(payload), ["error", "message", "settings_url"])
				self.assertEqual(payload["error"], case)
				self.assertTrue(payload["message"])
				self.assertTrue(payload["settings_url"].endswith("/settings"))
				self.assertTrue(payload["settings_url"].startswith("http"))

	def test_the_no_access_body_names_the_role(self):
		"""The 403 is the one failure a token cannot fix by itself."""
		utils.require_webserver()
		response = self.failure("no_access")
		self.assertEqual(response.status_code, 403, response.text[:400])
		self.assertIn("Sketch User", response.json()["message"])
		self.assertIn("Settings", response.json()["message"])

	# --------------------------------------------- the WWW-Authenticate trap

	def test_every_failure_carries_the_sketch_challenge(self):
		"""Core advertises the site as an OAuth server on a 401 and on a 403.

		`show_protected_resource_metadata` is on, so core writes
		`Bearer resource_metadata="..."` in `process_response`. An MCP client
		that reads it starts an OAuth flow `/mcp` does not serve, instead of
		telling the user to paste a token. Sketch pins its own value after it.

		The 403 counts. Core rewrites the header there too
		(`frappe/app.py:243`), so a good token with too few rights would send
		the same client down the same dead end.
		"""
		utils.require_webserver()
		for case in FAILURES:
			with self.subTest(case=case):
				challenge = self.failure(case).headers.get("WWW-Authenticate", "")
				self.assertTrue(
					challenge.startswith('Bearer realm="sketch"'),
					f"{case} answered WWW-Authenticate: {challenge!r}",
				)
				self.assertNotIn("resource_metadata", challenge)

	def test_the_challenge_names_each_wrong_credential_case(self):
		"""One code per failure, so a client can branch on the header alone."""
		utils.require_webserver()
		expected = {
			"wrong_auth_scheme": 'error="invalid_request"',
			"invalid_token": 'error="invalid_token"',
			"no_access": 'error="insufficient_scope"',
		}
		for case, code in expected.items():
			with self.subTest(case=case):
				self.assertIn(code, self.failure(case).headers["WWW-Authenticate"])

	# -------------------------------------------------- E7, E8, E9: the edges

	def test_delete_is_405_with_an_allow_header(self):
		"""E7. Core raises NotFound for DELETE before any renderer runs."""
		utils.require_webserver()
		response = utils.request("DELETE", "/mcp")
		self.assertEqual(response.status_code, 405, response.text[:400])
		self.assertEqual(response.headers.get("Allow"), "POST")
		self.assertEqual(response.json()["error"]["code"], -32600)

	def test_options_is_204_with_an_allow_header(self):
		"""E9. Core answers OPTIONS with a bare 200 and no Allow header."""
		utils.require_webserver()
		response = utils.request("OPTIONS", "/mcp")
		self.assertEqual(response.status_code, 204, response.text[:400])
		self.assertEqual(response.headers.get("Allow"), "POST, OPTIONS")
		self.assertEqual(response.text, "")

	def test_the_path_is_matched_in_any_letter_case(self):
		"""E8. `/MCP` used to miss the renderer and land on the website 404."""
		utils.require_webserver()
		for path in ("/MCP", "/Mcp"):
			with self.subTest(path=path):
				response = self.post({"Authorization": f"Bearer {self.token}"}, path=path)
				self.assertEqual(response.status_code, 200, response.text[:400])
				self.assertEqual(response.json()["id"], 1)

	def test_the_edges_are_answered_on_mcp_only(self):
		"""The `before_request` hook runs on every request on the site.

		Core keeps its own answers off `/mcp`: 404 for DELETE
		(`frappe/app.py:117-118`) and a bare 200 for OPTIONS
		(`frappe/app.py:82-83`). `/mcpx` is the near miss the path test must
		not catch.
		"""
		utils.require_webserver()
		for path in ("/mcpx", "/"):
			with self.subTest(path=path):
				deleted = utils.request("DELETE", path)
				self.assertEqual(deleted.status_code, 404)
				self.assertNotIn("-32600", deleted.text)

				options = utils.request("OPTIONS", path)
				self.assertEqual(options.status_code, 200)
				self.assertIsNone(options.headers.get("Allow"))

	# ------------------------------------------------- E6: a broken body

	def broken(self, body: str, headers: dict | None = None, path: str = "/mcp"):
		"""One POST carrying a body that is not JSON."""
		return utils.request(
			"POST",
			path,
			headers={"Content-Type": "application/json", **(headers or {})},
			data=body,
		)

	def test_a_broken_body_answers_the_parse_error_and_not_an_html_page(self):
		"""E6. Core threw a 417 HTML page from inside `make_form_dict`.

		That call is ahead of every app hook, so no hook on the way in can
		catch it. `after_request` holds the response on the way out instead.
		"""
		utils.require_webserver()
		for body in ("{bad json", "not json at all", "{'single': 'quotes'}"):
			with self.subTest(body=body):
				response = self.broken(body)
				self.assertEqual(response.status_code, 400, response.text[:400])
				self.assertTrue(
					response.headers.get("Content-Type", "").startswith("application/json"),
					response.headers.get("Content-Type"),
				)
				payload = response.json()
				self.assertEqual(payload["error"]["code"], -32700)
				self.assertEqual(payload["error"]["message"], rpc.PARSE_ERROR)
				self.assertIsNone(payload["id"])

	def test_the_broken_body_answer_matches_the_in_process_one(self):
		"""One mistake, one answer. `rpc.handle` and HTTP must not differ."""
		utils.require_webserver()
		status, payload = rpc.handle(b"{bad json", {})

		response = self.broken("{bad json")
		self.assertEqual(response.status_code, status)
		self.assertEqual(response.json(), payload)

	def test_the_broken_body_answer_carries_no_web_page_headers(self):
		"""Core's error page leaves `Link` preloads and `X-Page-Name` behind."""
		utils.require_webserver()
		response = self.broken("{bad json")
		for header in http.PAGE_HEADERS:
			with self.subTest(header=header):
				self.assertIsNone(response.headers.get(header))

	def test_a_broken_body_off_mcp_keeps_core_s_own_answer(self):
		"""The rewrite is scoped. Every other path still gets core's 417."""
		utils.require_webserver()
		for path in ("/mcpx", "/api/method/frappe.ping"):
			with self.subTest(path=path):
				response = self.broken("{bad json", path=path)
				self.assertEqual(response.status_code, 417, response.text[:200])
				self.assertNotIn("-32700", response.text)

	def test_a_good_body_is_never_rewritten(self):
		"""`after_request` must leave every Sketch answer alone.

		The flag is the whole guard. If it ever fails to set, a real reply
		turns into a parse error.
		"""
		utils.require_webserver()
		good = self.post({"Authorization": f"Bearer {self.token}"})
		self.assertEqual(good.status_code, 200, good.text[:400])
		self.assertNotIn("-32700", good.text)

		for case in FAILURES:
			with self.subTest(case=case):
				self.assertNotIn("-32700", self.failure(case).text)

	# ------------------------------------------- the raise stays on /mcp

	def test_the_raise_never_reaches_api_or_desk(self):
		"""Trap 8, from the other side.

		`sketch.auth` now stops a request. If that raise were not scoped to
		`/mcp`, a Sketch body would answer Desk and the REST API too, and a
		Sketch Token would be a site-wide credential.
		"""
		utils.require_webserver()
		for header in ({"Authorization": "Bearer sk_wrong"}, {"Authorization": f"Bearer {self.token}"}):
			for path in OFF_MCP_PATHS:
				with self.subTest(path=path, header=header["Authorization"][:16]):
					response = utils.request("GET", path, headers=header)
					self.assertEqual(response.status_code, 401, f"{path} answered {response.status_code}")
					for name in FAILURES:
						self.assertNotIn(name, response.text)
					self.assertNotIn("settings_url", response.text)
					self.assertNotIn(
						'realm="sketch"', response.headers.get("WWW-Authenticate", "")
					)

	# --------------------------------------------------------- C4: last_used

	def test_last_used_is_null_until_an_agent_connects(self):
		utils.require_webserver()
		fresh = utils.make_user("errfresh", "d2terrfresh")
		self.addCleanup(utils.drop_user, fresh)
		token = get_or_create(fresh)
		frappe.db.commit()

		self.assertIsNone(self.stored_last_used(fresh))
		with set_user(fresh):
			self.assertIsNone(api.get_session()["last_used"])
			self.assertIsNone(api.get_session()["last_used_pretty"])
			self.assertIsNone(api.get_agent_token()["last_used"])

		response = self.post({"Authorization": f"Bearer {token}"})
		self.assertEqual(response.status_code, 200, response.text[:400])

		self.assertIsNotNone(self.stored_last_used(fresh), "no agent request was stamped")
		with set_user(fresh):
			session = api.get_session()
			self.assertIsNotNone(session["last_used"])
			self.assertTrue(session["last_used_pretty"])
			self.assertIsNotNone(api.get_agent_token()["last_used"])

	def stored_last_used(self, user: str):
		"""The stamp the web server wrote, read on a fresh snapshot.

		The commit ends this connection's transaction. Without it InnoDB serves
		the snapshot the test opened with, which is older than the write.
		"""
		frappe.db.commit()
		return frappe.db.get_value("Sketch Token", {"user": user}, "last_used")


if __name__ == "__main__":
	unittest.main()
