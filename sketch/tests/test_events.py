# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""Product analytics: the row survives the failure it is about.

`sketch.events` exists to answer why a beta user got stuck, so its whole value
sits on the failure path. Two things roll work back under it:

- `sketch.mcp.tools.call_tool` rolls back to a savepoint when a tool raises.
- Core rolls the whole request back for every safe HTTP method
  (`frappe/app.py:404-407`).

Both would take an inline insert with them. `record` therefore only buffers,
and `flush` writes after core has closed the caller's transaction. These cases
hold that apart: a buffered row is invisible until flushed, a rolled-back tool
call still leaves its row, and a live wrong-token request records which of the
four ways it failed.

The doctype is operator data. A Sketch User must not read it, because one table
holds every account's tool calls.
"""

import json

import frappe
from frappe.tests import IntegrationTestCase

from sketch import events
from sketch.mcp import tools
from sketch.sketch.doctype.sketch_token.sketch_token import get_or_create
from sketch.tests import utils


class TestEvents(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.user = utils.make_user("ev", "d2tev")
		cls.addClassCleanup(utils.drop_user, cls.user)
		cls.token = get_or_create(cls.user)
		# The web server reads its own connection, so the token must be on disk
		# before any HTTP case runs.
		frappe.db.commit()

	def setUp(self):
		frappe.set_user("Administrator")
		self.drop_rows()
		self.addCleanup(self.drop_rows)
		# A leftover buffer from another case would be flushed into this one.
		events._buffer()[:] = []

	def drop_rows(self) -> None:
		frappe.db.delete("Sketch Event", {"user": self.user})
		frappe.db.delete("Sketch Event", {"detail": "d2t-case"})
		frappe.db.commit()

	def rows(self, event: str | None = None) -> list:
		filters = {"user": self.user}
		if event:
			filters["event"] = event
		return frappe.get_all("Sketch Event", filters=filters, fields=["event", "ok", "detail", "ms"])

	# ------------------------------------------------- buffered, then written

	def test_record_writes_nothing_until_flush(self):
		"""The buffer is the whole design. An inline insert would be rolled
		back by the caller it is watching."""
		events.record(events.TOOL_CALL, user=self.user, detail="d2t-case")
		self.assertEqual(self.rows(), [], "record wrote a row before the flush")

		events.flush()
		self.assertEqual(len(self.rows()), 1)

	def test_flush_empties_the_buffer(self):
		"""A second flush in one request must not write the row twice."""
		events.record(events.TOOL_CALL, user=self.user, detail="d2t-case")
		events.flush()
		events.flush()
		self.assertEqual(len(self.rows()), 1)

	def test_a_rollback_does_not_take_the_row(self):
		"""The case the whole module is built for.

		The insert happens after the rollback, because the flush hook runs in
		the `finally` of `application` and the rollback runs above it.
		"""
		events.record(events.CHECK, user=self.user, detail="compile-failed", ok=False)
		frappe.db.rollback()
		events.flush()

		rows = self.rows(events.CHECK)
		self.assertEqual(len(rows), 1, "the rollback took the event with it")
		self.assertEqual(rows[0].ok, 0)
		self.assertEqual(rows[0].detail, "compile-failed")

	def test_guest_is_stored_as_no_user(self):
		"""'Nobody was signed in' and 'this account did it' are different facts."""
		events.record(events.AUTH_FAILED, user="Guest", ok=False, detail="d2t-case")
		events.flush()
		row = frappe.get_all("Sketch Event", filters={"detail": "d2t-case"}, fields=["user"], limit=1)[0]
		self.assertIsNone(row.user)

	def test_a_long_detail_is_cut_not_refused(self):
		"""A log must never be the reason a request fails."""
		events.record(events.TOOL_CALL, user=self.user, detail="x" * 500)
		events.flush()
		self.assertEqual(len(self.rows()[0].detail), 140)

	def test_one_request_cannot_buffer_without_end(self):
		for _ in range(events.MAX_PER_REQUEST + 25):
			events.record(events.TOOL_CALL, user=self.user, detail="d2t-case")
		self.assertEqual(len(events._buffer()), events.MAX_PER_REQUEST)

	# --------------------------------------------------------- the tool seat

	def test_a_failed_tool_call_still_leaves_its_row(self):
		"""`call_tool` rolls back to its savepoint on the way out. The row is
		buffered, so the rollback cannot reach it."""
		frappe.set_user(self.user)
		self.addCleanup(frappe.set_user, "Administrator")

		reply = tools.call_tool("list_files", {"prototype": "d2t-no-such-slug"})
		self.assertTrue(reply["isError"], "the fixture stopped being a failure")

		frappe.set_user("Administrator")
		events.flush()
		rows = self.rows(events.TOOL_CALL)
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0].detail, "list_files")
		self.assertEqual(rows[0].ok, 0)

	def test_a_good_tool_call_is_recorded_as_ok(self):
		frappe.set_user(self.user)
		self.addCleanup(frappe.set_user, "Administrator")

		reply = tools.call_tool("list_prototypes", {})
		self.assertFalse(reply["isError"], reply)

		frappe.set_user("Administrator")
		events.flush()
		rows = self.rows(events.TOOL_CALL)
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0].detail, "list_prototypes")
		self.assertEqual(rows[0].ok, 1)

	# ------------------------------------------------------- the live request

	def test_a_wrong_token_records_which_failure_it_was(self):
		"""The audit called this the most likely failure a real user meets, and
		until now the endpoint answered it and forgot it.

		The row is written by the live server, so this reads the table rather
		than the buffer.
		"""
		utils.require_webserver()
		before = self.count("invalid_token")
		response = utils.request(
			"POST",
			"/mcp",
			headers={"Content-Type": "application/json", "Authorization": "Bearer sk_wrong"},
			data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}}),
		)
		self.assertEqual(response.status_code, 401, response.text[:400])
		self.assertEqual(self.count("invalid_token"), before + 1)

	def count(self, detail: str) -> int:
		"""Rows for one auth failure, read past this connection's snapshot.

		The web server writes on its own connection, so this one must not serve
		the read from a transaction it opened before that write.
		"""
		frappe.db.commit()
		return frappe.db.count("Sketch Event", {"event": events.AUTH_FAILED, "detail": detail})

	# ------------------------------------------------------------ permissions

	def test_a_sketch_user_cannot_read_the_table(self):
		"""One table holds every account's tool calls, so any read of it is a
		read across users."""
		frappe.set_user(self.user)
		self.addCleanup(frappe.set_user, "Administrator")
		self.assertFalse(frappe.has_permission("Sketch Event", "read"))
