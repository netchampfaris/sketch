# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The theme a person's prototypes open in (decision 84).

The rules this file holds:

- It is light, dark or system, kept on the account, and "system" until the person chooses.
- Only a Prototype's own switch saves it, through the Viewer shell over the session
  (`sketch.viewer_api.save_prototype_theme`, runtime/shell/theme.ts). Sketch's own UI has no control for it, and
  the frame holds no credential for it.
- A signed-in person's shell carries the preference; a Guest's carries none. The frame never does: the shell hands
  it the preference in its URL.
"""

import frappe
from frappe.tests import IntegrationTestCase, set_user

from sketch import api, prototype_theme, viewer_api
from sketch.tests import utils
from sketch.viewer import SketchViewerRenderer

FILES = {
	"src/App.vue": "<template><RouterView /></template>\n",
	"src/router.ts": "export default [{ path: '/', component: () => import('./pages/Home.vue') }]\n",
	"src/pages/Home.vue": "<template><p>Home</p></template>\n",
}


class TestPrototypeTheme(IntegrationTestCase):
	def setUp(self):
		self.owner = utils.make_user("theme-owner", "d2t-theme-owner")
		self.other = utils.make_user("theme-other", "d2t-theme-other")
		self.doc = utils.make_prototype(self.owner, "theme-proto", FILES, is_public=True)

	def tearDown(self):
		for user in (self.owner, self.other):
			frappe.defaults.clear_user_default(prototype_theme.KEY, user)
			utils.drop_user(user)

	def payload_for(self, user):
		renderer = SketchViewerRenderer(path=f"u/{utils.username_of(self.owner)}/{self.doc.slug}")
		with set_user(user):
			self.assertTrue(renderer.can_render())
			return renderer.shell_payload(), renderer.frame_payload()

	def test_it_is_system_until_the_person_chooses(self):
		self.assertEqual(prototype_theme.read(self.owner), "system")
		self.assertEqual(prototype_theme.read(self.other), "system")

	def test_a_prototypes_switch_saves_it_on_the_readers_account(self):
		with set_user(self.other):
			self.assertEqual(
				viewer_api.save_prototype_theme(self.doc.name, "dark")["prototype_theme"], "dark"
			)
		self.assertEqual(prototype_theme.read(self.other), "dark")
		self.assertEqual(prototype_theme.read(self.owner), "system")

	def test_only_the_three_choices_are_saved(self):
		with set_user(self.owner), self.assertRaises(frappe.ValidationError):
			viewer_api.save_prototype_theme(self.doc.name, "sepia")
		self.assertEqual(prototype_theme.read(self.owner), "system")

	def test_a_guest_cannot_save_one(self):
		with set_user("Guest"), self.assertRaises(frappe.PermissionError):
			viewer_api.save_prototype_theme(self.doc.name, "dark")

	def test_sketch_itself_has_no_way_to_set_it(self):
		self.assertFalse(hasattr(api, "set_prototype_theme"))
		self.assertFalse(hasattr(api, "prototype_theme_signed"))
		with set_user(self.owner):
			self.assertNotIn("prototype_theme", api.get_session())

	def test_a_signed_in_shell_carries_the_preference_and_the_frame_does_not(self):
		prototype_theme.write(self.other, "light")
		shell, frame = self.payload_for(self.other)
		self.assertEqual(shell["prototype_theme"], "light")
		self.assertNotIn("prototype_theme", frame)

	def test_a_guest_shell_carries_none(self):
		shell, _ = self.payload_for("Guest")
		self.assertIsNone(shell["prototype_theme"])
