# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The studio must never list a Prototype the Viewer refuses.

The regression: `list_prototypes` leaned on the `if_owner` permission rule
instead of filtering by owner. `if_owner` is set per role. `Sketch User`
carries it, `System Manager` does not, so a System Manager saw every Prototype
on the site. The Viewer serves the owner or a public Prototype and nobody
else, so each of those cards answered 404. Every prototype read "Page not
found".

Both listings are covered, the SPA one and the MCP tool one, because a token
can belong to a System Manager too.
"""

from urllib.parse import urlparse

import frappe
from frappe.tests import IntegrationTestCase

from sketch import api
from sketch.mcp import tools
from sketch.tests import utils
from sketch.viewer import SketchViewerRenderer


class TestListingMatchesViewer(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_runtime()
		files = {"src/App.vue": "<template><div>hi</div></template>"}
		cls.owner = utils.make_user("listown", "d2tlistown")
		cls.other = utils.make_user("listoth", "d2tlistoth")
		cls.mine = utils.make_prototype(cls.owner, "d2t-list-mine", files=files)
		cls.theirs = utils.make_prototype(cls.other, "d2t-list-theirs", files=files)

	@classmethod
	def tearDownClass(cls):
		for doc in (cls.mine, cls.theirs):
			utils.drop_prototype(doc.name)
		for email in (cls.owner, cls.other):
			utils.drop_user(email)
		frappe.set_user("Administrator")
		super().tearDownClass()

	def tearDown(self):
		frappe.set_user("Administrator")

	def refused(self, rows: list[dict]) -> list[str]:
		"""The listed links the Viewer would answer 404 for.

		The link each row carries is the one the card navigates to, so this
		tests what a person actually clicks. A row that names the wrong
		username fails here even when the Prototype itself is readable.
		"""
		out = []
		for row in rows:
			link = row.get("viewer_path") or urlparse(row["url"]).path
			if not SketchViewerRenderer(path=link.lstrip("/")).can_render():
				out.append(link)
		return out

	def test_the_spa_lists_only_what_the_viewer_serves(self):
		for who in (self.owner, self.other, "Administrator"):
			with self.subTest(user=who):
				frappe.set_user(who)
				self.assertEqual(self.refused(api.list_prototypes()), [])

	def test_the_mcp_tool_lists_only_what_the_viewer_serves(self):
		for who in (self.owner, self.other, "Administrator"):
			with self.subTest(user=who):
				frappe.set_user(who)
				rows = tools.do_list_prototypes({}).structured["prototypes"]
				self.assertEqual(self.refused(rows), [])

	def test_an_owner_sees_their_own_prototype(self):
		frappe.set_user(self.owner)
		slugs = [row["slug"] for row in api.list_prototypes()]
		self.assertIn("d2t-list-mine", slugs)

	def test_an_owner_never_sees_another_users_prototype(self):
		frappe.set_user(self.owner)
		slugs = [row["slug"] for row in api.list_prototypes()]
		self.assertNotIn("d2t-list-theirs", slugs)

	def test_a_system_manager_never_sees_another_users_prototype(self):
		"""The regression itself. System Manager has no `if_owner` rule."""
		frappe.set_user("Administrator")
		self.assertTrue(frappe.has_permission("Sketch Prototype", "read"))
		slugs = [row["slug"] for row in api.list_prototypes()]
		self.assertNotIn("d2t-list-mine", slugs)
		self.assertNotIn("d2t-list-theirs", slugs)
