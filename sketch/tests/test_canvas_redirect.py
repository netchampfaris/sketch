# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The canvas stays open on a Prototype whose page sends the person elsewhere as it mounts, in a real browser.

The canvas draws each page by rendering the whole app offscreen in it (`runtime/variants/Frame.vue`). Gate, below,
calls `useRouter().replace({ path: '/' })` in `onMounted`, as a sign-in gate or an old route does. Once that moved
the live page, which dropped `?canvas=` and shut the canvas a second after it opened. Each render now gets a router
whose navigation does nothing.

`canvas_redirect.mjs` opens the canvas on Gate's set from Home and reports what it saw. The control opens Gate
itself: outside the canvas the redirect still lands.

Skips when node, Playwright, the web server or the built shell is absent. A skip is not a pass.
"""

import json
import os
import unittest

import frappe
from frappe.sessions import delete_session
from frappe.tests import IntegrationTestCase

from sketch.tests import utils
from sketch.tests.test_viewer_api import open_session
from sketch.viewer import SHELL_HTML

SCRIPT = "canvas_redirect.mjs"

TREE = {
	"src/App.vue": (
		"<script setup lang='ts'>\nimport { RouterView } from 'vue-router'\n</script>\n\n"
		"<template>\n  <div class='min-h-screen w-full bg-surface-base p-8 text-ink-gray-8'>\n"
		"    <RouterView />\n  </div>\n</template>\n"
	),
	"src/pages/Home.vue": "<template>\n  <h1 class='text-2xl font-semibold'>Home page</h1>\n</template>\n",
	"src/pages/Gate.vue": (
		"<script setup>\nimport { onMounted } from 'vue'\nimport { useRouter } from 'vue-router'\n"
		"import { Variants } from 'sketch:variants'\n\n"
		"const router = useRouter()\nonMounted(() => router.replace({ path: '/' }))\n</script>\n\n"
		"<template>\n  <Variants name='Banner'>\n"
		"    <template #plain><p class='text-base'>Plain banner</p></template>\n"
		"    <template #bold><p class='text-xl font-bold'>Bold banner</p></template>\n"
		"  </Variants>\n</template>\n"
	),
	"src/router.ts": (
		"import type { RouteRecordRaw } from 'vue-router'\n"
		"import Home from './pages/Home.vue'\nimport Gate from './pages/Gate.vue'\n\n"
		"const routes: RouteRecordRaw[] = [\n"
		"  { path: '/', name: 'Home', component: Home, meta: { title: 'Home' } },\n"
		"  { path: '/gate', name: 'Gate', component: Gate, meta: { title: 'Gate' } },\n]\n\n"
		"export default routes\n"
	),
}


class TestCanvasStaysOpenOnARedirectingPage(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()

		reason = utils.node_reason() or utils.webserver_reason()
		if not reason and not os.path.isfile(frappe.get_app_path("sketch", *SHELL_HTML)):
			reason = "the frontend is not built, so there is no shell page"
		if reason:
			raise unittest.SkipTest(reason)

		cls.owner = utils.make_user("cnvred", "d2tcnvred")
		cls.addClassCleanup(utils.drop_user, cls.owner)
		cls.doc = utils.make_prototype(cls.owner, "d2t-canvas-redirect", files=TREE)
		cls.addClassCleanup(utils.drop_prototype, cls.doc.name)
		frappe.db.commit()

		sid, _ = open_session(cls.owner)
		cls.addClassCleanup(delete_session, sid)
		viewer = f"/u/{utils.username_of(cls.owner)}/{cls.doc.slug}"
		cls.canvas = cls.drive(viewer, sid, "canvas")
		cls.direct = cls.drive(viewer, sid, "direct")

	@classmethod
	def drive(cls, viewer: str, sid: str, mode: str) -> dict:
		entry = f"{utils.playwright_root()}/playwright/index.mjs"
		run = utils.run_node(SCRIPT, entry, utils.site_host(), str(utils.webserver_port()), viewer, sid, mode)
		if run.returncode != 0:
			raise AssertionError(f"{SCRIPT} {mode} failed:\n{run.stdout[-4000:]}\n{run.stderr[-4000:]}")
		return json.loads(run.stdout)

	def say(self, answer: dict) -> str:
		return json.dumps(answer, indent=1)[:4000]

	def test_the_canvas_stays_open(self):
		self.assertIn("canvas=", self.canvas["hash"], self.say(self.canvas))
		self.assertTrue(self.canvas["canvasOpen"], self.say(self.canvas))

	def test_the_tiles_draw_the_page_as_opened(self):
		"""Each tile shows its own option of Gate's set, not Home, where the redirect would have gone."""
		text = "\n".join(self.canvas["tileText"])
		self.assertIn("Plain banner", text, self.say(self.canvas))
		self.assertIn("Bold banner", text, self.say(self.canvas))
		self.assertNotIn("Home page", text, self.say(self.canvas))

	def test_outside_the_canvas_the_page_still_redirects(self):
		self.assertEqual(self.direct["hash"], "#/", self.say(self.direct))
		self.assertIn("Home page", self.direct["text"], self.say(self.direct))
