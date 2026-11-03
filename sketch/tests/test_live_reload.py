# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The Viewer's live reload: the revision string, who may poll, and with what.

Three parts, all cheap:

- `prototype_files.revision` must move for every write, add and delete a
  Sketch writer can make. It is a stat walk, so the mtime has to move too.
- The shell must carry a baseline `rev` to the owner's own tab and to nobody
  else. `check` reports console errors, and a Guest has no agent writing to
  the tree it is reading.
- The poll is the shell's, on Sketch's origin, with the owner's session
  (runtime/shell/liveReload.ts). `sketch.api.prototype_revision` is that door:
  the owner's alone, and one revision number and nothing else. The sandboxed
  frame holds nothing to poll with.
"""

import os
import time
from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase, set_user

from sketch import api, prototype_files, signature
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


class LiveCase(IntegrationTestCase):
	"""An owner with a public Prototype, and a renderer driven the way a request drives it.

	`is_live` reads the session user and `frappe.form_dict`, which is all a real
	request gives it.
	"""

	suffix = "live"

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_runtime()
		cls.user = utils.make_user(cls.suffix, f"d2t{cls.suffix}")
		cls.addClassCleanup(utils.drop_user, cls.user)
		cls.username = utils.username_of(cls.user)
		cls.doc = utils.make_prototype(cls.user, f"d2t-{cls.suffix}", files=FILES, is_public=True)
		cls.addClassCleanup(utils.drop_prototype, cls.doc.name)

	@contextmanager
	def query(self, **params):
		saved = frappe.local.form_dict
		frappe.local.form_dict = frappe._dict(params)
		try:
			yield
		finally:
			frappe.local.form_dict = saved

	def renderer(self, user, **params) -> SketchViewerRenderer:
		"""A renderer that ran can_render as `user`. Call it inside the session and query blocks."""
		renderer = SketchViewerRenderer(path=f"u/{self.username}/{self.doc.slug}")
		self.assertTrue(renderer.can_render(), user)
		return renderer

	def shell(self, user) -> dict:
		with set_user(user), self.query():
			return self.renderer(user).shell_payload()

	def frame(self, user, **params) -> tuple[str, dict]:
		"""The mode and the data slot of the document a request with `params` gets."""
		with set_user(user), self.query(**params):
			renderer = self.renderer(user)
			return renderer.mode, renderer.frame_payload()

	def check(self, user) -> tuple[str, dict]:
		"""What a `check` request gets: the signature in the query, whoever the session is."""
		return self.frame(user, **signature.mint(self.doc.name, ttl_seconds=600))


class TestLiveFlag(LiveCase):
	"""Who the shell lets poll: the one with a non-empty `rev`."""

	def test_the_owner_gets_the_poller(self):
		shell = self.shell(self.user)
		self.assertTrue(shell["rev"])
		self.assertEqual(shell["role"], "owner")
		self.assertEqual(shell["name"], self.doc.name, "the poller names the hash id")
		self.assertEqual(shell["slug"], self.doc.slug, "and asks by slug")

	def test_a_guest_on_a_public_prototype_does_not_poll(self):
		self.assertEqual(self.shell("Guest")["rev"], "")

	def test_a_check_request_does_not_poll(self):
		"""check arrives with the signature and gets the bare document, with nothing to poll with."""
		mode, data = self.check("Guest")
		self.assertEqual(mode, "check")
		self.assertNotIn("rev", data)
		self.assertEqual(data["chrome"], "off")

	def test_the_owner_with_a_signature_does_not_poll(self):
		"""The signature marks a check, whoever the session says is asking."""
		mode, data = self.check(self.user)
		self.assertEqual(mode, "check")
		self.assertNotIn("rev", data)
		self.assertEqual(data["chrome"], "off")

	def test_only_a_live_page_carries_and_computes_a_revision(self):
		"""The baseline the poller starts from, and who pays for the walk.

		The shell reads the revision at render time so a write in the two
		seconds before the first poll still reloads the page. It is a stat
		walk, so the callers that never poll must not run it.
		"""
		calls = []
		real = prototype_files.revision

		def counted(name: str) -> str:
			calls.append(name)
			return real(name)

		with patch.object(prototype_files, "revision", counted):
			owner = self.shell(self.user)
			self.assertEqual(calls, [self.doc.name], "the owner pays for one walk")
			self.assertEqual(owner["rev"], real(self.doc.name))

			calls.clear()
			guest = self.shell("Guest")
			self.check("Guest")
			self.check(self.user)
			self.frame(self.user, frame="1")

		self.assertEqual(calls, [], "a Guest, a check request and the frame compute nothing")
		self.assertEqual(guest["rev"], "")


class TestPollCredential(LiveCase):
	"""What the poll authenticates with: the owner's session, never anything in the frame.

	The frame runs the tree's code, which a fork makes a stranger's, so nothing
	in it may read the tree again or say who is reading.
	"""

	suffix = "cred"

	def test_the_owners_frame_carries_nothing_to_poll_with(self):
		_, data = self.frame(self.user, frame="1")
		self.assertEqual(utils.credential_keys(data), [])
		self.assertNotIn("rev", data)

	def test_a_check_document_carries_nothing_to_poll_with(self):
		_, data = self.check("Guest")
		self.assertEqual(utils.credential_keys(data), [])

	def test_the_shell_polls_with_the_session_and_its_csrf_token(self):
		"""The shell is Sketch's own page, so the session is the whole credential."""
		shell = self.shell(self.user)
		self.assertTrue(shell["csrf_token"])
		self.assertEqual(utils.credential_keys({k: v for k, v in shell.items() if k != "csrf_token"}), [])

	def test_the_old_signed_door_is_gone(self):
		self.assertFalse(hasattr(api, "signed_revision"))
		self.assertFalse(hasattr(signature, "REVISION"))


