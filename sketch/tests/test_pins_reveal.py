# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""A pin on something inside a popover, a closed section or another tab finds its way back, in a real browser.

A note or comment made on the live page keeps `reveal`: the controls that were open around its element, outermost
first. Once they close, its pin sits faded on the deepest of them still on the page, and moves with it; clicking the
pin, or the comment's row in the list, presses each closed one in turn and opens the box on the element itself. An
old pin, made before the way was kept, sits on its element's nearest ancestor still drawn, or hides when that is more
than half the page. Before this a pin stayed at its last spot on the screen, over whatever was there now.

`pins_reveal.mjs` makes the notes and comments, closes everything and reports where each pin is and what a click
on it does.

Skips when node, Playwright, the web server or the built shell is absent. A skip is not a pass.
"""

import json
import os
import unittest

import frappe
from frappe.sessions import delete_session
from frappe.tests import IntegrationTestCase

from sketch import annotations
from sketch.tests import utils
from sketch.tests.reveal_tree import TREE
from sketch.tests.test_viewer_api import open_session
from sketch.viewer import SHELL_HTML

SCRIPT = "pins_reveal.mjs"
SPOTS = ("cert", "docs", "tab")
KINDS = ("note", "comment")


def old_note(id: str, selector: str, words: str) -> dict:
	"""A note as one was saved before `reveal`: where it was on the screen, and no way back."""
	return {
		"id": id,
		"route": "/",
		"viewport": "1280x800",
		"selector": selector,
		"component": "Home",
		"element": "p",
		"text": words,
		"offset": {"x": 0.5, "y": 0.5},
		"rect": {"x": 300, "y": 600, "w": 200, "h": 20},
		"note": words,
		"createdAt": 1794857063006,
	}


class TestPinsFindTheirWayBack(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()

		reason = utils.node_reason() or utils.webserver_reason()
		if not reason and not os.path.isfile(frappe.get_app_path("sketch", *SHELL_HTML)):
			reason = "the frontend is not built, so there is no shell page"
		if reason:
			raise unittest.SkipTest(reason)

		cls.owner = utils.make_user("pinrev", "d2tpinrev")
		cls.addClassCleanup(utils.drop_user, cls.owner)
		cls.doc = utils.make_prototype(cls.owner, "d2t-pins-reveal", files=TREE, is_public=True)
		cls.addClassCleanup(utils.drop_prototype, cls.doc.name)
		notes = [
			# Inside the Documents card's body, which closes: its card is the nearest thing still drawn.
			old_note("oldnear", "#documents-body > p", "old near"),
			# Gone, and every ancestor left is most of the page.
			old_note("oldgone", "#app > div > div:nth-of-type(9) > p", "old gone"),
		]
		annotations.save(cls.doc.name, json.dumps({"notes": notes}), annotations.epoch(cls.doc.name))
		frappe.db.commit()

		sid, _ = open_session(cls.owner)
		cls.addClassCleanup(delete_session, sid)
		viewer = f"/u/{utils.username_of(cls.owner)}/{cls.doc.slug}"
		entry = f"{utils.playwright_root()}/playwright/index.mjs"
		args = [entry, utils.site_host(), str(utils.webserver_port()), viewer, sid]
		if os.environ.get("SKETCH_EVIDENCE"):
			args.append(os.environ["SKETCH_EVIDENCE"])
		run = utils.run_node(SCRIPT, *args)
		if run.returncode != 0:
			raise AssertionError(f"{SCRIPT} failed:\n{run.stdout[-4000:]}\n{run.stderr[-4000:]}")
		cls.answer = json.loads(run.stdout)
		# The browser's saves came through the web server: a fresh read sees them.
		frappe.db.rollback()

	def say(self, part=None) -> str:
		return json.dumps(self.answer if part is None else part, indent=1)[:4000]

	def test_each_pin_keeps_the_way_to_its_element(self):
		"""Saved with the controls that were open, outermost first: two for the checkbox, one for each of the rest."""
		notes = {n["note"]: n for n in annotations.read(self.doc.name)["notes"]}
		threads = {
			c.text: json.loads(c.anchor)
			for c in frappe.get_all(
				"Sketch Comment", filters={"prototype": self.doc.name}, fields=["text", "anchor"]
			)
		}
		for kind, rows in (("note", notes), ("comment", threads)):
			ways = {
				spot: next((a.get("reveal") for w, a in rows.items() if f"{kind} {spot}" in w), None)
				for spot in SPOTS
			}
			self.assertEqual(
				[s["kind"] for s in ways["cert"] or []], ["expanded", "expanded"], self.say(ways)
			)
			self.assertEqual([s["kind"] for s in ways["docs"] or []], ["expanded"], self.say(ways))
			self.assertEqual([s["kind"] for s in ways["tab"] or []], ["tab"], self.say(ways))
		self.assertNotIn("reveal", notes["old near"])

	def test_a_closed_pin_sits_faded_on_what_opens_it(self):
		for kind in KINDS:
			for spot in SPOTS:
				pin = self.answer["closed"][f"{kind}:{spot}"]
				self.assertTrue(
					pin["shown"] and pin["faded"] and pin["onStandIn"],
					self.say(pin | {"pin": f"{kind}:{spot}"}),
				)

	def test_a_closed_pin_moves_with_the_page(self):
		for key, pin in self.answer["scrolled"].items():
			self.assertTrue(
				pin["by"] > 0 and abs(pin["moved"] - pin["by"]) <= 1 and pin["onStandIn"],
				self.say(pin | {"pin": key}),
			)

	def test_a_click_on_the_pin_opens_the_way_and_the_box_on_the_element(self):
		for key, opened in self.answer["opened"].items():
			self.assertEqual(
				opened,
				{"visible": True, "boxOpen": True, "pinOnTarget": True, "faded": False, "boxNear": True},
				self.say(opened | {"pin": key}),
			)

	def test_a_row_in_the_comments_list_does_the_same(self):
		for key, opened in self.answer["listed"].items():
			self.assertEqual(
				opened,
				{"visible": True, "boxOpen": True, "pinOnTarget": True, "faded": False, "boxNear": True},
				self.say(opened | {"row": key}),
			)

	def test_an_old_pin_sits_on_its_nearest_ancestor_or_hides(self):
		self.assertEqual(
			self.answer["old"]["old near"], {"shown": True, "faded": True, "onSection": True}, self.say()
		)
		self.assertEqual(self.answer["old"]["old gone"], {"shown": False}, self.say())

	def test_the_page_threw_nothing(self):
		self.assertEqual(self.answer["errors"], [], self.say())
