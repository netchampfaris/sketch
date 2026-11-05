# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""Sketch records which app connected, so the screens can say "Connected · Cursor".

`initialize` is the one MCP message that names its client
(`params.clientInfo.name`). `sketch.mcp.rpc.handle_initialize` hands it to
`sketch_token.record_client`, which keeps a small map on the token row: the
app's display name to the last time it initialized. It writes at most once a
minute per app, so a client that reconnects often does not write a row each
time.

`get_session` and `get_agent_token` return the map as `clients`, newest first.
Reset clears it with `last_used`, because every app holds the dead token.

The last case drives the live server: an in-process call shares the test's
transaction, so only a real request proves the write commits.
"""

import json

import frappe
from frappe.tests import IntegrationTestCase, set_user
from frappe.utils import add_to_date, now_datetime

from sketch import api
from sketch.mcp import rpc
from sketch.sketch.doctype.sketch_token import sketch_token
from sketch.tests import utils


def initialize(name: str | None, version: str = "1.0.0") -> dict:
	"""One legacy `initialize`, as a client sends it."""
	params = {"protocolVersion": rpc.LEGACY_VERSION, "capabilities": {}}
	if name is not None:
		params["clientInfo"] = {"name": name, "version": version}
	status, payload = rpc.handle(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": params}).encode())
	assert status == 200, payload
	return payload


class TestTokenClients(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.user = utils.make_user("clients", "d2tclients")
		cls.addClassCleanup(utils.drop_user, cls.user)

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		super().tearDownClass()

	def setUp(self):
		sketch_token.get_or_create(self.user)
		frappe.db.set_value("Sketch Token", self.user, "clients", None, update_modified=False)
		frappe.db.commit()

	def stored(self) -> dict:
		value = frappe.db.get_value("Sketch Token", self.user, "clients")
		return json.loads(value) if value else {}

	def set_stored(self, clients: dict) -> None:
		frappe.db.set_value("Sketch Token", self.user, "clients", json.dumps(clients), update_modified=False)

	def connect(self, name: str | None) -> None:
		with set_user(self.user):
			initialize(name)

	# ---------------------------------------------------------- recording

	def test_initialize_records_the_app_by_its_display_name(self):
		self.connect("claude-code")

		self.assertEqual(list(self.stored()), ["Claude Code"])

	def test_known_names_fold_case_and_unknown_names_are_trimmed(self):
		self.connect("Visual Studio Code")
		self.connect("codex-mcp-client")
		self.connect("  " + "x" * 60)

		self.assertEqual(set(self.stored()), {"VS Code", "Codex", "x" * sketch_token.CLIENT_NAME_LIMIT})

	def test_a_client_with_no_name_records_nothing(self):
		self.connect(None)
		self.connect("   ")

		self.assertEqual(self.stored(), {})

	def test_a_second_initialize_within_a_minute_writes_nothing(self):
		recent = str(add_to_date(now_datetime(), seconds=-30))
		self.set_stored({"Cursor": recent})

		self.connect("cursor")

		self.assertEqual(self.stored(), {"Cursor": recent})

	def test_an_initialize_after_a_minute_moves_the_stamp(self):
		old = str(add_to_date(now_datetime(), minutes=-2))
		self.set_stored({"Cursor": old})

		self.connect("Cursor")

		self.assertGreater(self.stored()["Cursor"], old)

	def test_recording_leaves_modified_alone(self):
		before = frappe.db.get_value("Sketch Token", self.user, "modified")

		self.connect("cursor")

		self.assertEqual(frappe.db.get_value("Sketch Token", self.user, "modified"), before)

	# ------------------------------------------------------------ reading

	def test_both_payloads_list_the_apps_newest_first(self):
		self.set_stored(
			{
				"Cursor": str(add_to_date(now_datetime(), days=-5)),
				"Claude Code": str(add_to_date(now_datetime(), minutes=-2)),
			}
		)

		with set_user(self.user):
			session = api.get_session()
			token = api.get_agent_token()

		for payload in (session, token):
			self.assertEqual([one["name"] for one in payload["clients"]], ["Claude Code", "Cursor"])
			self.assertTrue(all(one["last_used_pretty"] for one in payload["clients"]))

	def test_reset_clears_the_apps(self):
		self.connect("cursor")

		sketch_token.regenerate(self.user)

		self.assertEqual(self.stored(), {})
		with set_user(self.user):
			self.assertEqual(api.get_session()["clients"], [])


class TestTokenClientsLive(IntegrationTestCase):
	"""The write survives a real `/mcp` request."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_webserver()
		cls.user = utils.make_user("clientslive", "d2tclientslive")
		cls.addClassCleanup(utils.drop_user, cls.user)
		cls.token = sketch_token.get_or_create(cls.user)

	def test_an_initialize_over_http_records_the_app(self):
		body = {
			"jsonrpc": "2.0",
			"id": 1,
			"method": "initialize",
			"params": {"protocolVersion": rpc.LEGACY_VERSION, "clientInfo": {"name": "cursor", "version": "1.0"}},
		}
		response = utils.request(
			"POST",
			"/mcp",
			json=body,
			headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
		)
		self.assertEqual(response.status_code, 200, response.text[:400])

		frappe.db.rollback()
		with set_user(self.user):
			self.assertEqual([one["name"] for one in api.get_session()["clients"]], ["Cursor"])
