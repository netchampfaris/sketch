# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The check browser reaches the origin under test and nothing else.

`check` runs one user's JavaScript in a browser on the server, inside the
perimeter. Without a network policy an `onMounted` fetch reaches a neighbouring
bench on loopback or the cloud metadata address, and an iframe of any frameable
internal page comes back to the author inside the check screenshot.

Two layers answer that, and this module holds both to their job:

- the route filter in `checkd/check-lib.mjs` `restrictEgress`, which is the
  control, because it names the one origin that is allowed;
- the `MAP * ~NOTFOUND` resolver rule in `checkd/checkd.mjs`, layer two.

The route filter has two halves, because Playwright keeps WebSocket handshakes
off the `context.route` list. `context.route` covers every other request and
`context.routeWebSocket` covers the sockets. A case here holds each half.

A block must also be readable. An aborted request renders as an empty picture,
with nothing in `errors` and nothing in `consoleErrors`, so `restrictEgress`
counts what it refused and `egressWarnings` names the origins in the report
`warnings`.

`checkd_egress.mjs` drives each layer in headless Chromium and prints one JSON
document. This module reads it and makes the assertions. The node run happens
once for the class, because a browser launch per case costs more than the whole
suite.

Skips when node, Playwright or the web server is absent. A skip is not a pass.
"""

import json
import unittest

from frappe.tests import IntegrationTestCase

from sketch.tests import utils

SCRIPT = "checkd_egress.mjs"


class TestCheckdEgress(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()

		reason = utils.node_reason() or utils.webserver_reason()
		if reason:
			raise unittest.SkipTest(reason)

		entry = f"{utils.playwright_root()}/playwright/index.mjs"
		run = utils.run_node(SCRIPT, entry, utils.site_host(), str(utils.webserver_port()))
		if run.returncode != 0:
			raise AssertionError(f"{SCRIPT} failed:\n{run.stdout[-4000:]}\n{run.stderr[-4000:]}")

		cls.answers = json.loads(run.stdout)

	def case(self, name: str) -> dict:
		answer = self.answers.get(name)
		self.assertIsNotNone(answer, f"{SCRIPT} reported no case named {name}")
		return answer

	# ------------------------------------------------------------- the control

	def test_another_origin_on_loopback_is_reachable_without_the_policy(self):
		"""The control. Every "blocked" below is a target that was reachable.

		The target is the same web server under `127.0.0.1`, so the case needs
		no second service and no internet.
		"""
		answer = self.case("control")
		self.assertEqual(answer["crossOrigin"], "ok", json.dumps(answer))

	# -------------------------------------------------------------- the layers

	def test_the_shipped_pair_allows_the_origin_under_test_only(self):
		answer = self.case("filtered")
		self.assertEqual(answer["document"], "ok", json.dumps(answer))
		self.assertEqual(answer["sameOrigin"], "ok", json.dumps(answer))
		self.assertEqual(answer["crossOrigin"], "blocked", json.dumps(answer))
		self.assertEqual(answer["unknownHost"], "blocked", json.dumps(answer))

	def test_a_data_url_still_loads(self):
		"""A data URL never leaves the browser, and the Runtime uses them."""
		self.assertEqual(self.case("filtered")["dataUrl"], "ok")

	def test_the_route_filter_alone_blocks_another_origin(self):
		"""The control layer, measured without the resolver rule."""
		answer = self.case("routeOnly")
		self.assertEqual(answer["document"], "ok", json.dumps(answer))
		self.assertEqual(answer["sameOrigin"], "ok", json.dumps(answer))
		self.assertEqual(answer["crossOrigin"], "blocked", json.dumps(answer))

	def test_the_resolver_rule_alone_blocks_another_origin(self):
		"""Layer two, measured without the route filter.

		The rule matches the host string before resolution, so on Chromium 151
		it covers a literal IP as well as a hostname. That is browser behaviour,
		not app code: when a Chromium version drops it this case fails, and the
		route filter above still holds the line.
		"""
		answer = self.case("resolverOnly")
		self.assertEqual(answer["document"], "ok", json.dumps(answer))
		self.assertEqual(answer["sameOrigin"], "ok", json.dumps(answer))
		self.assertEqual(answer["crossOrigin"], "blocked", json.dumps(answer))

	# ------------------------------------------------------------- the reason

	def test_a_blocked_request_names_itself(self):
		"""The author reads the abort in their own check report.

		Playwright aborts with `blockedbyclient`, which the page console prints
		as `net::ERR_BLOCKED_BY_CLIENT`. A silent drop reads as a broken fetch.
		"""
		aborted = self.case("filtered")["aborted"]
		self.assertTrue(
			any("127.0.0.1" in url for url in aborted),
			f"the blocked loopback request is not in {aborted}",
		)

	# ------------------------------------------------------------ WebSockets

	def test_a_websocket_reaches_another_origin_without_the_filter(self):
		"""The control for the two socket cases below.

		The neighbour counts the handshakes it accepted. That count is the only
		honest answer: Playwright answers a routed WebSocket itself, so a page
		can see an open socket that reached no server at all.
		"""
		answer = self.case("socketsOpen")
		self.assertEqual(answer["crossOriginSocket"], "open", json.dumps(answer))
		self.assertEqual(answer["otherUpgrades"], 1, json.dumps(answer))

	def test_a_websocket_to_another_origin_never_reaches_it(self):
		"""`context.route` alone leaves this hole open.

		Playwright routes a WebSocket handshake through its own list, so the
		request filter never sees one. Without `context.routeWebSocket` a
		Prototype opens a socket to a neighbouring bench on loopback from inside
		the perimeter.
		"""
		answer = self.case("sockets")
		self.assertEqual(answer["otherUpgrades"], 0, json.dumps(answer))
		self.assertNotEqual(answer["crossOriginSocket"], "open", json.dumps(answer))

	def test_a_websocket_to_the_origin_under_test_still_connects(self):
		"""The filter names one origin, and that origin keeps working.

		The matcher answers false for the origin under test, so Playwright never
		intercepts an allowed socket.
		"""
		answer = self.case("sockets")
		self.assertEqual(answer["sameOriginSocket"], "open", json.dumps(answer))
		self.assertEqual(answer["siteUpgrades"], 1, json.dumps(answer))

	# --------------------------------------------------------- the loud block

	def test_a_remote_picture_loads_without_the_filter(self):
		"""The control for the report cases below."""
		answer = self.case("socketsOpen")
		self.assertEqual(answer["remotePicture"], "loaded", json.dumps(answer))
		self.assertEqual(answer["warnings"], [], json.dumps(answer))

	def test_a_refused_request_is_named_in_the_report(self):
		"""A silent block is the bad failure mode this closes.

		A recipe loads a picture from a remote origin. Under the filter that
		request aborts, the picture renders at zero width, and `errors` and
		`consoleErrors` are both empty. The author reads a broken screenshot
		with no reason for it. The report names the origin instead.
		"""
		answer = self.case("sockets")
		self.assertEqual(answer["remotePicture"], "blank", json.dumps(answer))
		self.assertEqual(answer["refusedTotal"], 2, json.dumps(answer))

		warnings = answer["warnings"]
		self.assertEqual(len(warnings), 1, json.dumps(answer))
		self.assertEqual(warnings[0]["kind"], "egress-blocked")
		# One line per origin, not one per request. The picture and the socket
		# share a host, so they share a line.
		self.assertEqual(warnings[0]["file"], answer["refusedOrigins"][0])
		self.assertIn("websocket", warnings[0]["message"])
		self.assertIn("image", warnings[0]["message"])

	# ------------------------------------------------- the report `runCheck` builds

	def test_a_whole_check_reports_what_it_refused(self):
		"""The wiring, measured through `runCheck` and not through a helper.

		The `report` case runs one real check against a stand-in Runtime that
		asks for a remote picture and opens a remote socket. Both are refused,
		and the report must name the origin. `errors` and `consoleErrors` stay
		empty, which is exactly why a silent block was unreadable.
		"""
		answer = self.case("report")
		self.assertEqual(answer["errors"], [], json.dumps(answer))
		self.assertEqual(answer["consoleErrors"], [], json.dumps(answer))

		warnings = [entry for entry in answer["warnings"] if entry["kind"] == "egress-blocked"]
		self.assertEqual(len(warnings), 1, json.dumps(answer))
		self.assertIn("websocket", warnings[0]["message"])
		self.assertIn("image", warnings[0]["message"])

	def test_a_whole_check_blocks_the_websocket_too(self):
		"""The socket half of the filter, inside the shipped `runCheck` path."""
		answer = self.case("report")
		self.assertEqual(answer["otherUpgrades"], 0, json.dumps(answer))
		self.assertEqual(answer["otherPictures"], 0, json.dumps(answer))

	def test_a_refused_request_is_a_warning_and_not_an_error(self):
		"""Warnings, because the Prototype is not the thing that is wrong.

		`check-lib.mjs` `body` turns a non-empty `errors` list into status
		`errors`. A remote picture in a shipped recipe is correct code that this
		service refuses, so it must not read as the author's bug. `warnings` is
		the advisory list the report already has, and `mcp/tools.py check_text`
		prints every entry, so the line is in the text the agent reads.
		"""
		from sketch.mcp.tools import check_text

		answer = self.case("report")
		self.assertEqual(answer["status"], "ok", json.dumps(answer))

		lines = check_text(answer)
		self.assertIn("warning egress-blocked:", lines)
		self.assertIn(answer["warnings"][0]["file"], lines)
