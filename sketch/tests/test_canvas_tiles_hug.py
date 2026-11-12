# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""Canvas tiles fit their variant, and a variant that draws its own card drops the tile frame.

Two rules, run in a real browser page with the shipped source (`canvas_tiles_hug.mjs` bundles `runtime/variants/lift.ts`
and `layout.ts`; no server is needed):

- A set is self-framed when its drawn content is one outermost element with a background of its own and an edge to it
  (a visible border or a shadow). Several root elements, no background, or a background with no edge keep the frame.
- In a set's grid, each tile is its own size (the set's box plus the margin), not the widest option's. A row's tiles sit
  left to right with a gap between, share the row's top edge, and the grid is as wide as its widest row. The tile carries
  the self-framed flag so the canvas can draw it without the frame.

Skips when node, Playwright or esbuild (from a built Runtime's node_modules) is absent. A skip is not a pass.
"""

import json
import os
import unittest

import frappe
from frappe.tests import IntegrationTestCase

from sketch.tests import utils

SCRIPT = "canvas_tiles_hug.mjs"
GAP = 48
MARGIN = 16


def bundle_inputs() -> tuple[str, str, str] | None:
	"""(esbuild, node_modules, runtime/variants) from the first Runtime version that has installed its tools."""
	runtime = os.path.abspath(os.path.join(frappe.get_app_path("sketch"), "..", "runtime"))
	versions = os.path.join(runtime, "versions")
	for version in sorted(os.listdir(versions)) if os.path.isdir(versions) else []:
		modules = os.path.join(versions, version, "node_modules")
		esbuild = os.path.join(modules, ".bin", "esbuild")
		if os.path.exists(esbuild):
			return esbuild, modules, os.path.join(runtime, "variants")

	return None


class TestCanvasTilesHug(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		reason = utils.node_reason()
		inputs = bundle_inputs()
		if reason is None and inputs is None:
			reason = "esbuild is not installed under runtime/versions/*/node_modules; run runtime/build-all.sh"

		if reason:
			raise unittest.SkipTest(reason)

		entry = os.path.join(utils.playwright_root(), "playwright", "index.mjs")
		run = utils.run_node(SCRIPT, entry, *inputs)
		if run.returncode:
			raise AssertionError(f"{SCRIPT} failed: {run.stderr[-1500:]}")

		cls.answer = json.loads(run.stdout.strip().splitlines()[-1])

	def test_the_page_ran_without_errors(self):
		self.assertEqual(self.answer["errors"], [])

	def test_one_root_with_a_surface_and_an_edge_is_self_framed(self):
		own = self.answer["own"]
		self.assertEqual(own["card"], "12px", "the radius comes back, so the ring can follow it")
		self.assertIsNotNone(own["shadow"], "a shadow is an edge as much as a border is")

	def test_the_rest_keep_the_frame(self):
		own = self.answer["own"]
		for case in ("borderOnly", "fillOnly", "shadowOnly", "clearBorder", "twoRoots", "none"):
			self.assertIsNone(own[case], case)

	def test_each_tile_is_its_own_size_in_a_row(self):
		tiles = {t["id"]: t for t in self.answer["wide"]["tiles"]}
		sizes = {"a": (420, 400), "b": (420, 320), "c": (420, 480), "d": (840, 360)}
		x = 0
		for key, (w, h) in sizes.items():
			tile = tiles[key]
			self.assertEqual((tile["x"], tile["w"], tile["h"]), (x, w + MARGIN * 2, h + MARGIN * 2), key)
			self.assertEqual(tile["y"], tiles["a"]["y"], "a row shares its top edge")
			x += tile["w"] + GAP

	def test_the_grid_is_as_wide_as_its_widest_row(self):
		tiles = {t["id"]: t for t in self.answer["wide"]["tiles"]}
		self.assertEqual(self.answer["wide"]["bounds"]["w"], tiles["d"]["x"] + tiles["d"]["w"])
		self.assertEqual(tiles["e"]["x"], 0, "the next row starts at the left again")
		self.assertGreater(tiles["e"]["y"], tiles["a"]["y"])

	def test_a_phone_stacks_tiles_at_their_own_widths(self):
		phone = self.answer["phone"]
		self.assertEqual([t["x"] for t in phone["tiles"]], [0] * 5)
		self.assertEqual(sorted({t["w"] for t in phone["tiles"]}), [320 + 32, 420 + 32, 840 + 32])
		self.assertEqual(phone["bounds"]["w"], 840 + 32)

	def test_a_tile_carries_the_self_framed_flag_of_its_option(self):
		flags = {t["id"]: t["card"] for t in self.answer["wide"]["tiles"]}
		self.assertEqual(flags, {"a": "10px", "b": None, "c": "10px", "d": "10px", "e": "10px"})
