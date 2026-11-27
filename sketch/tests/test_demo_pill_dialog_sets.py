# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The Demo pill lists a set inside a dialog, open or closed, and under an open dialog it is as it was.

`AccountContent.vue` holds `<Variants name="Account style">`. The `/account` page renders it, and so does
`AccountDialog.vue`, a frappe-ui Dialog mounted in App.vue (outside RouterView) and opened from the sidebar on every
page. A closed Dialog does not mount its content, so the set once registered only while the dialog was open, and then
the pill was under the dialog's backdrop: the set could never be switched.

Now the frame finds the sets behind closed dialogs with a hidden render (`runtime/variants/Discover.vue`), the pill
lists them after the sets on screen, a pick made while closed is what the dialog opens on, and the page copy and the
dialog copy of one set are one row (`runtime/variants/model.ts`). Over an open dialog the pill is as it was: under the
backdrop, and a press on it closes the dialog.

`demo_pill_dialog_sets.mjs` drives the Viewer in a real browser. Skips when node, Playwright, the web server or the
built shell is absent. A skip is not a pass.
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

SCRIPT = "demo_pill_dialog_sets.mjs"

TREE = {
	"src/App.vue": (
		"<script setup lang='ts'>\nimport { ref } from 'vue'\nimport { RouterView, RouterLink } from 'vue-router'\n"
		"import { Button } from 'frappe-ui'\nimport AccountDialog from './components/AccountDialog.vue'\n"
		"const accountOpen = ref(false)\n</script>\n\n"
		"<template>\n  <div class='flex min-h-screen w-full bg-surface-base text-ink-gray-8'>\n"
		"    <aside class='flex w-48 flex-col gap-2 border-r p-4'>\n"
		"      <RouterLink to='/'>Home</RouterLink><RouterLink to='/account'>Account page</RouterLink>"
		"<RouterLink to='/reports'>Reports</RouterLink>\n"
		"      <Button label='Account settings' @click='accountOpen = true' />\n    </aside>\n"
		"    <main class='flex-1 p-8'><RouterView /></main>\n"
		"    <AccountDialog v-model:open='accountOpen' />\n  </div>\n</template>\n"
	),
	"src/components/AccountContent.vue": (
		"<script setup>\nimport { Variants } from 'sketch:variants'\n</script>\n\n"
		"<template>\n  <Variants name='Account style'>\n"
		"    <template #compact><p class='account-style'>Style compact</p></template>\n"
		"    <template #detailed><p class='account-style'>Style detailed</p></template>\n"
		"    <template #tabs><p class='account-style'>Style tabs</p></template>\n"
		"  </Variants>\n</template>\n"
	),
	"src/components/AccountDialog.vue": (
		"<script setup>\nimport { Dialog } from 'frappe-ui'\nimport AccountContent from './AccountContent.vue'\n"
		"const open = defineModel('open', { type: Boolean, default: false })\n</script>\n\n"
		"<template>\n  <Dialog v-model:open='open' title='Account settings'>\n    <AccountContent />\n  </Dialog>\n</template>\n"
	),
	"src/pages/Home.vue": (
		"<script setup>\nimport { Variants } from 'sketch:variants'\n</script>\n\n"
		"<template>\n  <h1 class='text-2xl font-semibold'>Home</h1>\n  <Variants name='Home layout'>\n"
		"    <template #grid><div class='rounded border p-4'>Grid</div></template>\n"
		# A set inside an unpicked option: never listed while Grid shows.
		"    <template #list><div class='rounded border p-4'>List<Variants name='List density'>"
		"<template #tight><span>Tight</span></template><template #loose><span>Loose</span></template></Variants></div></template>\n"
		"  </Variants>\n</template>\n"
	),
	"src/pages/Account.vue": (
		"<script setup>\nimport AccountContent from '../components/AccountContent.vue'\n</script>\n\n"
		"<template>\n  <h1 class='text-2xl font-semibold'>Account page</h1>\n  <AccountContent />\n</template>\n"
	),
	# A dialog mounted in one page: its set is listed there, and nowhere else.
	"src/pages/Reports.vue": (
		"<script setup>\nimport { ref } from 'vue'\nimport { Button, Dialog } from 'frappe-ui'\nimport { Variants } from 'sketch:variants'\n"
		"const open = ref(false)\nconst summary = ref(true)\n</script>\n\n"
		"<template>\n  <h1 class='text-2xl font-semibold'>Reports</h1>\n  <Button label='Filters' @click='open = true' />\n"
		# A set in a section the page can take away: not behind a dialog, so it is listed only while it is drawn.
		"  <Button label='Hide summary' @click='summary = false' />\n"
		"  <Variants v-if='summary' name='Summary style'>\n"
		"    <template #short><p>Short summary</p></template><template #long><p>Long summary</p></template>\n  </Variants>\n"
		"  <Dialog v-model:open='open' title='Filters'>\n    <Variants name='Report filters'>\n"
		"      <template #simple><p>Simple filters</p></template><template #advanced><p>Advanced filters</p></template>\n"
		"    </Variants>\n  </Dialog>\n</template>\n"
	),
	"src/router.ts": (
		"import type { RouteRecordRaw } from 'vue-router'\nimport Home from './pages/Home.vue'\n"
		"import Account from './pages/Account.vue'\nimport Reports from './pages/Reports.vue'\n\n"
		"const routes: RouteRecordRaw[] = [\n  { path: '/', component: Home },\n"
		"  { path: '/account', component: Account },\n  { path: '/reports', component: Reports },\n]\n\nexport default routes\n"
	),
}


