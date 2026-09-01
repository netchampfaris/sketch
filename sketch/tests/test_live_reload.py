# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The Viewer's live reload: the revision string, who may poll, and with what.

Three parts, all cheap:

- `prototype_files.revision` must move for every write, add and delete a
  Sketch writer can make. It is a stat walk, so the mtime has to move too.
- The renderer must send `live: true` to the owner's own tab and to nobody
  else. `check` reports console errors, and a Guest has no agent writing to
  the tree it is reading.
- The poll must authenticate with the minted signature, because the Viewer
  document is sandboxed into an opaque origin and sends no cookie
  (`sketch/viewer.py` SANDBOX). `sketch.api.signed_revision` is that door, and
  it must open one revision number and nothing else.
"""

import os
import time
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase, set_user

from sketch import api, prototype_files, signature
from sketch.tests import utils
from sketch.viewer import LIVE_TTL_SECONDS, SketchViewerRenderer

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
		"""Put a valid `check` signature in form_dict, the way a request does.

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
		self.assertEqual(payload["name"], self.doc.name, "the poller names the hash id")

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

	def test_only_a_live_page_carries_and_computes_a_revision(self):
		"""The baseline the poller starts from, and who pays for the walk.

		The renderer reads the revision at render time so a write in the two
		seconds before the first poll still reloads the page. It is a stat
		walk, so the two callers that never poll must not run it.
		"""
		calls = []
		real = prototype_files.revision

		def counted(name: str) -> str:
			calls.append(name)
			return real(name)

		with patch.object(prototype_files, "revision", counted):
			with set_user(self.user):
				owner = self.payload()

			self.assertEqual(calls, [self.doc.name], "the owner pays for one walk")
			self.assertEqual(owner["rev"], real(self.doc.name))

			calls.clear()
			with set_user("Guest"):
				guest = self.payload()

			with set_user("Guest"):
				self.sign()
				checked = self.payload()

			with set_user(self.user):
				self.sign()
				signed_owner = self.payload()

		self.assertEqual(calls, [], "a Guest and a check request compute nothing")
		self.assertEqual(guest["rev"], "")
		self.assertEqual(checked["rev"], "")
		self.assertEqual(signed_owner["rev"], "")


class TestPollCredential(IntegrationTestCase):
	"""What the live page is handed to poll with.

	The document sits in an opaque origin, so it sends no session cookie. The
	renderer mints a signature into the payload instead, and only a live page
	is given one.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_runtime()
		cls.user = utils.make_user("cred", "d2tcred")
		cls.addClassCleanup(utils.drop_user, cls.user)
		cls.username = utils.username_of(cls.user)
		cls.doc = utils.make_prototype(cls.user, "d2t-cred", files=FILES, is_public=True)
		cls.addClassCleanup(utils.drop_prototype, cls.doc.name)
		cls.other = utils.make_prototype(cls.user, "d2t-cred-two", files=FILES)
		cls.addClassCleanup(utils.drop_prototype, cls.other.name)

	def payload(self) -> dict:
		renderer = SketchViewerRenderer(path=f"u/{self.username}/{self.doc.slug}")
		self.assertTrue(renderer.can_render())
		return renderer.payload()

	def test_the_owners_page_carries_a_revision_signature(self):
		with set_user(self.user):
			payload = self.payload()

		self.assertTrue(payload["sig"], "a live page must be able to poll")
		self.assertTrue(
			signature.verify(self.doc.name, payload["exp"], payload["sig"], signature.REVISION)
		)

	def test_the_credential_outlives_a_working_session(self):
		"""A `check` TTL would leave the tab dead a minute after it opened."""
		with set_user(self.user):
			payload = self.payload()

		self.assertGreaterEqual(LIVE_TTL_SECONDS, 4 * 60 * 60)
		self.assertGreater(int(payload["exp"]) - int(time.time()), 4 * 60 * 60)

	def test_the_credential_does_not_open_the_viewer_document(self):
		"""Scope REVISION, so the page's own code cannot read the tree with it.

		The payload is read by whatever JavaScript the tree holds, and a fork
		means that code is a stranger's. A VIEW signature there would be a
		twelve hour link to the reader's own Prototype.
		"""
		with set_user(self.user):
			payload = self.payload()

		self.assertFalse(
			signature.verify(self.doc.name, payload["exp"], payload["sig"]),
			"the poll credential must not verify as a view signature",
		)

	def test_the_credential_names_one_prototype(self):
		"""It cannot be replayed against another tree, not even the owner's."""
		with set_user(self.user):
			payload = self.payload()

		self.assertFalse(
			signature.verify(self.other.name, payload["exp"], payload["sig"], signature.REVISION)
		)

	def test_a_page_that_does_not_poll_is_given_nothing(self):
		"""A Guest and a `check` request hold no credential at all."""
		with set_user("Guest"):
			guest = self.payload()

		self.assertEqual((guest["exp"], guest["sig"]), ("", ""))


