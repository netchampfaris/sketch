# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The Viewer is a shell with the Prototype in a sandboxed frame.

/u/<username>/<slug> is Sketch's own page on Sketch's origin. It holds the reader's session and no
Prototype source, and it frames the Prototype from the same URL with ?frame=1. The frame is
sandboxed and carries the tree and nothing that can act as anyone: no signature, ticket or CSRF
token, for any reader. `check` keeps its signed URL and gets the document with its chrome off.
"""

import os
from contextlib import contextmanager

import frappe
from frappe.tests import IntegrationTestCase, set_user

from sketch import api, comments, signature
from sketch.tests import utils
from sketch.tests.utils import credential_keys, shell_slot
from sketch.viewer import SHELL_HTML, SketchViewerRenderer

FILES = {"src/App.vue": "<template><h1>hello</h1></template>\n"}

CSP = "Content-Security-Policy"

#: Everything the frame may hold, and no more.
FRAME_KEYS = {"files", "name", "title", "slug", "pin", "authors", "theme", "chrome"}

#: The doors the shell replaced. Each acted on a signature in the page, so none may come back.
REMOVED = {
	api: (
		"set_variant_default_signed",
		"undo_variant_default_signed",
		"keep_variant_signed",
		"undo_keep_variant_signed",
		"delete_variant_signed",
		"undo_delete_variant_signed",
		"signed_revision",
		"save_annotations",
		"comment_pass",
		"comments_list",
		"comment_add",
		"comment_reply",
		"comment_edit",
		"comment_delete",
		"comment_restore",
		"comments_delete_resolved",
		"comment_resolve",
		"seen_mark",
		"comment_note_draft",
	),
	comments: ("mint_ticket", "mint_pass", "actor_for"),
	signature: ("subject", "signed_user", "REVISION", "ANNOTATE", "COMMENT", "COMMENT_MINT", "VARIANT_DEFAULT", "VARIANT_EDIT", "SEEN"),
}


class ShellCase(IntegrationTestCase):
	"""An owner, an invited editor, a signed-in reader, and a public and a private Prototype."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_runtime()
		for attr, suffix in (("owner", "shown"), ("editor", "shed"), ("reader", "shrd")):
			email = utils.make_user(suffix, f"d2t{suffix}")
			cls.addClassCleanup(utils.drop_user, email)
			setattr(cls, attr, email)

		cls.username = utils.username_of(cls.owner)
		cls.public = utils.make_prototype(cls.owner, "d2t-shell-public", files=FILES, is_public=True)
		cls.addClassCleanup(utils.drop_prototype, cls.public.name)
		cls.private = utils.make_prototype(cls.owner, "d2t-shell-private", files=FILES)
		cls.addClassCleanup(utils.drop_prototype, cls.private.name)
		with set_user(cls.owner):
			api.invite_editor(cls.public.slug, utils.username_of(cls.editor))
		frappe.db.commit()

	@contextmanager
	def query(self, **params):
		saved = frappe.local.form_dict
		frappe.local.form_dict = frappe._dict(params)
		try:
			yield
		finally:
			frappe.local.form_dict = saved

	def renderer(self, user, doc, **params):
		"""A renderer that ran can_render as `user`, or None when the answer is 404."""
		with set_user(user), self.query(**params):
			renderer = SketchViewerRenderer(path=f"u/{self.username}/{doc.slug}")
			return renderer if renderer.can_render() else None

	def render(self, user, doc, **params):
		with set_user(user), self.query(**params):
			renderer = SketchViewerRenderer(path=f"u/{self.username}/{doc.slug}")
			self.assertTrue(renderer.can_render(), user)
			return renderer.render()

	def require_shell(self):
		if not os.path.isfile(frappe.get_app_path("sketch", *SHELL_HTML)):
			self.skipTest("the frontend is not built, so there is no shell page")

	def readers(self):
		return (("owner", self.owner), ("editor", self.editor), ("reader", self.reader), ("guest", "Guest"))


