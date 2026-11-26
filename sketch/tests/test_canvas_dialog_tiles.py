# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""A set whose options are dialogs shows each dialog in its tile, and a page routed twice is listed once.

The Gallery page renders `NewPrototypeDialog`, a `<Variants>` set whose three options are each a component with a
frappe-ui `<Dialog>` at its root. The page keeps it closed; `/demo/new` routes the same page with the dialog opened as it
mounts. A dialog renders nothing in place and portals its panel to `<body>`, so its tiles once showed the page behind
with no dialog, and the two routes listed every set and state of Gallery twice.

Now, in a canvas frame (`runtime/variants/Frame.vue`), a frappe-ui Dialog portals into the frame and is never modal,
and the target set's dialogs show open. Its tiles show the panel alone, as a self-framed card. Two routes of one
component are one page in Browse (`runtime/variants/Canvas.vue` `discover`).

`canvas_dialog_tiles.mjs` drives the canvas in a real browser. Skips when node, Playwright, the web server or the built
shell is absent. A skip is not a pass.
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

SCRIPT = "canvas_dialog_tiles.mjs"


def option(title: str, field: str) -> str:
	"""One option of the set: a component whose root is a frappe-ui Dialog, with an autofocused field."""
	return (
		"<script setup>\nimport { Dialog } from 'frappe-ui'\n"
		"const open = defineModel('open', { type: Boolean, default: false })\n</script>\n\n"
		f"<template>\n  <Dialog v-model:open='open' title='{title}'>\n"
		f"    <div class='flex flex-col gap-3'><p>{title} body</p>"
		f"<input autofocus class='rounded border px-2 py-1' placeholder='{field}' /></div>\n"
		"  </Dialog>\n</template>\n"
	)


TREE = {
	"src/App.vue": (
		"<script setup lang='ts'>\nimport { RouterView } from 'vue-router'\n</script>\n\n"
		"<template>\n  <div class='min-h-screen w-full bg-surface-base p-8 text-ink-gray-8'>\n"
		"    <RouterView />\n  </div>\n</template>\n"
	),
	"src/pages/Gallery.vue": (
		"<script setup>\nimport { onMounted, ref } from 'vue'\nimport { Button } from 'frappe-ui'\n"
		"import { Variants, useDemoState } from 'sketch:variants'\n"
		"import NewPrototypeDialog from '../components/NewPrototypeDialog.vue'\n\n"
		"const props = defineProps({ openNew: { type: Boolean, default: false } })\n"
		"const data = useDemoState('Data', ['Full', 'Empty'])\n"
		"const newOpen = ref(false)\nonMounted(() => { if (props.openNew) newOpen.value = true })\n</script>\n\n"
		"<template>\n  <div class='flex flex-col gap-4'>\n    <h1 class='text-2xl font-semibold'>Gallery page</h1>\n"
		"    <Button label='New prototype' @click='newOpen = true' />\n"
		"    <Variants name='Gallery body'>\n"
		"      <template #grid><div class='rounded border p-4'>Grid of {{ data }}</div></template>\n"
		"      <template #list><div class='rounded border p-4'>List of {{ data }}</div></template>\n"
		"    </Variants>\n"
		"    <NewPrototypeDialog v-model:open='newOpen' />\n  </div>\n</template>\n"
	),
	"src/components/NewPrototypeDialog.vue": (
		"<script setup>\nimport { Variants } from 'sketch:variants'\n"
		"import NewSimple from './NewSimple.vue'\nimport NewRecipe from './NewRecipe.vue'\nimport NewBlank from './NewBlank.vue'\n"
		"const open = defineModel('open', { type: Boolean, default: false })\n</script>\n\n"
		"<template>\n  <Variants name='New prototype'>\n"
		"    <template #simple><NewSimple v-model:open='open' /></template>\n"
		"    <template #recipe><NewRecipe v-model:open='open' /></template>\n"
		"    <template #blank><NewBlank v-model:open='open' /></template>\n"
		"  </Variants>\n</template>\n"
	),
	"src/components/NewSimple.vue": option("Simple start", "Name"),
	"src/components/NewRecipe.vue": option("From a recipe", "Recipe"),
	"src/components/NewBlank.vue": option("Blank prototype", "Title"),
	"src/router.ts": (
		"import type { RouteRecordRaw } from 'vue-router'\nimport Gallery from './pages/Gallery.vue'\n\n"
		# The demo route comes first: the canvas still renders Gallery from the plain one.
		"const routes: RouteRecordRaw[] = [\n"
		"  { path: '/demo/new', component: Gallery, props: () => ({ openNew: true }) },\n"
		"  { path: '/', component: Gallery },\n"
		"]\n\nexport default routes\n"
	),
}


