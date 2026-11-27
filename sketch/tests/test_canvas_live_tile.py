# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""A set tile made live shows its page, in a real browser, even when the set has no box of its own.

A live set tile lifts the set out of its page (`runtime/variants/lift.ts`): everything but the set's elements is
hidden. Layout's options below render only a `<span hidden>`, as a slot that just flips a design flag does, so they
have no box. Lifting them once hid the whole page, and the live tile went blank. Such a set now shows the whole page,
as its snapshot does.

`canvas_live_tile.mjs` opens the canvas on Layout's set, clicks a tile and reports what the live tile shows.

A page that throws as it mounts has nothing to lift either. Its live tile shows the frame's alert, with the message.

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

SCRIPT = "canvas_live_tile.mjs"

TREE = {
	"src/App.vue": (
		"<script setup lang='ts'>\nimport { RouterView } from 'vue-router'\n</script>\n\n"
		"<template>\n  <div class='min-h-screen w-full bg-surface-base p-8 text-ink-gray-8'>\n"
		"    <RouterView />\n  </div>\n</template>\n"
	),
	"src/pages/Home.vue": (
		"<script setup>\nimport { Variants } from 'sketch:variants'\n</script>\n\n"
		"<template>\n  <div>\n    <Variants name='Layout'>\n"
		"      <template #compact><span hidden /></template>\n"
		"      <template #roomy><span hidden /></template>\n"
		"    </Variants>\n    <h1 class='text-2xl font-semibold'>Home page</h1>\n  </div>\n</template>\n"
	),
	# A page that throws as it mounts, in one of its states.
	"src/pages/Broken.vue": (
		"<script setup>\nimport { useDemoState } from 'sketch:variants'\n\n"
		"const data = useDemoState('Data', ['Full', 'Empty'])\n"
		"if (data.value === 'Empty') throw new Error('No rows to draw')\n</script>\n\n"
		"<template>\n  <h1 class='text-2xl font-semibold'>Broken page, {{ data }}</h1>\n</template>\n"
	),
	"src/router.ts": (
		"import type { RouteRecordRaw } from 'vue-router'\nimport Home from './pages/Home.vue'\n"
		"import Broken from './pages/Broken.vue'\n\n"
		"const routes: RouteRecordRaw[] = [\n"
		"  { path: '/', name: 'Home', component: Home, meta: { title: 'Home' } },\n"
		"  { path: '/broken', name: 'Broken', component: Broken, meta: { title: 'Broken' } },\n"
		"]\n\n"
		"export default routes\n"
	),
}


class TestLiveTileOfASetWithNoBox(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()

		reason = utils.node_reason() or utils.webserver_reason()
		if not reason and not os.path.isfile(frappe.get_app_path("sketch", *SHELL_HTML)):
			reason = "the frontend is not built, so there is no shell page"
		if reason:
			raise unittest.SkipTest(reason)

		cls.owner = utils.make_user("cnvlive", "d2tcnvlive")
		cls.addClassCleanup(utils.drop_user, cls.owner)
		cls.doc = utils.make_prototype(cls.owner, "d2t-canvas-live-tile", files=TREE)
		cls.addClassCleanup(utils.drop_prototype, cls.doc.name)
		frappe.db.commit()

		sid, _ = open_session(cls.owner)
		cls.addClassCleanup(delete_session, sid)
		viewer = f"/u/{utils.username_of(cls.owner)}/{cls.doc.slug}"
		entry = f"{utils.playwright_root()}/playwright/index.mjs"
		run = utils.run_node(SCRIPT, entry, utils.site_host(), str(utils.webserver_port()), viewer, sid)
		if run.returncode != 0:
			raise AssertionError(f"{SCRIPT} failed:\n{run.stdout[-4000:]}\n{run.stderr[-4000:]}")
		cls.answer = json.loads(run.stdout)

	def say(self) -> str:
		return json.dumps(self.answer, indent=1)[:4000]

	def test_the_tile_went_live(self):
		self.assertTrue(self.answer["live"], self.say())

	def test_the_live_tile_shows_the_page(self):
		self.assertTrue(self.answer["headingVisible"], self.say())
		self.assertIn("Home page", self.answer["liveText"], self.say())

	def test_a_live_tile_of_a_page_that_throws_says_so(self):
		# The live frame's own alert, with the page's message: seen, and not left under a tile that waits for it to paint.
		thrown = self.answer["thrown"]
		self.assertIn("Could not render this page", thrown["text"], self.say())
		self.assertIn("No rows to draw", thrown["text"], self.say())
		self.assertTrue(thrown["visible"], self.say())
		self.assertNotEqual(thrown["pointer"], "none", self.say())
