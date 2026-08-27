# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The path guard: every agent-supplied path stays inside the Prototype.

Trap 9. `write_files`, `edit_file` and `delete_file` take a path an agent wrote,
so each one must refuse `..`, an absolute path, and a symlink that points out of
the tree. A miss here writes any file the site user can write.

The tests assert two things for every bad path: the call raises, and the file it
aimed at is still not there.
"""

import os

import frappe
from frappe.tests import IntegrationTestCase

from sketch import prototype_files
from sketch.tests import utils

#: One entry per class of escape. `rel` is what an agent could send.
BAD_PATHS = (
	"../escaped.txt",
	"../../escaped.txt",
	"src/../../escaped.txt",
	"src/./../../escaped.txt",
	"..",
	"../",
	"/etc/passwd",
	"/tmp/escaped.txt",
	"//tmp/escaped.txt",
	"..\\escaped.txt",
	"src\\..\\..\\escaped.txt",
	"",
	"   ",
)

#: The symlink name planted inside the tree. It points at /tmp.
LINK = "outside"


class TestPathGuard(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_runtime()
		cls.user = utils.make_user("guard", "d2tguard")
		cls.addClassCleanup(utils.drop_user, cls.user)
		cls.doc = utils.make_prototype(
			cls.user, "d2t-guard", files={"src/App.vue": "<template><div/></template>\n"}
		)
		cls.addClassCleanup(utils.drop_prototype, cls.doc.name)
		cls.base = prototype_files.prototype_dir(cls.doc.name)

	def setUp(self):
		self.witness = os.path.join(os.path.dirname(self.base), "escaped.txt")
		self.addCleanup(self.remove, self.witness)
		self.addCleanup(self.remove, "/tmp/escaped.txt")

	def remove(self, path):
		if os.path.isfile(path) or os.path.islink(path):
			os.remove(path)

	def assert_nothing_escaped(self):
		self.assertFalse(os.path.exists(self.witness), f"a write escaped to {self.witness}")
		self.assertFalse(os.path.exists("/tmp/escaped.txt"), "a write escaped to /tmp/escaped.txt")

	# ------------------------------------------------------------- safe_join

	def test_safe_join_rejects_every_bad_path(self):
		for rel in BAD_PATHS:
			with self.subTest(path=rel):
				with self.assertRaises(frappe.ValidationError):
					prototype_files.safe_join(self.doc.name, rel)

	def test_safe_join_accepts_a_normal_path(self):
		"""The positive control. A guard that refuses everything is not a guard."""
		target = prototype_files.safe_join(self.doc.name, "src/pages/Home.vue")
		self.assertEqual(target, os.path.join(self.base, "src/pages/Home.vue"))

	def test_safe_join_rejects_a_null_byte(self):
		with self.assertRaises(frappe.ValidationError):
			prototype_files.safe_join(self.doc.name, "src/App\x00.vue")

	# ----------------------------------------------------------- write_files

	def test_write_files_rejects_every_bad_path(self):
		for rel in BAD_PATHS:
			with self.subTest(path=rel):
				with self.assertRaises(frappe.ValidationError):
					prototype_files.write_files(self.doc.name, [{"path": rel, "content": "escaped"}])
				self.assert_nothing_escaped()

	# ------------------------------------------------------------- edit_file

	def test_edit_file_rejects_every_bad_path(self):
		for rel in BAD_PATHS:
			with self.subTest(path=rel):
				with self.assertRaises(frappe.ValidationError):
					prototype_files.edit_file(self.doc.name, rel, "a", "b")

	# ----------------------------------------------------------- delete_file

	def test_delete_file_rejects_every_bad_path(self):
		"""A file outside the tree must survive the call."""
		with open(self.witness, "w", encoding="utf-8") as handle:
			handle.write("do not delete me")

		for rel in BAD_PATHS:
			with self.subTest(path=rel):
				with self.assertRaises(frappe.ValidationError):
					prototype_files.delete_file(self.doc.name, rel)

		self.assertTrue(os.path.isfile(self.witness), "delete_file escaped the prototype")

	# --------------------------------------------------------------- symlink

	def test_a_symlink_out_of_the_tree_is_refused(self):
		"""A `..` check alone misses this. Only the realpath step catches it."""
		link = os.path.join(self.base, LINK)
		self.remove(link)
		os.symlink("/tmp", link)
		self.addCleanup(self.remove, link)

		for rel in (f"{LINK}/escaped.txt", f"{LINK}/"):
			with self.subTest(path=rel):
				with self.assertRaises(frappe.ValidationError):
					prototype_files.write_files(self.doc.name, [{"path": rel, "content": "escaped"}])
				self.assert_nothing_escaped()

		with self.assertRaises(frappe.ValidationError):
			prototype_files.edit_file(self.doc.name, f"{LINK}/escaped.txt", "a", "b")

		with self.assertRaises(frappe.ValidationError):
			prototype_files.delete_file(self.doc.name, f"{LINK}/escaped.txt")

	def test_a_symlinked_file_is_not_read_or_listed(self):
		"""A link to a file outside the tree must not leak through read_tree."""
		secret = "/tmp/d2t-secret.txt"
		with open(secret, "w", encoding="utf-8") as handle:
			handle.write("secret")
		self.addCleanup(self.remove, secret)

		link = os.path.join(self.base, "src", "leak.txt")
		self.remove(link)
		os.symlink(secret, link)
		self.addCleanup(self.remove, link)

		self.assertNotIn("src/leak.txt", prototype_files.read_tree(self.doc.name))
		self.assertNotIn("src/leak.txt", [row["path"] for row in prototype_files.list_files(self.doc.name)])

	# ------------------------------------------------------- the hash id itself

	def test_prototype_dir_refuses_a_traversing_id(self):
		"""`name` comes from the database, but the guard must not trust it."""
		for name in ("..", "../other", "a/b", "", None):
			with self.subTest(name=name):
				with self.assertRaises(frappe.ValidationError):
					prototype_files.prototype_dir(name)