class TestCanvasDialogTiles(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()

		reason = utils.node_reason() or utils.webserver_reason()
		if not reason and not os.path.isfile(frappe.get_app_path("sketch", *SHELL_HTML)):
			reason = "the frontend is not built, so there is no shell page"
		if reason:
			raise unittest.SkipTest(reason)

		cls.owner = utils.make_user("cnvdlg", "d2tcnvdlg")
		cls.addClassCleanup(utils.drop_user, cls.owner)
		cls.doc = utils.make_prototype(cls.owner, "d2t-canvas-dialog-tiles", files=TREE)
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

	# ---- The dialog set

	def test_every_tile_shows_its_dialog_panel(self):
		tiles = self.answer["tiles"]
		self.assertEqual(len(tiles), 3, self.say())
		titles = ["Simple start", "From a recipe", "Blank prototype"]
		for tile, title in zip(tiles, titles, strict=True):
			self.assertTrue(tile["panelVisible"], self.say())
			self.assertIn(title, tile["panelText"], self.say())

	def test_a_tile_is_the_panel_alone(self):
		for tile in self.answer["tiles"]:
			# The panel's own size, as a self-framed card: no tile surface, no backdrop, no page behind.
			self.assertTrue(tile["card"], self.say())
			self.assertAlmostEqual(tile["w"], tile["panelW"], delta=1, msg=self.say())
			self.assertAlmostEqual(tile["h"], tile["panelH"], delta=1, msg=self.say())
			self.assertLess(tile["w"], 1280, self.say())
			self.assertFalse(tile["pageVisible"], self.say())
			self.assertFalse(tile["backdropVisible"], self.say())

	def test_tile_dialogs_leave_the_real_page_alone(self):
		for state in (self.answer["drawnState"], self.answer["liveState"]):
			self.assertEqual(state["dialogsOutside"], 0, self.say())
			self.assertNotEqual(state["bodyPointer"], "none", self.say())
			self.assertFalse(state["scrollLocked"], self.say())
			self.assertEqual(state["canvasHidden"], [], self.say())
		# Drawing the tiles never moves focus into one, though every option has an autofocused field.
		self.assertFalse(self.answer["drawnState"]["focusInTile"], self.say())
		self.assertEqual(self.answer["drawnState"]["focusedInTiles"], 0, self.say())

	def test_a_live_tile_shows_its_dialog(self):
		live = [t for t in self.answer["liveTiles"] if t["live"]]
		self.assertEqual(len(live), 1, self.say())
		self.assertTrue(live[0]["panelVisible"], self.say())
		self.assertFalse(live[0]["pageVisible"], self.say())

	def test_escape_still_reaches_the_canvas(self):
		self.assertFalse(self.answer["liveAfterEscape"], self.say())
		self.assertIn("canvas=", self.answer["hashAfterEscape"], self.say())

	def test_the_page_dialog_is_still_modal(self):
		dialog = self.answer["pageDialog"]
		self.assertTrue(dialog["inBody"], self.say())
		self.assertEqual(dialog["state"], "open", self.say())
		self.assertEqual(dialog["bodyPointer"], "none", self.say())

	def test_no_errors(self):
		# Chrome declines the autofocus these fields ask for, in a cross-origin frame, and logs it. That is the browser, not us.
		errors = [e for e in self.answer["errors"] if not e.startswith("Blocked autofocusing")]
		self.assertEqual(errors, [], self.say())

	# ---- Two routes, one component

	def test_browse_lists_the_page_once(self):
		for browse in (self.answer["browse"], self.answer["demoBrowse"]):
			# A row's first line is its name: the two sets, and Gallery for the page's states.
			names = [r.split("\n")[0] for r in browse]
			self.assertEqual(sorted(names), ["Gallery", "Gallery body", "New prototype"], self.say())

	def test_links_from_either_route_open(self):
		self.assertEqual(len(self.answer["demoTiles"]), 3, self.say())
		self.assertTrue(all(t["panelVisible"] for t in self.answer["demoTiles"]), self.say())
		# page: names the route it was opened on; it still opens Gallery's states.
		self.assertIn("canvas=page", self.answer["pageLinkHash"], self.say())
		self.assertEqual(len(self.answer["pageLinkTiles"]), 2, self.say())

	def test_the_page_renders_from_its_plain_route(self):
		# Not from /demo/new, which opens the dialog over the page as it mounts.
		for tile in self.answer["tiles"] + self.answer["pageLinkTiles"]:
			self.assertTrue(tile["id"].startswith("/|"), self.say())
		for tile in self.answer["pageLinkTiles"]:
			self.assertTrue(tile["pageVisible"], self.say())
			self.assertFalse(tile["panelVisible"], self.say())
