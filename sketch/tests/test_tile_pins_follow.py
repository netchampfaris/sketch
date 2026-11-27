# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""A pin on a canvas tile stays on the element it was clicked on, whatever size the tile becomes, in a real browser.

A tile pin used to keep only the click as a fraction of its tile. Tiles hug their variant, so a variant drawn at a new
width moved every pin onto whatever now sat at that fraction. A tile click now also keeps the element under it
(`target`: a selector inside the tile's drawing, the click as a fraction of the element, and the element's tag, words
and label), and the pin sits on that element while its tile draws it. An agent adding a block above the element shifts
the selector's places, so the element is then found by its tag, words and label. A pin made before, with no element,
still sits at its fraction of the tile.

`tile_pins_follow.mjs` leaves a note and a comment on the first tile's Submit button and a comment on its No button,
and reports where the pins are. The card is then drawn wider, with a block of two lines inserted as its first child,
before the header row, and it reports again.

Skips when node, Playwright, the web server or the built shell is absent. A skip is not a pass.
"""

import json
import os
import unittest

import frappe
from frappe.sessions import delete_session
from frappe.tests import IntegrationTestCase

from sketch import annotations, comments, prototype_files
from sketch.tests import utils
from sketch.tests.test_viewer_api import open_session
from sketch.viewer import SHELL_HTML

SCRIPT = "tile_pins_follow.mjs"
TILE = {
	"kind": "set",
	"view": "set:home/card",
	"page": "Home",
	"group": "Card",
	"groupKey": "card",
	"option": "narrow",
	"optionLabel": "Narrow",
}
# The old note's spot on its tile, as a fraction: top right, clear of Submit, so no pin steps aside for another.
OLD = (0.8, 0.15)


def home(width: int, extra: str = "") -> str:
	verdict = "".join(
		f"<button class='rounded border border-outline-gray-2 px-2 py-1'>{word}</button>"
		for word in ("Strong yes", "Yes", "No", "Strong no")
	)
	card = (
		f"<div class='w-[{width}px] rounded-lg border border-outline-gray-2 bg-surface-base p-4 shadow-lg'>\n"
		f"          {extra}\n"
		"          <div class='flex items-center gap-3'><h2 class='text-lg font-semibold'>Priya Nair</h2></div>\n"
		"          <div class='mt-3'><div class='text-p-sm text-ink-gray-5'>Your verdict</div>"
		f"<div class='mt-2 flex gap-2'>{verdict}</div></div>\n"
		# Opened in a live tile, it pushes Submit down, away from where the tile's snapshot has it.
		"          <details class='mt-3'><summary>More</summary><p class='text-p-base'>One<br>Two<br>Three</p></details>\n"
		"          <div class='my-4'><button class='rounded bg-surface-gray-7 px-3 py-1 text-ink-white'>Submit</button></div>\n"
		"          <p class='text-p-base text-ink-gray-6'>Walked through the pricing page.</p>\n"
		"        </div>"
	)
	return (
		"<script setup>\nimport { Variants } from 'sketch:variants'\n</script>\n\n"
		"<template>\n  <div>\n    <Variants name='Card'>\n"
		f"      <template #narrow>\n        {card}\n      </template>\n"
		"      <template #roomy>\n        <div class='w-[360px] rounded-lg border border-outline-gray-2 bg-surface-base p-6 shadow-lg'>Roomy</div>\n      </template>\n"
		"    </Variants>\n  </div>\n</template>\n"
	)


TREE = {
	"src/App.vue": (
		"<script setup lang='ts'>\nimport { RouterView } from 'vue-router'\n</script>\n\n"
		"<template>\n  <div class='min-h-screen w-full bg-surface-base p-8 text-ink-gray-8'>\n"
		"    <RouterView />\n  </div>\n</template>\n"
	),
	"src/pages/Home.vue": home(320),
	"src/router.ts": (
		"import type { RouteRecordRaw } from 'vue-router'\nimport Home from './pages/Home.vue'\n\n"
		"const routes: RouteRecordRaw[] = [{ path: '/', name: 'Home', component: Home, meta: { title: 'Home' } }]\n\n"
		"export default routes\n"
	),
}
# What an agent's edit does to the variant: wider, and a block inserted before the header row, which moves every
# element's place among its siblings.
WIDE = home(560, "<div class='p-4 text-p-sm text-ink-gray-5'>An extra line.<br>And a second line.</div>")


def old_note() -> dict:
	"""A tile note as one was saved before tiles kept an element: the fraction of the tile only."""
	return {
		"id": "oldtile",
		"route": "/",
		"viewport": "1280x800",
		"selector": "",
		"component": "",
		"componentChain": [],
		"element": "",
		"text": "",
		"offset": {"x": OLD[0], "y": OLD[1]},
		"rect": {"x": 0, "y": 0, "w": 0, "h": 0},
		"tile": TILE,
		"note": "old note",
		"createdAt": 1794857063006,
	}


class TestTilePinsFollowTheirElement(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()

		reason = utils.node_reason() or utils.webserver_reason()
		if not reason and not os.path.isfile(frappe.get_app_path("sketch", *SHELL_HTML)):
			reason = "the frontend is not built, so there is no shell page"
		if reason:
			raise unittest.SkipTest(reason)

		cls.owner = utils.make_user("tilepin", "d2ttilepin")
		cls.addClassCleanup(utils.drop_user, cls.owner)
		cls.doc = utils.make_prototype(cls.owner, "d2t-tile-pins", files=TREE, is_public=True)
		cls.addClassCleanup(utils.drop_prototype, cls.doc.name)
		annotations.save(cls.doc.name, json.dumps({"notes": [old_note()]}), annotations.epoch(cls.doc.name))
		frappe.db.commit()

		sid, _ = open_session(cls.owner)
		cls.addClassCleanup(delete_session, sid)
		viewer = f"/u/{utils.username_of(cls.owner)}/{cls.doc.slug}"
		entry = f"{utils.playwright_root()}/playwright/index.mjs"
		evidence = os.environ.get("SKETCH_EVIDENCE")

		def run(mode: str) -> dict:
			args = [entry, utils.site_host(), str(utils.webserver_port()), viewer, sid, mode]
			if evidence:
				args.append(os.path.join(evidence, f"tilepin-{mode}.png"))
			done = utils.run_node(SCRIPT, *args)
			if done.returncode != 0:
				raise AssertionError(f"{SCRIPT} {mode} failed:\n{done.stdout[-4000:]}\n{done.stderr[-4000:]}")
			return json.loads(done.stdout)

		cls.narrow = run("make")
		# The browser's saves came through the web server: a fresh read sees them.
		frappe.db.rollback()
		prototype_files.write_files(cls.doc.name, [{"path": "src/pages/Home.vue", "content": WIDE}])
		frappe.db.commit()
		cls.wide = run("measure")

	def say(self, part=None) -> str:
		return json.dumps({"narrow": self.narrow, "wide": self.wide} if part is None else part, indent=1)[:4000]

	def on(self, pin, box) -> bool:
		return (
			bool(pin)
			and box["x"] - 1 <= pin["x"] <= box["x"] + box["w"] + 1
			and box["y"] - 1 <= pin["y"] <= box["y"] + box["h"] + 1
		)

	def test_the_pages_ran_without_errors(self):
		self.assertEqual(self.narrow["errors"] + self.wide["errors"], [], self.say())

	def test_a_tile_pin_keeps_the_element_it_was_made_on(self):
		note = next(n for n in annotations.read(self.doc.name)["notes"] if n["note"] == "note on submit")
		thread = json.loads(
			frappe.get_value("Sketch Comment", {"prototype": self.doc.name, "text": "comment on submit"}, "anchor")
		)
		for anchor in (note, thread):
			self.assertTrue(anchor.get("target", {}).get("selector"), self.say(anchor))
			self.assertTrue(0 < anchor["offset"]["x"] <= 1, "the fraction of the tile stays as the fallback")

	def test_the_tile_changed_size_and_its_fraction_misses_submit(self):
		"""Without its element, the pin would now sit off Submit: the case this is about."""
		note = next(n for n in annotations.read(self.doc.name)["notes"] if n["note"] == "note on submit")
		tile = self.wide["tile"]
		self.assertGreater(tile["w"] / tile["h"], self.narrow["tile"]["w"] / self.narrow["tile"]["h"])
		fraction = {"x": tile["x"] + note["offset"]["x"] * tile["w"], "y": tile["y"] + note["offset"]["y"] * tile["h"]}
		self.assertFalse(self.on(fraction, self.wide["submit"]), self.say(fraction))

	def test_the_pins_sit_on_the_element_before_and_after(self):
		for run in (self.narrow, self.wide):
			for kind in ("note", "comment"):
				self.assertTrue(self.on(run["pins"][kind], run["submit"]), self.say(run | {"pin": kind}))
			self.assertTrue(self.on(run["pins"]["no"], run["no"]), self.say(run | {"pin": "no"}))

	def test_a_block_inserted_above_moves_the_selector_and_the_pin_still_finds_no(self):
		"""The saved selector now names another element, or none: the pin finds No by its tag and words."""
		anchor = json.loads(
			frappe.get_value("Sketch Comment", {"prototype": self.doc.name, "text": "comment on no"}, "anchor")
		)
		self.assertEqual({k: anchor["target"][k] for k in ("tag", "text", "label")}, {"tag": "button", "text": "No", "label": ""})
		self.assertIn("nth-of-type", anchor["target"]["selector"], "a positional selector, which the insert shifts")
		tile = self.wide["tile"]
		fraction = {"x": tile["x"] + anchor["offset"]["x"] * tile["w"], "y": tile["y"] + anchor["offset"]["y"] * tile["h"]}
		self.assertFalse(self.on(fraction, self.wide["no"]), self.say(fraction))

	def test_a_pin_without_an_element_keeps_its_fraction_of_the_tile(self):
		for run in (self.narrow, self.wide):
			tile, pin = run["tile"], run["pins"]["old"]
			self.assertIsNotNone(pin, self.say(run))
			self.assertAlmostEqual(pin["x"], tile["x"] + OLD[0] * tile["w"], delta=1.5)
			self.assertAlmostEqual(pin["y"], tile["y"] + OLD[1] * tile["h"], delta=1.5)

	def test_an_element_in_a_live_tile_is_found_in_its_live_render(self):
		"""A live tile keeps its snapshot under the live render, unseen. The element is where the live render draws it."""
		live = self.wide["live"]
		self.assertGreater(live["render"]["y"] - live["snapshot"]["y"], 10, self.say(live))
		self.assertIsNotNone(live["tracked"], self.say(live))
		self.assertAlmostEqual(live["tracked"]["x"], live["render"]["x"], delta=1, msg=self.say(live))
		self.assertAlmostEqual(live["tracked"]["y"], live["render"]["y"], delta=1, msg=self.say(live))


class TestTileTargetIsChecked(IntegrationTestCase):
	"""The server keeps a tile's element only when it is whole, and the fraction of the tile always."""

	def anchor(self, target) -> dict:
		return {"route": "/", "tile": TILE, "offset": {"x": 0.4, "y": 0.6}, "target": target}

	def test_a_target_is_kept_with_its_fractions_held_to_the_element(self):
		out = comments.clean_anchor(self.anchor({"selector": "div > button", "x": 1.5, "y": -1, "extra": "x"}))
		self.assertEqual(
			out["target"], {"selector": "div > button", "x": 1.0, "y": 0.0, "tag": "", "text": "", "label": ""}
		)
		self.assertEqual(out["offset"], {"x": 0.4, "y": 0.6})
		self.assertEqual(out["selector"], "", "the page's own selector stays empty on a tile")

	def test_the_traits_are_kept_and_bounded(self):
		target = {"selector": "div > button", "x": 0.5, "y": 0.5, "tag": "button", "text": "N" * 900, "label": 7}
		out = comments.clean_anchor(self.anchor(target))["target"]
		self.assertEqual((out["tag"], len(out["text"]), out["label"]), ("button", 300, ""))

	def test_a_bad_or_cut_short_target_is_dropped(self):
		for bad in (None, "div", {"x": 0.5}, {"selector": ""}, {"selector": 3}, {"selector": "a" * 5000}):
			out = comments.clean_anchor(self.anchor(bad))
			self.assertNotIn("target", out, bad)
			self.assertEqual(out["offset"], {"x": 0.4, "y": 0.6})
