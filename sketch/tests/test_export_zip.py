# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""Export sends the caller's own tree, or anybody's public one.

`sketch.api.export_prototype` answers a file, not a value: it fills the
download slots `frappe.utils.response.as_raw` reads. So the cases here read
`frappe.response`, and one of them opens the archive to prove the bytes are a
zip and not a traceback.

Every entry sits under a folder named for the slug. Without it an unzip
scatters `src/` and `README.md` into whatever directory the user ran it in.

A public Prototype is public to take as well as to look at: the feed card
offers this beside its Files browser, so what a stranger can read one file at a
time they can also take in one file. The check is therefore the browser's own,
`prototype.resolve_readable`. A bare slug means the caller's own Prototype; a
slug with a `username` means the one at `/u/<username>/<slug>`, and `is_public`
is the whole check there.
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
		# Public on purpose. A visitor may render it and, from the feed card,
		# take it.
		cls.doc = utils.make_prototype(cls.owner, "d2t-zip", files=FILES, is_public=True)
		cls.addClassCleanup(utils.drop_prototype, cls.doc.name)
		cls.empty = utils.make_prototype(cls.owner, "d2t-zip-empty")
		cls.addClassCleanup(utils.drop_prototype, cls.empty.name)
		cls.shut = utils.make_prototype(cls.owner, "d2t-zip-private", files=FILES)
		cls.addClassCleanup(utils.drop_prototype, cls.shut.name)
		cls.handle = utils.username_of(cls.owner)

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		super().tearDownClass()

	def setUp(self):
		frappe.local.response = frappe._dict({"type": None})

	def export(self, slug: str, username: str = "", as_user: str = "") -> dict:
		"""Run the method and hand back the download slots.

		Defaults to the owner asking for their own tree, which is the gallery
		card's export.
		"""
		with set_user(as_user or self.owner):
			api.export_prototype(slug, username)

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

	# ---------------------------------------------------------- who may take

	def test_another_user_cannot_export_by_slug_alone(self):
		"""A bare slug means "mine", so it never reaches somebody else's row."""
		with set_user(self.other):
			with self.assertRaises(frappe.DoesNotExistError):
				api.export_prototype(self.doc.slug)

		self.assertIsNone(frappe.local.response.get("filecontent"))

	def test_a_stranger_takes_a_public_prototype(self):
		"""The feed card's export."""
		response = self.export(self.doc.slug, self.handle, as_user=self.other)

		self.assertEqual(response["filename"], "d2t-zip.zip")
		with zipfile.ZipFile(io.BytesIO(response["filecontent"])) as archive:
			self.assertEqual(
				sorted(archive.namelist()), sorted(f"d2t-zip/{path}" for path in FILES)
			)

	def test_a_guest_takes_a_public_prototype(self):
		"""/feed is read with no session, so `allow_guest` has to hold here as
		well as on the listing."""
		response = self.export(self.doc.slug, self.handle, as_user="Guest")

		self.assertEqual(response["type"], "download")

	def test_nobody_takes_a_private_prototype(self):
		"""The line the address does not cross."""
		for user in (self.other, "Guest"):
			with self.subTest(user=user), set_user(user):
				with self.assertRaises(frappe.DoesNotExistError):
					api.export_prototype(self.shut.slug, self.handle)

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
