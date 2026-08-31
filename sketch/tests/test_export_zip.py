# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""Export sends one user's whole tree, and only that one.

`sketch.api.export_prototype` answers a file, not a value: it fills the
download slots `frappe.utils.response.as_raw` reads. So the cases here read
`frappe.response`, and one of them opens the archive to prove the bytes are a
zip and not a traceback.

Every entry sits under a folder named for the slug. Without it an unzip
scatters `src/` and `README.md` into whatever directory the user ran it in.

A Prototype is public to look at, never public to take, so the owner check is
the same one the Files browser carries.
"""

import io
import zipfile

import frappe
from frappe.tests import IntegrationTestCase, set_user

from sketch import api, prototype_files
from sketch.tests import utils

#: The fixture tree. A file in the root and two levels under src/, so the
#: folder rule is tested at more than one depth.
FILES = {
	"README.md": "# hello\n",
	"src/App.vue": "<template><RouterView /></template>\n",
	"src/pages/Home.vue": "<template><h1>hi</h1></template>\n",
}


class TestExportZip(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_runtime()
		cls.owner = utils.make_user("zip", "d2tzip")
		cls.addClassCleanup(utils.drop_user, cls.owner)
		cls.other = utils.make_user("zipoth", "d2tzipoth")
		cls.addClassCleanup(utils.drop_user, cls.other)
		# Public on purpose. A visitor may render it and must still not take it.
		cls.doc = utils.make_prototype(cls.owner, "d2t-zip", files=FILES, is_public=True)
		cls.addClassCleanup(utils.drop_prototype, cls.doc.name)
		cls.empty = utils.make_prototype(cls.owner, "d2t-zip-empty")
		cls.addClassCleanup(utils.drop_prototype, cls.empty.name)

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		super().tearDownClass()

	def setUp(self):
		frappe.local.response = frappe._dict({"type": None})

	def export(self, slug: str) -> dict:
		"""Run the method as the owner and hand back the download slots."""
		with set_user(self.owner):
			api.export_prototype(slug)

		return frappe.local.response

	# ------------------------------------------------------------- the file

	def test_the_answer_is_a_download_named_after_the_slug(self):
		response = self.export(self.doc.slug)
		self.assertEqual(response["type"], "download")
		self.assertEqual(response["filename"], "d2t-zip.zip")
		self.assertIsInstance(response["filecontent"], bytes)

	def test_the_archive_holds_every_file_under_one_folder(self):
		content = self.export(self.doc.slug)["filecontent"]
		with zipfile.ZipFile(io.BytesIO(content)) as archive:
			self.assertEqual(
				sorted(archive.namelist()),
				sorted(f"d2t-zip/{path}" for path in FILES),
			)

	def test_every_file_reads_back_word_for_word(self):
		content = self.export(self.doc.slug)["filecontent"]
		with zipfile.ZipFile(io.BytesIO(content)) as archive:
			for path, source in FILES.items():
				with self.subTest(path=path):
					self.assertEqual(
						archive.read(f"d2t-zip/{path}").decode(), source
					)

	def test_the_archive_is_not_corrupt(self):
		"""`testzip` returns the first bad entry, or None when every CRC is good."""
		content = self.export(self.doc.slug)["filecontent"]
		with zipfile.ZipFile(io.BytesIO(content)) as archive:
			self.assertIsNone(archive.testzip())

	def test_an_empty_tree_is_a_valid_empty_archive(self):
		content = self.export(self.empty.slug)["filecontent"]
		with zipfile.ZipFile(io.BytesIO(content)) as archive:
			self.assertEqual(archive.namelist(), [])

	# ------------------------------------------------------------ the owner

	def test_another_user_cannot_export(self):
		with set_user(self.other):
			with self.assertRaises(frappe.DoesNotExistError):
				api.export_prototype(self.doc.slug)

		self.assertIsNone(frappe.local.response.get("filecontent"))

	# ------------------------------------------------------------ the walk

	def test_a_symlink_out_of_the_tree_is_never_packed(self):
		"""The one entry that could carry a file from outside the Prototype."""
		import os

		secret = "/tmp/d2t-zip-secret.txt"
		with open(secret, "w", encoding="utf-8") as handle:
			handle.write("not yours")

		self.addCleanup(os.remove, secret)
		link = prototype_files.safe_join(self.doc.name, "src/link.txt")
		os.symlink(secret, link)
		self.addCleanup(os.remove, link)

		content = self.export(self.doc.slug)["filecontent"]
		with zipfile.ZipFile(io.BytesIO(content)) as archive:
			self.assertNotIn("d2t-zip/src/link.txt", archive.namelist())
