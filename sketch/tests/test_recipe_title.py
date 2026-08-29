# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""A new Prototype opens on the name the user typed.

The blank recipe hardcoded "Untitled" in its heading, so a Prototype named
"First look" opened on somebody else's word (review 6.2). `create_prototype`
now writes the tree through `_apply_title` (`sketch/api.py:105-113`), which
replaces `TITLE_TOKEN` in every file of the recipe.

The title lands in a Vue single-file component that is compiled in the browser,
so `_title_for_source` (`sketch/api.py:93-102`) drops the characters that end a
tag, an interpolation or an attribute early. Only the copy written into source
is stripped. `Sketch Prototype.title` keeps every character, because it is the
name on the card and it is never compiled.

None of this needs a web server. `create_prototype` needs a built Runtime,
because `prototype.create` pins one.
"""

import re

import frappe
from frappe.tests import IntegrationTestCase, set_user

from sketch import api, prototype_files
from sketch.tests import utils

#: The one file of the blank recipe that carries the token.
BLANK_HOME = "src/pages/Home.vue"

#: The page heading, read the way a person reads the rendered page. The class
#: list is deliberately out of the pattern: this asserts the name, not the type
#: style, which conventions.md owns.
HEADING = re.compile(r"<h1[^>]*>(.*?)</h1>", re.DOTALL)

#: A typed title and the copy that may be pasted into a component, one pair per
#: rule in `_title_for_source`. `/` and `(` are absent from `_TITLE_UNSAFE` on
#: purpose: neither can break a template, and stripping them would mangle a
#: name for nothing.
SAFE_SOURCE = (
	("First look", "First look"),
	("Faris's app", "Fariss app"),
	('He said "hi"', "He said hi"),
	("<script>alert(1)</script>", "scriptalert(1)/script"),
	("{{ 1 + 1 }}", "1 + 1"),
	("back\\slash", "backslash"),
	("`tick`", "tick"),
	("two\nlines", "two lines"),
	("  padded  ", "padded"),
	("one   wide   gap", "one wide gap"),
)

#: Titles that leave nothing behind. These are the only way to reach the
#: fallback, and the fallback is the word the fix removed from the recipe.
NOTHING_SURVIVES = ("", "   ", "<>{}", "\"'`\\", "\n\n")


class TestRecipeTitle(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.user = utils.make_user("title", "d2ttitle")
		cls.addClassCleanup(utils.drop_user, cls.user)

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		super().tearDownClass()

	# ------------------------------------------------------ the sanitiser

	def test_a_title_reaches_source_with_nothing_that_breaks_a_compile(self):
		for typed, expected in SAFE_SOURCE:
			with self.subTest(typed=typed):
				self.assertEqual(api._title_for_source(typed), expected)

	def test_a_title_that_leaves_nothing_falls_back_to_untitled(self):
		"""The one path that may still print "Untitled"."""
		for typed in NOTHING_SURVIVES:
			with self.subTest(typed=typed):
				self.assertEqual(api._title_for_source(typed), "Untitled")

	def test_a_missing_title_falls_back_instead_of_raising(self):
		"""`None` reaches here from a caller that never validated. It must not
		raise: a create that throws here leaves the Prototype row behind with
		no tree."""
		self.assertEqual(api._title_for_source(None), "Untitled")

	# --------------------------------------------------- the substitution

	def test_every_file_of_the_tree_takes_the_title(self):
		"""The replace runs over the whole tree, not over one named file, so a
		recipe may put the token in a heading, a sidebar and a document
		title."""
		tree = [
			{"path": "src/App.vue", "content": f"<h1>{api.TITLE_TOKEN}</h1>"},
			{"path": "src/pages/Home.vue", "content": f"{api.TITLE_TOKEN} then {api.TITLE_TOKEN}"},
			{"path": "src/router.ts", "content": "no token here"},
		]

		out = api._apply_title(tree, "First look")

		self.assertEqual(out[0]["content"], "<h1>First look</h1>")
		self.assertEqual(out[1]["content"], "First look then First look")
		self.assertEqual(out[2]["content"], "no token here")

	def test_a_recipe_with_no_token_comes_back_unchanged(self):
		"""Eight of the nine recipes carry no token. None of them may move."""
		tree = [{"path": "src/App.vue", "content": "<template><div>hi</div></template>"}]

		self.assertEqual(api._apply_title(tree, "First look"), tree)

	def test_the_tree_on_disk_is_never_mutated(self):
		"""`_apply_title` builds new dicts. If it wrote through, the second
		create in one process would substitute into an already-substituted
		tree and every later Prototype would carry the first one's name."""
		tree = [{"path": "src/App.vue", "content": api.TITLE_TOKEN}]

		api._apply_title(tree, "First look")

		self.assertEqual(tree[0]["content"], api.TITLE_TOKEN)

	def test_the_blank_recipe_still_holds_the_token(self):
		"""Without this the end-to-end cases below pass on a tree that has
		nothing to replace."""
		tree = {row["path"]: row["content"] for row in api._recipe_tree("blank")}

		self.assertIn(BLANK_HOME, tree)
		self.assertIn(api.TITLE_TOKEN, tree[BLANK_HOME])

	# ------------------------------------------------------ end to end

	def create(self, title: str) -> dict:
		"""One Prototype through the whitelisted method, dropped at the end.

		The session is switched, because `prototype.create` reads
		`frappe.session.user` for the owner and for the slug collision check.
		"""
		with set_user(self.user):
			row = api.create_prototype(title)

		self.addCleanup(utils.drop_prototype, row["name"])
		frappe.db.commit()
		return row

	def heading_of(self, name: str) -> str:
		"""The text of the `h1` on the first page of a written tree."""
		source = prototype_files.read_files(name, [BLANK_HOME])[0]["content"]
		match = HEADING.search(source)
		if not match:
			raise AssertionError(f"{BLANK_HOME} has no h1")

		return match.group(1).strip()

	def test_a_new_prototype_opens_on_the_name_the_user_typed(self):
		"""The regression. The heading read "Untitled" whatever was typed."""
		utils.require_runtime()
		row = self.create("D2t First Look")

		self.assertEqual(self.heading_of(row["name"]), "D2t First Look")

	def test_no_written_file_keeps_the_token(self):
		"""A token left in the tree is a placeholder on screen, which is the
		same failure with a different word in it."""
		utils.require_runtime()
		row = self.create("D2t Token Sweep")

		for entry in prototype_files.read_tree(row["name"]).values():
			self.assertNotIn(api.TITLE_TOKEN, entry)

	def test_the_prototypes_own_name_keeps_every_character(self):
		"""The strip is on the source copy only. The card, the rename field
		and the History dialog all print the field, and a user who typed a
		quotation mark must see it there."""
		utils.require_runtime()
		typed = 'D2t "Quoted" Name'
		row = self.create(typed)

		self.assertEqual(row["title"], typed)
		self.assertEqual(frappe.db.get_value("Sketch Prototype", row["name"], "title"), typed)
		self.assertEqual(self.heading_of(row["name"]), "D2t Quoted Name")
