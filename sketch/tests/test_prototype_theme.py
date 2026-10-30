# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The theme a person's prototypes open in (decision 84).

The rules this file holds:

- It is light, dark or system, kept on the account, and "system" until the person chooses.
- Only a Prototype's own switch saves it, with the page's `theme` credential, which names one person and
  opens nothing else. Sketch's own UI has no control for it.
- A signed-in person's page carries the preference and the credential. A Guest's and a `check` page carry neither.
"""

import frappe
from frappe.tests import IntegrationTestCase, set_user

from sketch import api, prototype_theme, signature
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

	def credential(self, user):
		username = utils.username_of(user)
		stamp = signature.mint(prototype_theme.subject(username), 600, signature.THEME)
		return {"username": username, "exp": str(stamp["exp"]), "sig": stamp["sig"]}

	def payload_for(self, user):
		renderer = SketchViewerRenderer(path=f"u/{utils.username_of(self.owner)}/{self.doc.slug}")
		with set_user(user):
			self.assertTrue(renderer.can_render())
			return renderer.payload()

	def test_it_is_system_until_the_person_chooses(self):
		self.assertEqual(prototype_theme.read(self.owner), "system")

	def test_only_the_three_choices_are_saved(self):
		with set_user("Guest"), self.assertRaises(frappe.ValidationError):
			api.prototype_theme_signed(**self.credential(self.owner), theme="sepia")
		self.assertEqual(prototype_theme.read(self.owner), "system")

	def test_sketch_itself_has_no_way_to_set_it(self):
		self.assertFalse(hasattr(api, "set_prototype_theme"))
		with set_user(self.owner):
			self.assertNotIn("prototype_theme", api.get_session())

	def test_a_prototypes_switch_saves_it_with_the_pages_credential(self):
		with set_user("Guest"):
			self.assertEqual(api.prototype_theme_signed(**self.credential(self.owner), theme="dark")["prototype_theme"], "dark")
		self.assertEqual(prototype_theme.read(self.owner), "dark")

	def test_the_credential_speaks_for_one_person_and_one_write(self):
		stolen = self.credential(self.owner)
		seen = signature.mint(f"{self.doc.name}|{stolen['username']}", 600, signature.SEEN)
		with set_user("Guest"):
			for bad in (
				{**stolen, "username": utils.username_of(self.other)},
				{**stolen, "sig": "0" * 64},
				{**stolen, "exp": str(seen["exp"]), "sig": seen["sig"]},
				{"username": stolen["username"], "exp": "", "sig": ""},
			):
				with self.assertRaises(frappe.DoesNotExistError):
					api.prototype_theme_signed(**bad, theme="dark")
		self.assertEqual(prototype_theme.read(self.owner), "system")
		self.assertEqual(prototype_theme.read(self.other), "system")

	def test_a_signed_in_page_carries_the_preference_and_a_credential_that_saves_it(self):
		prototype_theme.write(self.other, "light")
		data = self.payload_for(self.other)
		self.assertEqual(data["theme_pref"], "light")
		self.assertEqual(data["theme_user"], utils.username_of(self.other))
		stamp = {"username": data["theme_user"], "exp": str(data["theme_exp"]), "sig": data["theme_sig"]}
		with set_user("Guest"):
			api.prototype_theme_signed(**stamp, theme="dark")
		self.assertEqual(prototype_theme.read(self.other), "dark")

	def test_a_guest_page_carries_neither(self):
		data = self.payload_for("Guest")
		self.assertIsNone(data["theme_pref"])
		self.assertEqual((data["theme_user"], data["theme_exp"], data["theme_sig"]), ("", "", ""))