class TestRevisionEndpoint(IntegrationTestCase):
	"""`sketch.api.prototype_revision`: the shell's poll, with the owner's session."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_runtime()
		cls.user = utils.make_user("sigrev", "d2tsigrev")
		cls.addClassCleanup(utils.drop_user, cls.user)
		cls.stranger = utils.make_user("sigrevx", "d2tsigrevx")
		cls.addClassCleanup(utils.drop_user, cls.stranger)
		cls.doc = utils.make_prototype(cls.user, "d2t-sigrev", files=FILES, is_public=True)
		cls.addClassCleanup(utils.drop_prototype, cls.doc.name)
		cls.other = utils.make_prototype(cls.stranger, "d2t-sigrev-two", files=FILES)
		cls.addClassCleanup(utils.drop_prototype, cls.other.name)

	def test_the_owner_reads_the_revision(self):
		with set_user(self.user):
			answer = api.prototype_revision(self.doc.slug)

		self.assertEqual(answer, {"rev": prototype_files.revision(self.doc.name)})

	def test_it_answers_the_revision_and_nothing_else(self):
		"""No title, no owner, no file. One number is the whole answer."""
		with set_user(self.user):
			answer = api.prototype_revision(self.doc.slug)

		self.assertEqual(list(answer), ["rev"])

	def test_a_guest_is_refused(self):
		with set_user("Guest"), self.assertRaises(frappe.DoesNotExistError):
			api.prototype_revision(self.doc.slug)

	def test_a_reader_of_a_public_prototype_is_refused(self):
		"""Nobody but the owner has an agent writing to the tree, so nobody else polls it."""
		with set_user(self.stranger), self.assertRaises(frappe.DoesNotExistError):
			api.prototype_revision(self.doc.slug)

	def test_it_reads_the_callers_own_tree_only(self):
		"""A slug names the caller's own Prototype, so another owner's tree is out of reach."""
		with set_user(self.user), self.assertRaises(frappe.DoesNotExistError):
			api.prototype_revision(self.other.slug)


class TestRevisionOnTheWire(IntegrationTestCase):
	"""The same method over HTTP, which is how the shell reaches it.

	The unit cases above cannot see the status code the browser reads.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_runtime()
		cls.user = utils.make_user("sigwire", "d2tsigwire")
		cls.addClassCleanup(utils.drop_user, cls.user)
		cls.doc = utils.make_prototype(cls.user, "d2t-sigwire", files=FILES)
		cls.addClassCleanup(utils.drop_prototype, cls.doc.name)

	def setUp(self):
		utils.require_webserver()

	def get(self, headers: dict | None = None) -> object:
		path = f"/api/method/sketch.api.prototype_revision?slug={self.doc.slug}"
		return utils.request("GET", path, headers=headers)

	def test_the_owner_reads_the_revision(self):
		response = self.get(utils.api_auth_header(self.user))

		self.assertEqual(response.status_code, 200, response.text[:400])
		self.assertEqual(response.json()["message"]["rev"], prototype_files.revision(self.doc.name))

	def test_a_guest_is_refused(self):
		response = self.get()

		self.assertIn(response.status_code, (403, 404), response.text[:400])

	def test_the_signed_door_answers_nothing(self):
		mark = signature.mint(self.doc.name, ttl_seconds=600)
		path = f"/api/method/sketch.api.signed_revision?name={self.doc.name}&exp={mark['exp']}&sig={mark['sig']}"
		response = utils.request("GET", path, headers={"Origin": "null"})

		self.assertNotEqual(response.status_code, 200, response.text[:400])
