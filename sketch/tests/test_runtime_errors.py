# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The Runtime error classes, ported from `runtime/test-errors.mjs`.

An agent only learns what it broke from what the Runtime reports, so every
error class has to arrive with a status, a kind and a file. A class that
silently reports `ok` is worse than a crash: `check` then tells the agent the
Prototype is fine.

`runtime_errors.mjs` boots each case in headless Chromium and prints one JSON
document. This module reads it and makes the assertions. The node run happens
once for the class, because a browser launch per case costs more than the whole
suite.

Skips when node, Playwright or a built Runtime is absent. A skip is not a pass.
"""

import json
import unittest

from frappe.tests import IntegrationTestCase

from sketch.tests import utils

SCRIPT = "runtime_errors.mjs"


class TestRuntimeErrors(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()

		reason = utils.node_reason() or utils.webserver_reason()
		if reason:
			raise unittest.SkipTest(reason)

		version = utils.newest_runtime()
		viewer = f"{utils.base_url()}/assets/sketch/runtimes/{version}/viewer.html"
		entry = f"{utils.playwright_root()}/playwright/index.mjs"

		run = utils.run_node(SCRIPT, entry, viewer)
		if run.returncode != 0:
			raise AssertionError(f"{SCRIPT} failed:\n{run.stdout[-4000:]}\n{run.stderr[-4000:]}")

		cls.answers = json.loads(run.stdout)
		cls.stderr = run.stderr

	def case(self, name: str) -> dict:
		answer = self.answers.get(name)
		self.assertIsNotNone(answer, f"{SCRIPT} reported no case named {name}")
		self.assertNotIn("harnessError", answer, f"{name}: {answer.get('harnessError')}")
		return answer

	def assert_failed(self, name: str, status: str, kind: str, file: str, needle: str) -> dict:
		"""Every failing class reports a status, one error, a kind and a file."""
		answer = self.case(name)
		report = json.dumps(answer)[:600]
		self.assertEqual(answer["status"], status, report)
		self.assertTrue(answer["errors"], f"{name} reported no error: {report}")

		first = answer["errors"][0]
		self.assertEqual(first["kind"], kind, report)
		self.assertEqual(first.get("file"), file, report)
		self.assertIn(needle, first["message"], report)
		return answer

	# ----------------------------------------------------- the failing classes

	def test_an_sfc_parse_error_is_reported(self):
		answer = self.assert_failed(
			"missing-end-tag", "compile-failed", "compile", "src/pages/About.vue", "end tag"
		)
		self.assertIsInstance(answer["errors"][0]["line"], int)
		self.assertIsInstance(answer["errors"][0]["column"], int)

	def test_a_ts_syntax_error_is_reported(self):
		self.assert_failed("ts-syntax", "compile-failed", "compile", "src/data.ts", "Unexpected token")

	def test_an_unresolvable_relative_import_is_reported(self):
		self.assert_failed("bad-import", "link-failed", "resolve", "src/router.ts", "./pages/Missing.vue")

	def test_a_bad_named_import_is_reported(self):
		"""Spec 5.9 wrote `boot-failed`. The build resolves it earlier, at link."""
		answer = self.case("bad-named-import")
		self.assertIn(answer["status"], ("link-failed", "boot-failed"), json.dumps(answer)[:600])
		self.assertTrue(answer["errors"])
		self.assertIn("Badgee", answer["errors"][0]["message"])
		self.assertEqual(answer["errors"][0].get("file"), "src/pages/About.vue")

	def test_a_vue_runtime_throw_is_reported(self):
		answer = self.case("runtime-throw")
		self.assertEqual(answer["status"], "errors")
		self.assertTrue(answer["errors"])
		self.assertEqual(answer["errors"][0]["kind"], "vue")
		self.assertIn("boom", answer["errors"][0]["message"])

	def test_an_empty_tree_is_reported_as_empty(self):
		answer = self.case("empty")
		self.assertEqual(answer["status"], "empty")
		self.assertEqual(answer["errors"], [])

	def test_a_missing_app_vue_is_reported(self):
		self.assert_failed("no-app", "link-failed", "precondition", "src/App.vue", "src/App.vue is missing")

	# ---------------------------------------------------- the working classes

	def test_an_import_cycle_resolves(self):
		"""Both modules read the other at call time, so both must resolve."""
		answer = self.case("cycle")
		self.assertEqual(answer["status"], "ok", json.dumps(answer)[:600])
		self.assertEqual(answer["errors"], [])
		self.assertEqual(answer["probe"]["cycle"], "AA")

	def test_vueuse_core_resolves(self):
		"""The ninth import specifier, loaded on demand."""
		answer = self.case("vueuse")
		self.assertEqual(answer["status"], "ok", json.dumps(answer)[:600])
		self.assertEqual(answer["errors"], [])
		self.assertEqual(answer["probe"]["counter"], "3")

	def test_an_imported_css_file_becomes_a_stylesheet(self):
		answer = self.case("css")
		self.assertEqual(answer["status"], "ok", json.dumps(answer)[:600])
		self.assertEqual(answer["errors"], [])
		self.assertEqual(answer["probe"]["colour"], "rgb(1, 2, 3)")
		self.assertEqual(answer["probe"]["styleTags"], ["src/style.css"])

	def test_a_closing_script_tag_in_a_file_survives_the_browser(self):
		"""Trap 1, read from the rendered DOM instead of the served HTML."""
		answer = self.case("closing-script-tag")
		self.assertEqual(answer["status"], "ok", json.dumps(answer)[:600])
		self.assertEqual(answer["errors"], [])
		self.assertEqual(answer["probe"]["closing"], "</script>")

	# ------------------------------------------------------------- the whole set

	def test_no_case_logged_a_console_error(self):
		"""A console error the Runtime does not report is a silent failure."""
		for name, answer in self.answers.items():
			with self.subTest(case=name):
				self.assertEqual(answer.get("consoleErrors"), [], json.dumps(answer)[:600])
