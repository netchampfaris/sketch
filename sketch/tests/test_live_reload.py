# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The Viewer's live reload: the revision string, and who is allowed to poll.

Two parts, both cheap:

- `prototype_files.revision` must move for every write, add and delete a
  Sketch writer can make. It is a stat walk, so the mtime has to move too.
- The renderer must send `live: true` to the owner's own tab and to nobody
  else. `check` reports console errors, and a Guest polling an owner-only
  method would raise a permission error every two seconds.
"""

import os
import time

import frappe
from frappe.tests import IntegrationTestCase, set_user

from sketch import prototype_files, signature
from sketch.tests import utils
from sketch.viewer import SketchViewerRenderer

FILES = {"src/App.vue": "<template><h1>hello</h1></template>\n"}


def bump(name: str, path: str, content: str) -> None:
	"""Write a file and make sure the mtime moved.

	A test can write twice inside one filesystem timestamp tick. Real edits are
	seconds apart, so this is a test problem only.
	"""
	prototype_files.write_files(name, [{"path": path, "content": content}])
	absolute = prototype_files.safe_join(name, path)
	stamp = time.time() + 1
	os.utime(absolute, (stamp, stamp))


class TestRevision(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_runtime()
		cls.user = utils.make_user("rev", "d2trev")
		cls.addClassCleanup(utils.drop_user, cls.user)
		cls.doc = utils.make_prototype(cls.user, "d2t-rev", files=FILES)
		cls.addClassCleanup(utils.drop_prototype, cls.doc.name)

	def test_a_missing_tree_has_no_revision(self):
		self.assertEqual(prototype_files.revision("d2t-no-such-prototype"), "")

	def test_the_revision_is_stable_when_nothing_changes(self):
		first = prototype_files.revision(self.doc.name)
		self.assertTrue(first)
		self.assertEqual(first, prototype_files.revision(self.doc.name))

	def test_the_revision_moves_when_a_file_changes(self):
		first = prototype_files.revision(self.doc.name)
		bump(self.doc.name, "src/App.vue", "<template><h1>changed</h1></template>\n")
		self.assertNotEqual(first, prototype_files.revision(self.doc.name))

	def test_the_revision_moves_when_a_file_is_added_or_deleted(self):
		first = prototype_files.revision(self.doc.name)
		bump(self.doc.name, "src/pages/Extra.vue", "<template><p>extra</p></template>\n")
		added = prototype_files.revision(self.doc.name)
		self.assertNotEqual(first, added)

		prototype_files.delete_file(self.doc.name, "src/pages/Extra.vue")
		self.assertNotEqual(added, prototype_files.revision(self.doc.name))


class TestLiveFlag(IntegrationTestCase):
	"""Who the renderer lets poll.

	The renderer is driven directly. `is_live` reads the session user and
	`frappe.form_dict`, which is all a real request gives it.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_runtime()
		cls.user = utils.make_user("live", "d2tlive")
		cls.addClassCleanup(utils.drop_user, cls.user)
		cls.username = utils.username_of(cls.user)
		cls.doc = utils.make_prototype(cls.user, "d2t-live", files=FILES, is_public=True)
		cls.addClassCleanup(utils.drop_prototype, cls.doc.name)

	def sign(self) -> None:
		"""Put a valid check signature in form_dict, the way a request does.

		`frappe.set_user` clears form_dict, so this runs inside the session
		block, never before it.
		"""
		stamp = signature.mint(self.doc.name, ttl_seconds=600)
		frappe.form_dict.update({"exp": stamp["exp"], "sig": stamp["sig"]})

	def payload(self) -> dict:
		renderer = SketchViewerRenderer(path=f"u/{self.username}/{self.doc.slug}")
		self.assertTrue(renderer.can_render())
		return renderer.payload()

	def test_the_owner_gets_the_poller(self):
		with set_user(self.user):
			payload = self.payload()

		self.assertTrue(payload["live"])
		self.assertEqual(payload["slug"], self.doc.slug, "the poller needs the slug")

	def test_a_guest_on_a_public_prototype_does_not_poll(self):
		with set_user("Guest"):
			self.assertFalse(self.payload()["live"])

	def test_a_check_request_does_not_poll(self):
		"""check arrives with the signature, so the page must stay quiet."""
		with set_user("Guest"):
			self.sign()
			self.assertFalse(self.payload()["live"])

	def test_the_owner_with_a_signature_does_not_poll(self):
		"""The signature marks a check, whoever the session says is asking."""
		with set_user(self.user):
			self.sign()
			self.assertFalse(self.payload()["live"])