class TestDemoPillDialogSets(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()

		reason = utils.node_reason() or utils.webserver_reason()
		if not reason and not os.path.isfile(frappe.get_app_path("sketch", *SHELL_HTML)):
			reason = "the frontend is not built, so there is no shell page"
		if reason:
			raise unittest.SkipTest(reason)

		cls.owner = utils.make_user("pilldlg", "d2tpilldlg")
		cls.addClassCleanup(utils.drop_user, cls.owner)
		cls.doc = utils.make_prototype(cls.owner, "d2t-demo-pill-dialog-sets", files=TREE)
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
		return json.dumps(self.answer, indent=1)[:6000]

	# ---- 1. Listed while the dialog is closed

	def test_the_dialog_set_is_listed_while_closed(self):
		# On screen first, the dialog's set after it; the set in Home layout's unpicked option and the other page's
		# dialog set are not listed.
		self.assertEqual(self.answer["homeRows"], ["Home layout", "Account style"], self.say())
		self.assertFalse(self.answer["homeDialogOpen"], self.say())

	def test_hovering_a_set_behind_a_dialog_outlines_nothing(self):
		self.assertTrue(self.answer["outlineOnScreen"], self.say())
		self.assertFalse(self.answer["outlineHidden"], self.say())

	def test_a_pick_while_closed_is_what_the_dialog_opens_on(self):
		self.assertIn("account-style.detailed", self.answer["hashAfterPick"], self.say())
		self.assertEqual(self.answer["dialogShows"], "Style detailed", self.say())

	def test_a_page_dialog_set_is_listed_on_its_page_only(self):
		self.assertEqual(self.answer["reportsRows"], ["Summary style", "Report filters", "Account style"], self.say())

	def test_a_set_not_behind_a_dialog_leaves_the_pill_when_it_unmounts(self):
		# The page has a closed dialog, so it is looked behind; the set in the section taken away is not one of its finds.
		self.assertEqual(self.answer["reportsRowsHidden"], ["Report filters", "Account style"], self.say())
		self.assertNotIn("summary-style", self.answer["reportsHashHidden"], self.say())

	# ---- The pill over an open dialog, as before

	def test_the_pill_is_under_an_open_dialog_as_before(self):
		under = self.answer["underDialog"]
		self.assertTrue(under["tint"], self.say())
		self.assertTrue(under["inert"], self.say())
		# A press on it is a press on the backdrop: the dialog closes.
		self.assertFalse(under["dialogOpenAfterPress"], self.say())

	def test_the_row_stays_after_the_dialog_closes(self):
		under = self.answer["underDialog"]
		self.assertEqual(under["rows"], ["Home layout", "Account style"], self.say())
		self.assertEqual(under["current"], "Account style: Detailed", self.say())

	# ---- 4. One set mounted twice is one row

	def test_the_page_copy_and_the_dialog_copy_are_one_row(self):
		both = self.answer["accountBoth"]
		# With the dialog open over the page, and closed again.
		self.assertEqual(both["rows"], ["Account style"], self.say())
		self.assertEqual(both["rowsClosed"], ["Account style"], self.say())
		# One pick, both copies.
		self.assertEqual(both["shown"], ["Style compact", "Style compact"], self.say())

	def test_open_page_from_a_canvas_tile_picks_both_copies(self):
		# Both copies were on Tabs; the page's tile for Compact, the default, was opened as a page.
		opened = self.answer["openedPage"]
		self.assertEqual(opened["page"], ["Style compact"], self.say())
		self.assertEqual(opened["shown"], ["Style compact", "Style compact"], self.say())
		# The link names no option: the dialog copy is not left on Tabs.
		self.assertNotIn("account-style.", opened["hash"], self.say())

	def test_no_errors(self):
		self.assertEqual(self.answer["errors"], [], self.say())
