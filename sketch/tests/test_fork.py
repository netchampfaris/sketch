# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""Fork copies a public Prototype into the caller's own gallery.

The one write on /feed. `sketch.api.fork_prototype` reads the source through
`prototype.resolve_readable`, so `is_public` is the whole permission check on
the way in, and the row it makes is owned by the caller.

Three things must hold, and each has a case here.

- The copy is the whole tree, byte for byte, and the Pin the tree was written
  against. A fork that renders differently from the card it was taken from is
  not a copy.
- The fork is private. Publishing is the new owner's decision, never
  inherited.
- Nothing about the source moves. A fork is a read of somebody else's work.

There is no `allow_guest`, unlike the reads beside it: a fork makes a document
owned by the caller, so the caller has to be somebody.
"""

import frappe
from frappe.tests import IntegrationTestCase, set_user

from sketch import api, prototype_files
from sketch.tests import utils

#: The fixture tree. A file in the root and two levels under src/, so the copy
#: is checked at more than one depth.
FILES = {
	"README.md": "# hello\n",
	"src/App.vue": "<template><RouterView /></template>\n",
	"src/pages/Home.vue": "<template><h1>hi</h1></template>\n",
}


class TestFork(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_runtime()
		cls.author = utils.make_user("fork", "d2tfork")
		cls.addClassCleanup(utils.drop_user, cls.author)
		cls.reader = utils.make_user("forkread", "d2tforkread")
		cls.addClassCleanup(utils.drop_user, cls.reader)

		cls.doc = utils.make_prototype(
			cls.author, "d2t-fork", files=FILES, is_public=True, title="D2t Fork Source"
		)
		cls.addClassCleanup(utils.drop_prototype, cls.doc.name)
		cls.shut = utils.make_prototype(cls.author, "d2t-fork-private", files=FILES)
		cls.addClassCleanup(utils.drop_prototype, cls.shut.name)
		cls.handle = utils.username_of(cls.author)

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		super().tearDownClass()

	def fork(self, slug: str = "", user: str = "") -> dict:
		"""Fork as `user`, and clean the copy up afterwards."""
		with set_user(user or self.reader):
			row = api.fork_prototype(self.handle, slug or self.doc.slug)

		self.addCleanup(utils.drop_prototype, row["name"])
		return row

	# ---------------------------------------------------------------- the copy

	def test_the_fork_belongs_to_the_caller(self):
		row = self.fork()

		self.assertEqual(frappe.db.get_value("Sketch Prototype", row["name"], "owner"), self.reader)

	def test_every_file_is_copied_word_for_word(self):
		row = self.fork()

		self.assertEqual(prototype_files.read_tree(row["name"]), FILES)

	def test_the_fork_keeps_the_title(self):
		"""Two people may hold one title. The slug is freed per owner, so the
		copy needs no renaming to sit in the caller's gallery."""
		self.assertEqual(self.fork()["title"], self.doc.title)

	def test_the_fork_keeps_the_pin(self):
		"""The tree was written against that Runtime."""
		self.assertEqual(self.fork()["pin"], self.doc.pin)

	def test_the_fork_is_private(self):
		"""Publishing is the new owner's decision, never inherited."""
		self.assertFalse(self.fork()["is_public"])

	def test_the_fork_has_its_own_address(self):
		"""`/u/<username>/<slug>` is the only address a Prototype has, and the
		fork's is under the caller's own username."""
		row = self.fork()

		self.assertEqual(row["viewer_path"], f"/u/d2tforkread/{row['slug']}")

	def test_forking_twice_makes_two_prototypes(self):
		"""`prototype._free_slug` adds the suffix. A second fork must not
		collide with the first, or the unique index refuses it."""
		first = self.fork()
		second = self.fork()

		self.assertNotEqual(first["name"], second["name"])
		self.assertNotEqual(first["slug"], second["slug"])

	def test_the_source_does_not_move(self):
		"""A fork is a read of somebody else's work."""
		before = prototype_files.read_tree(self.doc.name)
		self.fork()

		self.assertEqual(prototype_files.read_tree(self.doc.name), before)
		self.assertTrue(frappe.db.get_value("Sketch Prototype", self.doc.name, "is_public"))

	# ------------------------------------------------------------- who may ask

	def test_a_private_prototype_cannot_be_forked(self):
		"""`is_public` is the whole check on the way in."""
		with set_user(self.reader):
			with self.assertRaises(frappe.DoesNotExistError):
				api.fork_prototype(self.handle, self.shut.slug)

	def test_a_guest_cannot_fork(self):
		"""The write needs an owner. `fork_prototype` carries no
		`allow_guest`, unlike the reads beside it, and the feed card hides the
		row for a signed-out reader."""
		with set_user("Guest"):
			with self.assertRaises(frappe.PermissionError):
				api.fork_prototype(self.handle, self.doc.slug)

	def test_the_owner_may_fork_their_own(self):
		"""Nothing special, and nothing refused: it is a copy like any other."""
		row = self.fork(user=self.author)

		self.assertEqual(frappe.db.get_value("Sketch Prototype", row["name"], "owner"), self.author)

	# ------------------------------------------------------------- a big tree

	def test_a_tree_over_one_batch_still_forks(self):
		"""A tree holds up to `MAX_TREE_FILES` (500), and one write carries at
		most `MAX_BATCH_FILES` (100). `api._copy_tree` slices, so a Prototype
		above the batch cap can still be copied instead of being readable and
		exportable but never forkable."""
		count = prototype_files.MAX_BATCH_FILES + 50
		big = utils.make_prototype(self.author, "d2t-fork-big", is_public=True, title="D2t Fork Big")
		self.addCleanup(utils.drop_prototype, big.name)

		with set_user(self.author):
			for start in range(0, count, prototype_files.MAX_BATCH_FILES):
				prototype_files.write_files(
					big.name,
					[
						{"path": f"src/pages/P{i}.vue", "content": f"<template>{i}</template>\n"}
						for i in range(start, min(start + prototype_files.MAX_BATCH_FILES, count))
					],
				)

		row = self.fork(slug=big.slug, user=self.reader)

		self.assertEqual(prototype_files.read_tree(row["name"]), prototype_files.read_tree(big.name))
		self.assertEqual(len(prototype_files.read_tree(row["name"])), count)
