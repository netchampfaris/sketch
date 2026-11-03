# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The Viewer in a real browser: does the frame boot, does the shell reload it.

The Viewer is a shell on Sketch's origin with the Prototype in a sandboxed frame
(`sketch/viewer.py`). Two things have to work, and only a browser can say
whether they do:

- the Runtime boots in the frame. It lands in an opaque origin, so every one of
  its requests is cross-origin, and `localStorage` throws.
- the owner's live reload runs. The shell polls `sketch.api.prototype_revision`
  with the owner's session (runtime/shell/liveReload.ts) and reloads the frame,
  and only the frame, when the revision moves.

`viewer_live_reload.mjs` drives one headless Chromium and prints one JSON
document. This module reads it and makes the assertions. The node run happens
once for the class, because a browser launch costs more than the whole suite.

Skips when node, Playwright, the web server or the built shell is absent. A skip is not a pass.
"""

import json
import os
import unittest

import frappe
from frappe.sessions import delete_session
from frappe.tests import IntegrationTestCase

from sketch import prototype_files
from sketch.tests import utils
from sketch.tests.test_viewer_api import open_session
from sketch.viewer import SHELL_HTML

SCRIPT = "viewer_live_reload.mjs"

#: A tree that mounts and paints one heading, so a boot can be told from a
#: status screen. `check` walks the router, so the router file is not optional.
TREE = {
	"src/App.vue": (
		"<script setup lang='ts'>\nimport { RouterView } from 'vue-router'\n</script>\n\n"
		"<template>\n  <div class='h-screen w-full bg-surface-base text-ink-gray-8'>\n"
		"    <RouterView />\n  </div>\n</template>\n"
	),
	"src/pages/Home.vue": (
		"<template>\n  <div class='p-5'>\n"
		"    <h1 class='text-2xl-semibold text-ink-gray-8'>Sandboxed</h1>\n"
		"  </div>\n</template>\n"
	),
	"src/router.ts": (
		"import type { RouteRecordRaw } from 'vue-router'\n"
		"import Home from './pages/Home.vue'\n\n"
		"const routes: RouteRecordRaw[] = [{ path: '/', name: 'Home', component: Home }]\n\n"
		"export default routes\n"
	),
}


class TestSandboxedViewerInABrowser(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()

		reason = utils.node_reason() or utils.webserver_reason()
		if not reason and not os.path.isfile(frappe.get_app_path("sketch", *SHELL_HTML)):
			reason = "the frontend is not built, so there is no shell page"
		if reason:
			raise unittest.SkipTest(reason)

		cls.user = utils.make_user("sblive", "d2tsblive")
		cls.addClassCleanup(utils.drop_user, cls.user)
		cls.doc = utils.make_prototype(cls.user, "d2t-sblive", files=TREE)
		cls.addClassCleanup(utils.drop_prototype, cls.doc.name)
		sid, _ = open_session(cls.user)
		cls.addClassCleanup(delete_session, sid)

		entry = f"{utils.playwright_root()}/playwright/index.mjs"
		run = utils.run_node(
			SCRIPT,
			entry,
			utils.site_host(),
			str(utils.webserver_port()),
			f"/u/{utils.username_of(cls.user)}/{cls.doc.slug}",
			sid,
			prototype_files.prototype_dir(cls.doc.name),
		)
		if run.returncode != 0:
			raise AssertionError(f"{SCRIPT} failed:\n{run.stdout[-4000:]}\n{run.stderr[-4000:]}")

		cls.answer = json.loads(run.stdout)

	def report(self) -> str:
		return json.dumps(self.answer, indent=2)[:4000]

	# --------------------------------------------------------------- the origin

	def test_the_shell_is_on_sketchs_origin_and_the_frame_in_an_opaque_one(self):
		"""The sandbox landed on the frame and not on the shell. Everything below is measured there."""
		self.assertEqual(self.answer["status"], 200, self.report())
		self.assertNotIn("sandbox", self.answer["csp"])
		self.assertNotEqual(self.answer["shellOrigin"], "null", self.report())
		self.assertEqual(self.answer["frameStatus"], 200, self.report())
		self.assertIn("sandbox allow-scripts", self.answer["frameCsp"])
		self.assertEqual(self.answer["origin"], "null", self.report())
		self.assertEqual(self.answer["csrf"], "undefined", self.report())

	# ---------------------------------------------------------------- the boot

	def test_the_runtime_still_boots_under_the_sandbox(self):
		"""Every Runtime request is cross-origin here, and Inter is a font."""
		self.assertEqual(self.answer["bootStatus"], "ok", self.report())
		self.assertEqual(self.answer["errors"], [], self.report())
		self.assertEqual(self.answer["consoleErrors"], [], self.report())
		self.assertEqual(self.answer["heading"], "Sandboxed", self.report())

	# ---------------------------------------------------------- the live reload

	def test_the_frame_holds_nothing_to_poll_with(self):
		self.assertEqual(utils.credential_keys(dict.fromkeys(self.answer["frameKeys"])), [], self.report())
		self.assertNotIn("rev", self.answer["frameKeys"], self.report())

	def test_the_shell_polls_with_the_session(self):
		self.assertGreaterEqual(self.answer["pollsBeforeWrite"], 1, self.report())
		self.assertEqual(self.answer["pollStatuses"], [200], self.report())

	def test_the_session_is_what_authorises_the_read(self):
		"""The same URL with no cookie is refused."""
		self.assertIn(self.answer["withoutSession"], (403, 404), self.report())

	def test_the_frame_reloads_when_a_file_arrives_and_the_shell_stays(self):
		"""The core loop: the agent writes, the owner's open frame reloads, the shell's state stays put."""
		self.assertTrue(self.answer["reloaded"], self.report())
		self.assertTrue(self.answer["shellKept"], self.report())
