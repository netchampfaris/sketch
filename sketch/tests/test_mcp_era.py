# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The MCP era switch, on the one `/mcp` endpoint.

Spec 8.3. One endpoint serves the legacy revision `2025-06-18` and the modern
revision `2026-07-28`. The switch is the presence of
`params._meta["io.modelcontextprotocol/protocolVersion"]`.

Trap 2: `rpc.handle` must be able to return HTTP 400. Builder answers 200 for
every protocol error, which leaves a client with no transport-level signal. An
unsupported version is `-32022` **with HTTP 400**.

Every case runs twice: once against `rpc.handle` on its own, and once over HTTP
against the live server, because only the live path proves the status code
survives the transport.
"""

import json

import frappe
from frappe.tests import IntegrationTestCase

from sketch.mcp import rpc
from sketch.sketch.doctype.sketch_token.sketch_token import get_or_create
from sketch.tests import utils

MODERN = rpc.MODERN_VERSION
LEGACY = rpc.LEGACY_VERSION
UNSUPPORTED = "2024-11-05"

META_VERSION = rpc.META_PROTOCOL_VERSION
META_CAPS = rpc.META_CLIENT_CAPABILITIES


def legacy_message(method: str, params: dict | None = None, request_id=1) -> dict:
	return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}


def modern_message(method: str, params: dict | None = None, version: str = MODERN, request_id=1) -> dict:
	body = dict(params or {})
	body["_meta"] = {META_VERSION: version, META_CAPS: {}}
	return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": body}


def modern_headers(method: str, version: str = MODERN, name: str | None = None) -> dict:
	headers = {rpc.HEADER_PROTOCOL_VERSION: version, rpc.HEADER_METHOD: method}
	if name:
		headers[rpc.HEADER_NAME] = name
	return headers


class TestMcpEraSwitch(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.user = utils.make_user("mcp", "d2tmcp")
		cls.addClassCleanup(utils.drop_user, cls.user)
		cls.token = get_or_create(cls.user)
		# The web server reads its own connection, so the token must be on disk
		# before any HTTP case runs.
		frappe.db.commit()

	# ---------------------------------------------------------- rpc.handle

	def call(self, message: dict, headers: dict | None = None):
		return rpc.handle(json.dumps(message).encode(), headers or {})

	def test_legacy_initialize_works(self):
		status, payload = self.call(
			legacy_message("initialize", {"protocolVersion": LEGACY, "capabilities": {}})
		)
		self.assertEqual(status, 200)
		result = payload["result"]
		self.assertEqual(result["protocolVersion"], LEGACY)
		self.assertEqual(result["serverInfo"]["name"], "sketch")
		self.assertIn("tools", result["capabilities"])
		self.assertIn("get_skill", result["instructions"])
		self.assertNotIn("resultType", result, "a legacy result must not carry resultType")

	def test_legacy_tools_list_works(self):
		status, payload = self.call(legacy_message("tools/list"))
		self.assertEqual(status, 200)
		tools = payload["result"]["tools"]
		self.assertEqual(len(tools), 11, "spec 8.5: eleven tools, and no more")
		self.assertNotIn("ttlMs", payload["result"])

	def test_modern_request_works(self):
		status, payload = self.call(
			modern_message("tools/list"), modern_headers("tools/list")
		)
		self.assertEqual(status, 200, payload)
		result = payload["result"]
		self.assertEqual(result["resultType"], "complete")
		self.assertEqual(result["_meta"][rpc.META_SERVER_INFO]["name"], "sketch")
		self.assertEqual(result["ttlMs"], rpc.CACHE_TTL_MS)
		self.assertEqual(result["cacheScope"], rpc.CACHE_SCOPE)
		self.assertEqual(len(result["tools"]), 11)

	def test_modern_server_discover_works(self):
		status, payload = self.call(
			modern_message("server/discover"), modern_headers("server/discover")
		)
		self.assertEqual(status, 200, payload)
		result = payload["result"]
		self.assertEqual(result["supportedVersions"], [MODERN, LEGACY])
		self.assertEqual(result["resultType"], "complete")

	def test_an_unsupported_version_is_32022_with_400(self):
		"""Trap 2, in both eras and from both places a version can arrive."""
		cases = {
			"legacy initialize param": (
				legacy_message("initialize", {"protocolVersion": UNSUPPORTED}),
				{},
			),
			"legacy header": (
				legacy_message("tools/list"),
				{rpc.HEADER_PROTOCOL_VERSION: UNSUPPORTED},
			),
			"modern _meta": (
				modern_message("tools/list", version=UNSUPPORTED),
				modern_headers("tools/list", version=UNSUPPORTED),
			),
		}
		for label, (message, headers) in cases.items():
			with self.subTest(case=label):
				status, payload = self.call(message, headers)
				self.assertEqual(status, 400, payload)
				self.assertEqual(payload["error"]["code"], rpc.UNSUPPORTED_PROTOCOL_VERSION)
				self.assertEqual(payload["error"]["data"]["requested"], UNSUPPORTED)
				self.assertEqual(payload["error"]["data"]["supported"], [MODERN, LEGACY])

	def test_a_method_removed_in_the_modern_era_says_so(self):
		for method in ("initialize", "ping"):
			with self.subTest(method=method):
				status, payload = self.call(modern_message(method), modern_headers(method))
				self.assertEqual(status, 200)
				self.assertEqual(payload["error"]["code"], -32601)
				self.assertIn(MODERN, payload["error"]["message"])

	def test_a_modern_only_method_is_refused_in_the_legacy_era(self):
		status, payload = self.call(legacy_message("server/discover"))
		self.assertEqual(status, 200)
		self.assertEqual(payload["error"]["code"], -32601)
		self.assertIn("_meta", payload["error"]["message"])

	def test_a_modern_header_mismatch_is_32020_with_400(self):
		cases = {
			"no version header": (modern_message("tools/list"), {rpc.HEADER_METHOD: "tools/list"}),
			"no method header": (
				modern_message("tools/list"),
				{rpc.HEADER_PROTOCOL_VERSION: MODERN},
			),
			"method header disagrees": (
				modern_message("tools/list"),
				modern_headers("server/discover"),
			),
		}
		for label, (message, headers) in cases.items():
			with self.subTest(case=label):
				status, payload = self.call(message, headers)
				self.assertEqual(status, 400, payload)
				self.assertEqual(payload["error"]["code"], rpc.HEADER_MISMATCH)

	def test_a_modern_request_without_client_capabilities_is_400(self):
		message = modern_message("tools/list")
		del message["params"]["_meta"][META_CAPS]
		status, payload = self.call(message, modern_headers("tools/list"))
		self.assertEqual(status, 400)
		self.assertEqual(payload["error"]["code"], -32602)

	def test_a_notification_is_202_with_no_body(self):
		status, payload = self.call({"jsonrpc": "2.0", "method": "notifications/initialized"})
		self.assertEqual(status, 202)
		self.assertIsNone(payload)

	def test_a_batch_is_refused(self):
		status, payload = rpc.handle(b'[{"jsonrpc":"2.0","id":1,"method":"ping"}]', {})
		self.assertEqual(status, 200)
		self.assertEqual(payload["error"]["code"], -32600)

	def test_a_broken_body_is_a_parse_error(self):
		status, payload = rpc.handle(b"{not json", {})
		self.assertEqual(status, 200)
		self.assertEqual(payload["error"]["code"], -32700)

	# --------------------------------------------------------- over HTTP

	def post(self, message: dict, headers: dict | None = None):
		return utils.request(
			"POST",
			"/mcp",
			headers={
				"Authorization": f"Bearer {self.token}",
				"Content-Type": "application/json",
				**(headers or {}),
			},
			data=json.dumps(message),
		)

	def test_http_serves_both_eras_on_one_endpoint(self):
		utils.require_webserver()

		legacy = self.post(legacy_message("initialize", {"protocolVersion": LEGACY}))
		self.assertEqual(legacy.status_code, 200, legacy.text[:400])
		self.assertEqual(legacy.json()["result"]["protocolVersion"], LEGACY)

		modern = self.post(modern_message("tools/list"), modern_headers("tools/list"))
		self.assertEqual(modern.status_code, 200, modern.text[:400])
		self.assertEqual(modern.json()["result"]["resultType"], "complete")

	def test_http_answers_400_for_an_unsupported_version(self):
		"""Trap 2 over the wire. A 200 here is the Builder bug."""
		utils.require_webserver()
		for label, (message, headers) in {
			"legacy": (legacy_message("initialize", {"protocolVersion": UNSUPPORTED}), {}),
			"modern": (
				modern_message("tools/list", version=UNSUPPORTED),
				modern_headers("tools/list", version=UNSUPPORTED),
			),
		}.items():
			with self.subTest(case=label):
				response = self.post(message, headers)
				self.assertEqual(response.status_code, 400, response.text[:400])
				self.assertEqual(response.json()["error"]["code"], rpc.UNSUPPORTED_PROTOCOL_VERSION)

	def test_http_refuses_a_get(self):
		utils.require_webserver()
		response = utils.request(
			"GET", "/mcp", headers={"Authorization": f"Bearer {self.token}"}
		)
		self.assertEqual(response.status_code, 405, response.text[:400])
		self.assertEqual(response.headers.get("Allow"), "POST")
		self.assertEqual(response.json()["error"]["code"], -32600)

	def test_http_answers_202_with_an_empty_body_for_a_notification(self):
		utils.require_webserver()
		response = self.post({"jsonrpc": "2.0", "method": "notifications/initialized"})
		self.assertEqual(response.status_code, 202)
		self.assertEqual(response.text, "")
