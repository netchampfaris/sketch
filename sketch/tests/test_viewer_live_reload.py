# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The sandboxed Viewer in a real browser: does it boot, does it reload.

The sandbox in `sketch/viewer.py` puts every Viewer document, the owner's own
included, in an opaque origin. Two things had to keep working there, and only a
browser can say whether they do:

- the Runtime boots. Every one of its requests is cross-origin in an opaque
  origin, and `localStorage` throws.
- the owner's live reload runs. The page sends no cookie, so the poller
  authenticates with the signature the renderer minted into the payload
  (`sketch.api.signed_revision`), and reloads when the revision moves.

`viewer_live_reload.mjs` drives one headless Chromium and prints one JSON
document. This module reads it and makes the assertions. The node run happens
once for the class, because a browser launch costs more than the whole suite.

Skips when node, Playwright or the web server is absent. A skip is not a pass.
"""

import json
import unittest

from frappe.tests import IntegrationTestCase

from sketch import prototype_files
from sketch.tests import utils

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
		if reason:
			raise unittest.SkipTest(reason)

		cls.user = utils.make_user("sblive", "d2tsblive")
		cls.addClassCleanup(utils.drop_user, cls.user)
		cls.doc = utils.make_prototype(cls.user, "d2t-sblive", files=TREE)
		cls.addClassCleanup(utils.drop_prototype, cls.doc.name)

		entry = f"{utils.playwright_root()}/playwright/index.mjs"
		run = utils.run_node(
			SCRIPT,
			entry,
			utils.site_host(),
			str(utils.webserver_port()),
			f"/u/{utils.username_of(cls.user)}/{cls.doc.slug}",
			utils.api_auth_header(cls.user)["Authorization"],
			prototype_files.prototype_dir(cls.doc.name),
		)
		if run.returncode != 0:
			raise AssertionError(f"{SCRIPT} failed:\n{run.stdout[-4000:]}\n{run.stderr[-4000:]}")

		cls.answer = json.loads(run.stdout)

	def report(self) -> str:
		return json.dumps(self.answer, indent=2)[:4000]

	# --------------------------------------------------------------- the origin

	def test_the_owners_own_tab_is_in_an_opaque_origin(self):
		"""The sandbox landed. Everything below is measured inside it."""
		self.assertEqual(self.answer["status"], 200, self.report())
		self.assertIn("sandbox allow-scripts", self.answer["csp"])
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

	def test_the_page_holds_a_credential_to_poll_with(self):
		self.assertTrue(self.answer["live"], self.report())
		self.assertTrue(self.answer["hasCredential"], self.report())

	def test_the_poller_reaches_the_endpoint_from_the_opaque_origin(self):
		"""A cookie cannot come from here, so the signature has to be enough."""
		self.assertGreaterEqual(self.answer["pollsBeforeWrite"], 1, self.report())
		self.assertEqual(self.answer["pollStatuses"], [200], self.report())

	def test_the_signature_is_what_authorises_the_read(self):
		"""One character changed is a 404, header or no header."""
		self.assertEqual(self.answer["forged"], 404, self.report())

	def test_the_tab_reloads_when_a_file_arrives(self):
		"""The core loop: the agent writes, the owner's open tab reloads."""
		self.assertTrue(self.answer["reloaded"], self.report())
