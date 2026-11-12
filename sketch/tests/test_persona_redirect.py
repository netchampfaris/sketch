# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""A panel a page opens as it redirects stays open while the Viewer shows a persona, in a real browser.

A persona is an app-wide demo state, so its pick rides in the URL as `?s=`. Old, below, does what an old route
does as it mounts: `router.replace('/')`, then opens a panel that closes on any route change. The redirect names no
query, so it used to land without `?s=`, and Sketch wrote it back with a second navigation a tick later, which shut
the panel if it was open by then. Old opens it as the redirect lands, so that is every time, not a race. The picks now ride along in the redirect itself (`runtime/variants/state.ts`, `carryPicks`).

`persona_redirect.mjs` follows a link to Old as Grace, types Old's address as Grace, and follows the link with no
persona, and reports what it saw.

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

SCRIPT = "persona_redirect.mjs"

TREE = {
	"src/App.vue": (
		"<script setup lang='ts'>\nimport { watch } from 'vue'\nimport { RouterView, useRoute } from 'vue-router'\n"
		"import { useDemoState } from 'sketch:variants'\nimport { ui } from './ui'\n\n"
		"const viewAs = useDemoState('View as', ['Ada', 'Grace'])\nconst route = useRoute()\n"
		"watch(() => route.fullPath, () => (ui.panel = false))\n</script>\n\n"
		"<template>\n  <div class='min-h-screen w-full bg-surface-base p-8 text-ink-gray-8'>\n"
		"    <p>Viewing as {{ viewAs }}</p>\n    <RouterView />\n"
		"    <aside v-if='ui.panel' class='fixed right-4 top-4 rounded border p-4'>Notifications panel</aside>\n"
		"  </div>\n</template>\n"
	),
	"src/ui.ts": "import { reactive } from 'vue'\n\nexport const ui = reactive({ panel: false })\n",
	"src/pages/Home.vue": (
		"<script setup>\nimport { RouterLink } from 'vue-router'\n</script>\n\n"
		"<template>\n  <h1 class='text-2xl font-semibold'>Home page</h1>\n"
		"  <RouterLink to='/old'>Old link</RouterLink>\n</template>\n"
	),
	"src/pages/Old.vue": (
		"<script setup>\nimport { onMounted } from 'vue'\nimport { useRouter } from 'vue-router'\nimport { ui } from '../ui'\n\n"
		"const router = useRouter()\nonMounted(() => router.replace('/').then(() => (ui.panel = true)))\n</script>\n\n"
		"<template>\n  <p>Old page</p>\n</template>\n"
	),
	"src/router.ts": (
		"import type { RouteRecordRaw } from 'vue-router'\n"
		"import Home from './pages/Home.vue'\nimport Old from './pages/Old.vue'\n\n"
		"const routes: RouteRecordRaw[] = [\n"
		"  { path: '/', name: 'Home', component: Home, meta: { title: 'Home' } },\n"
		"  { path: '/old', name: 'Old', component: Old, meta: { title: 'Old' } },\n]\n\n"
		"export default routes\n"
	),
}


class TestPanelStaysOpenOnARedirectAsAPersona(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()

		reason = utils.node_reason() or utils.webserver_reason()
		if not reason and not os.path.isfile(frappe.get_app_path("sketch", *SHELL_HTML)):
			reason = "the frontend is not built, so there is no shell page"
		if reason:
			raise unittest.SkipTest(reason)

		cls.owner = utils.make_user("perred", "d2tperred")
		cls.addClassCleanup(utils.drop_user, cls.owner)
		cls.doc = utils.make_prototype(cls.owner, "d2t-persona-redirect", files=TREE)
		cls.addClassCleanup(utils.drop_prototype, cls.doc.name)
		frappe.db.commit()

		sid, _ = open_session(cls.owner)
		cls.addClassCleanup(delete_session, sid)
		viewer = f"/u/{utils.username_of(cls.owner)}/{cls.doc.slug}"
		cls.link = cls.drive(viewer, sid, "link")
		cls.hash = cls.drive(viewer, sid, "hash")
		cls.bare = cls.drive(viewer, sid, "bare")

	@classmethod
	def drive(cls, viewer: str, sid: str, mode: str) -> dict:
		entry = f"{utils.playwright_root()}/playwright/index.mjs"
		run = utils.run_node(SCRIPT, entry, utils.site_host(), str(utils.webserver_port()), viewer, sid, mode)
		if run.returncode != 0:
			raise AssertionError(f"{SCRIPT} {mode} failed:\n{run.stdout[-4000:]}\n{run.stderr[-4000:]}")
		return json.loads(run.stdout)

	def say(self, answer: dict) -> str:
		return json.dumps(answer, indent=1)[:4000]

	def test_a_link_lands_home_with_the_persona_and_the_panel_open(self):
		after = self.link["after"]
		self.assertEqual(after["hash"], "#/?s=view-as.grace", self.say(self.link))
		self.assertIn("Viewing as Grace", after["text"], self.say(self.link))
		self.assertTrue(after["panelOpen"], self.say(self.link))

	def test_back_returns_to_home_as_the_persona(self):
		self.assertEqual(self.link["back"]["hash"], "#/?s=view-as.grace", self.say(self.link))
		self.assertIn("Home page", self.link["back"]["text"], self.say(self.link))

	def test_typing_the_old_address_lands_the_same(self):
		after = self.hash["after"]
		self.assertEqual(after["hash"], "#/?s=view-as.grace", self.say(self.hash))
		self.assertTrue(after["panelOpen"], self.say(self.hash))

	def test_with_no_persona_the_url_stays_bare(self):
		after = self.bare["after"]
		self.assertEqual(after["hash"], "#/", self.say(self.bare))
		self.assertIn("Viewing as Ada", after["text"], self.say(self.bare))
		self.assertTrue(after["panelOpen"], self.say(self.bare))