class TestShell(ShellCase):
	def setUp(self):
		super().setUp()
		self.require_shell()

	def test_the_shell_is_not_sandboxed_and_cannot_be_framed(self):
		for role, user in self.readers():
			with self.subTest(role):
				response = self.render(user, self.public)
				policy = response.headers[CSP]
				self.assertEqual(response.status_code, 200)
				self.assertNotIn("sandbox", policy)
				self.assertIn("frame-ancestors 'none'", policy)
				self.assertIn("frame-src 'self'", policy)
				self.assertIn("object-src 'none'", policy)
				self.assertIn("base-uri 'self'", policy)
				self.assertEqual(response.headers["Cache-Control"], "no-store")

	def test_the_shell_carries_no_files(self):
		for role, user in self.readers():
			with self.subTest(role):
				page = self.render(user, self.public).get_data(as_text=True)
				data = shell_slot(page)
				self.assertNotIn("files", data)
				self.assertNotIn("sketch-data", page)
				self.assertNotIn("hello", page)

	def test_the_shell_names_the_reader_and_frames_the_same_url(self):
		data = shell_slot(self.render(self.owner, self.public).get_data(as_text=True))
		self.assertEqual(data["role"], "owner")
		self.assertTrue(data["rev"], "the owner's poller needs its baseline")
		self.assertTrue(data["csrf_token"])
		self.assertEqual(data["frame_src"], f"/u/{self.username}/{self.public.slug}?frame=1")

		data = shell_slot(self.render(self.editor, self.public).get_data(as_text=True))
		self.assertEqual((data["role"], data["rev"]), ("editor", ""))

		data = shell_slot(self.render("Guest", self.public).get_data(as_text=True))
		self.assertEqual((data["role"], data["me"], data["csrf_token"]), ("guest", None, ""))
		self.assertTrue(data["sign_in"])


class TestFrame(ShellCase):
	def test_the_frame_is_sandboxed(self):
		for role, user in self.readers():
			with self.subTest(role):
				policy = self.render(user, self.public, frame="1").headers[CSP]
				self.assertIn("sandbox allow-scripts allow-forms allow-popups", policy)
				self.assertNotIn("allow-same-origin", policy)
				self.assertIn("frame-ancestors 'self'", policy)

	def test_the_frame_holds_no_credential_for_anyone(self):
		for role, user in self.readers():
			with self.subTest(role):
				data = utils.data_slot(self.render(user, self.public, frame="1").get_data(as_text=True))
				self.assertEqual(credential_keys(data), [])
				self.assertEqual(set(data), FRAME_KEYS)
				self.assertEqual(data["chrome"], "shell")
				self.assertIn("src/App.vue", data["files"])

	def test_the_frame_follows_the_theme_the_shell_asks_for(self):
		data = utils.data_slot(self.render(self.owner, self.public, frame="1", theme="dark").get_data(as_text=True))
		self.assertEqual(data["theme"], "dark")


class TestAccessIsUnchanged(ShellCase):
	def test_a_private_prototype_is_404_to_the_uninvited_and_a_guest(self):
		for user in (self.reader, "Guest"):
			for params in ({}, {"frame": "1"}):
				with self.subTest(user=user, **params):
					self.assertIsNone(self.renderer(user, self.private, **params))

	def test_the_owner_opens_a_private_shell_and_frame(self):
		self.assertEqual(self.renderer(self.owner, self.private).mode, "shell")
		self.assertEqual(self.renderer(self.owner, self.private, frame="1").mode, "frame")


class TestCheck(ShellCase):
	def test_a_check_request_gets_the_document_with_its_chrome_off(self):
		stamp = signature.mint(self.private.name, ttl_seconds=600)
		renderer = self.renderer("Guest", self.private, theme="light", **stamp)
		self.assertIsNotNone(renderer, "the signed URL still opens a private Prototype")
		self.assertEqual(renderer.mode, "check")

		response = self.render("Guest", self.private, theme="light", **stamp)
		self.assertIn("sandbox allow-scripts", response.headers[CSP])
		data = utils.data_slot(response.get_data(as_text=True))
		self.assertIn("src/App.vue", data["files"])
		self.assertEqual(data["chrome"], "off")
		self.assertEqual(credential_keys(data), [])
		self.assertEqual(set(data), FRAME_KEYS)


class TestNothingSignedIsLeft(ShellCase):
	def test_every_removed_door_is_gone(self):
		for module, names in REMOVED.items():
			for name in names:
				with self.subTest(f"{module.__name__}.{name}"):
					self.assertFalse(hasattr(module, name))

	def test_no_removed_method_answers_over_http(self):
		for name in REMOVED[api]:
			with self.subTest(name):
				self.assertRaises(Exception, frappe.get_attr, f"sketch.api.{name}")

	def test_no_frame_payload_for_any_role_holds_a_credential(self):
		# The editor is invited to the public one only, so the private one is the owner's and check's.
		cases = [(self.public, role, user) for role, user in self.readers()]
		cases += [(self.private, "owner", self.owner), (self.public, "check", "Guest"), (self.private, "check", "Guest")]
		for doc, role, user in cases:
			params = signature.mint(doc.name, ttl_seconds=600) if role == "check" else {"frame": "1"}
			with self.subTest(doc=doc.slug, role=role), set_user(user), self.query(**params):
				renderer = SketchViewerRenderer(path=f"u/{self.username}/{doc.slug}")
				self.assertTrue(renderer.can_render())
				data = renderer.frame_payload()
				self.assertEqual(credential_keys(data), [])
				self.assertEqual(set(data), FRAME_KEYS)