class TestSignedRevisionEndpoint(IntegrationTestCase):
	"""`sketch.api.signed_revision`: the poller's door, with no session.

	It runs as a Guest on purpose. The signature is the whole authentication,
	so each case drives the method with `set_user("Guest")`.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_runtime()
		cls.user = utils.make_user("sigrev", "d2tsigrev")
		cls.addClassCleanup(utils.drop_user, cls.user)
		cls.doc = utils.make_prototype(cls.user, "d2t-sigrev", files=FILES)
		cls.addClassCleanup(utils.drop_prototype, cls.doc.name)
		cls.other = utils.make_prototype(cls.user, "d2t-sigrev-two", files=FILES)
		cls.addClassCleanup(utils.drop_prototype, cls.other.name)

	def stamp(self, name: str, ttl_seconds: int = 600, scope: str = signature.REVISION) -> dict:
		return signature.mint(name, ttl_seconds=ttl_seconds, scope=scope)

	def test_a_good_signature_reads_the_revision_without_a_session(self):
		mark = self.stamp(self.doc.name)
		with set_user("Guest"):
			answer = api.signed_revision(self.doc.name, str(mark["exp"]), mark["sig"])

		self.assertEqual(answer, {"rev": prototype_files.revision(self.doc.name)})

	def test_it_answers_the_revision_and_nothing_else(self):
		"""No title, no owner, no file. One number is the whole capability."""
		mark = self.stamp(self.doc.name)
		with set_user("Guest"):
			answer = api.signed_revision(self.doc.name, str(mark["exp"]), mark["sig"])

		self.assertEqual(list(answer), ["rev"])

	def test_the_answer_is_readable_from_an_opaque_origin(self):
		"""Origin "null" matches no allowlist, so the header has to be "*"."""
		mark = self.stamp(self.doc.name)
		with set_user("Guest"):
			api.signed_revision(self.doc.name, str(mark["exp"]), mark["sig"])

		self.assertEqual(frappe.local.response_headers["Access-Control-Allow-Origin"], "*")

	def test_a_missing_signature_is_a_404(self):
		with set_user("Guest"), self.assertRaises(frappe.DoesNotExistError):
			api.signed_revision(self.doc.name)

	def test_a_forged_signature_is_a_404(self):
		mark = self.stamp(self.doc.name)
		with set_user("Guest"), self.assertRaises(frappe.DoesNotExistError):
			api.signed_revision(self.doc.name, str(mark["exp"]), "0" * 64)

	def test_an_expired_signature_is_a_404(self):
		mark = self.stamp(self.doc.name, ttl_seconds=-60)
		with set_user("Guest"), self.assertRaises(frappe.DoesNotExistError):
			api.signed_revision(self.doc.name, str(mark["exp"]), mark["sig"])

	def test_another_prototypes_signature_is_a_404(self):
		"""The signature covers the hash id, so it reads one tree only."""
		mark = self.stamp(self.other.name)
		with set_user("Guest"), self.assertRaises(frappe.DoesNotExistError):
			api.signed_revision(self.doc.name, str(mark["exp"]), mark["sig"])

	def test_a_view_signature_is_a_404(self):
		"""A `check` link must not become a revision reader, or the reverse."""
		mark = self.stamp(self.doc.name, scope=signature.VIEW)
		with set_user("Guest"), self.assertRaises(frappe.DoesNotExistError):
			api.signed_revision(self.doc.name, str(mark["exp"]), mark["sig"])


class TestSignedRevisionOnTheWire(IntegrationTestCase):
	"""The same method over HTTP, which is how the Viewer reaches it.

	The unit cases above cannot see the status code or the header the browser
	reads, and both are the point.
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

	def get(self, name: str, mark: dict) -> object:
		path = (
			"/api/method/sketch.api.signed_revision"
			f"?name={name}&exp={mark['exp']}&sig={mark['sig']}"
		)
		# `Origin: null` is what a sandboxed document sends.
		return utils.request("GET", path, headers={"Origin": "null"})

	def test_a_guest_with_the_signature_reads_the_revision(self):
		mark = signature.mint(self.doc.name, ttl_seconds=600, scope=signature.REVISION)
		response = self.get(self.doc.name, mark)

		self.assertEqual(response.status_code, 200, response.text[:400])
		self.assertEqual(response.json()["message"]["rev"], prototype_files.revision(self.doc.name))
		self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "*")
		self.assertIsNone(
			response.headers.get("Access-Control-Allow-Credentials"),
			"the signature is the whole authentication; a cookie must not widen it",
		)

	def test_a_forged_signature_answers_404(self):
		mark = signature.mint(self.doc.name, ttl_seconds=600, scope=signature.REVISION)
		mark = {"exp": mark["exp"], "sig": "0" * 64}
		response = self.get(self.doc.name, mark)

		self.assertEqual(response.status_code, 404, response.text[:400])
