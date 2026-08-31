# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The Files browser reads the caller's own tree, or anybody's public one.

`sketch.api.read_prototype_file` takes a path from the browser, so it carries
the two checks the MCP tools carry: `prototype.resolve_readable` says whose
tree it is, and `prototype_files.safe_join` says the path stays inside it.
Trap 9 applies to a read the same way it applies to a write.

The address decides which tree. A bare slug means the caller's own, which is
the gallery card's read and is unchanged. A slug with a `username` means the
Prototype at `/u/<username>/<slug>`, which is the feed card's read, and
`is_public` is the whole check there: the feed carries this same browser, so a
Prototype a stranger may render is one a stranger may read. A private one is
still refused, and that is the case that matters most here.

`read_text` is the viewer's own reader. `read_files` is the agent's and returns
a file whole; this one stops at a limit and says so, and refuses a file that is
not text.
"""

import frappe
from frappe.tests import IntegrationTestCase, set_user

from sketch import api, prototype_files
from sketch.tests import utils

#: The fixture tree. A file in the root, so the browser has a group with no
#: directory, and two levels under src/.
FILES = {
	"README.md": "# hello\n",
	"src/App.vue": "<template><RouterView /></template>\n",
	"src/pages/Home.vue": "<template><h1>hi</h1></template>\n",
}


class TestFileBrowser(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_runtime()
		cls.owner = utils.make_user("browse", "d2tbrowse")
		cls.addClassCleanup(utils.drop_user, cls.owner)
		cls.other = utils.make_user("browseoth", "d2tbrowseoth")
		cls.addClassCleanup(utils.drop_user, cls.other)
		# Public on purpose. A visitor may render this Prototype and, through
		# the feed card, read it.
		cls.doc = utils.make_prototype(cls.owner, "d2t-browse", files=FILES, is_public=True)
		cls.addClassCleanup(utils.drop_prototype, cls.doc.name)
		cls.shut = utils.make_prototype(cls.owner, "d2t-browse-private", files=FILES)
		cls.addClassCleanup(utils.drop_prototype, cls.shut.name)
		cls.handle = utils.username_of(cls.owner)

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		super().tearDownClass()

	# ------------------------------------------------------------- listing

	def test_the_listing_is_the_whole_tree_sorted_by_path(self):
		with set_user(self.owner):
			rows = api.list_prototype_files(self.doc.slug)

		self.assertEqual([row["path"] for row in rows], sorted(FILES))
		for row in rows:
			self.assertEqual(row["size"], len(FILES[row["path"]].encode()))

	def test_another_user_cannot_list_the_tree_by_slug_alone(self):
		"""A bare slug means "mine". It never reaches somebody else's row, so
		the gallery's read cannot cross a user by accident."""
		with set_user(self.other):
			with self.assertRaises(frappe.DoesNotExistError):
				api.list_prototype_files(self.doc.slug)

	def test_a_stranger_lists_a_public_tree_by_address(self):
		"""The feed card's read. `username` plus slug, and `is_public` is the
		check."""
		with set_user(self.other):
			rows = api.list_prototype_files(self.doc.slug, self.handle)

		self.assertEqual([row["path"] for row in rows], sorted(FILES))

	def test_a_guest_lists_a_public_tree(self):
		"""/feed is read with no session, so the browser on it must answer
		one. `allow_guest` on the method is what makes that work."""
		with set_user("Guest"):
			rows = api.list_prototype_files(self.doc.slug, self.handle)

		self.assertEqual([row["path"] for row in rows], sorted(FILES))

	def test_a_stranger_cannot_list_a_private_tree(self):
		"""The line the address does not cross. `is_public` is the whole
		check, so this is the case that holds it."""
		for user in (self.other, "Guest"):
			with self.subTest(user=user), set_user(user):
				with self.assertRaises(frappe.DoesNotExistError):
					api.list_prototype_files(self.shut.slug, self.handle)

	def test_the_owner_reads_their_own_private_tree_by_address(self):
		"""A signed-in owner looking at their own card is not refused."""
		with set_user(self.owner):
			rows = api.list_prototype_files(self.shut.slug, self.handle)

		self.assertEqual([row["path"] for row in rows], sorted(FILES))

	# ---------------------------------------------------------------- read

	def test_a_file_reads_back_word_for_word(self):
		with set_user(self.owner):
			answer = api.read_prototype_file(self.doc.slug, "src/App.vue")

		self.assertEqual(answer["path"], "src/App.vue")
		self.assertEqual(answer["content"], FILES["src/App.vue"])
		self.assertEqual(answer["size"], len(FILES["src/App.vue"].encode()))
		self.assertFalse(answer["truncated"])

	def test_another_user_cannot_read_a_file_by_slug_alone(self):
		with set_user(self.other):
			with self.assertRaises(frappe.DoesNotExistError):
				api.read_prototype_file(self.doc.slug, "src/App.vue")

	def test_a_stranger_reads_a_file_of_a_public_prototype(self):
		with set_user(self.other):
			answer = api.read_prototype_file(self.doc.slug, "src/App.vue", self.handle)

		self.assertEqual(answer["content"], FILES["src/App.vue"])

	def test_a_stranger_cannot_read_a_file_of_a_private_prototype(self):
		for user in (self.other, "Guest"):
			with self.subTest(user=user), set_user(user):
				with self.assertRaises(frappe.DoesNotExistError):
					api.read_prototype_file(self.shut.slug, "src/App.vue", self.handle)

	def test_the_path_guard_still_runs_on_a_public_read(self):
		"""Trap 9 does not relax because the Prototype is public. The reader
		names the path, so `safe_join` runs whoever is asking."""
		with set_user(self.other):
			with self.assertRaises(frappe.ValidationError):
				api.read_prototype_file(self.doc.slug, "../../../../etc/passwd", self.handle)

	def test_a_missing_file_raises(self):
		with set_user(self.owner):
			with self.assertRaises(frappe.ValidationError):
				api.read_prototype_file(self.doc.slug, "src/Gone.vue")

	def test_a_path_out_of_the_tree_is_refused(self):
		"""The same guard the agent's tools get. The browser names the path too."""
		for path in ("../../../../etc/passwd", "src/../../escaped.txt", "/etc/passwd", ""):
			with self.subTest(path=path):
				with set_user(self.owner):
					with self.assertRaises(frappe.ValidationError):
						api.read_prototype_file(self.doc.slug, path)

	# ----------------------------------------------------------- read_text

	def test_a_long_file_is_cut_and_says_so(self):
		"""The size is the file's own size, not the length of what came back."""
		body = "x" * 5000
		prototype_files.write_files(self.doc.name, [{"path": "src/long.txt", "content": body}])
		self.addCleanup(prototype_files.delete_file, self.doc.name, "src/long.txt")

		answer = prototype_files.read_text(self.doc.name, "src/long.txt", limit=1000)
		self.assertTrue(answer["truncated"])
		self.assertEqual(answer["content"], "x" * 1000)
		self.assertEqual(answer["size"], 5000)

	def test_a_cut_inside_a_character_still_reads(self):
		"""A limit lands mid-character. The partial character goes, nothing else."""
		prototype_files.write_files(self.doc.name, [{"path": "src/wide.txt", "content": "é" * 10}])
		self.addCleanup(prototype_files.delete_file, self.doc.name, "src/wide.txt")

		answer = prototype_files.read_text(self.doc.name, "src/wide.txt", limit=5)
		self.assertTrue(answer["truncated"])
		self.assertEqual(answer["content"], "é" * 2)

	def test_a_binary_file_is_refused(self):
		"""It is not source. A screen of control characters is not a viewer."""
		path = prototype_files.safe_join(self.doc.name, "src/blob.bin")
		with open(path, "wb") as handle:
			handle.write(b"\x89PNG\x00\x1a\n")

		self.addCleanup(prototype_files.delete_file, self.doc.name, "src/blob.bin")

		with self.assertRaises(frappe.ValidationError):
			prototype_files.read_text(self.doc.name, "src/blob.bin")
