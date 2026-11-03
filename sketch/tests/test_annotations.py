# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The owner's notes and tweaks: the save door, the shell's boot data, and the agent's tools.

The Viewer's shell writes through `sketch.viewer_api.save_annotations` with the
reader's session and its CSRF token. The agent reads and clears the same rows
over MCP. Each case drives the method directly as the session's person, except
the one that needs the HTTP door itself.
"""

import json
from contextlib import contextmanager

import frappe
from frappe.sessions import delete_session
from frappe.tests import IntegrationTestCase, set_user

from sketch import annotations, api, prototype_files, signature, viewer_api
from sketch.mcp import tools
from sketch.tests import utils
from sketch.tests.test_viewer_api import open_session, post
from sketch.viewer import SketchViewerRenderer

FILES = {"src/App.vue": "<template><h1>hello</h1></template>\n"}

NOTE = {"id": "n1", "route": "/", "note": "Make it bigger", "offset": {"x": 0, "y": 0}, "rect": {}}
TWEAK = {"id": "t1", "group": "g1", "route": "/", "classes": ["p-2"], "original": {"classes": []}, "props": {}}


def body(**over) -> str:
	return json.dumps({"notes": [NOTE], "tweaks": [TWEAK], "prompt": "do it", **over})


class TestSaveAnnotations(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_runtime()
		cls.user = utils.make_user("annsave", "d2tannsave")
		cls.addClassCleanup(utils.drop_user, cls.user)
		cls.stranger = utils.make_user("annsavex", "d2tannsavex")
		cls.addClassCleanup(utils.drop_user, cls.stranger)
		cls.doc = utils.make_prototype(cls.user, "d2t-annsave", files=FILES)
		cls.addClassCleanup(utils.drop_prototype, cls.doc.name)

	def save(self, data: str, user: str | None = None, epoch: str | None = None) -> dict:
		"""A save from a page that loaded now, unless `epoch` says otherwise."""
		if epoch is None:
			epoch = str(annotations.epoch(self.doc.name))

		with set_user(user or self.user):
			return viewer_api.save_annotations(self.doc.name, data, epoch)

	def test_a_good_save_is_stored_and_read_back(self):
		self.save(body(anchor="top-left"))
		saved = annotations.read(self.doc.name)
		self.assertEqual(saved["notes"], [NOTE])
		self.assertEqual(saved["tweaks"], [TWEAK])
		self.assertEqual(saved["prompt"], "do it")
		self.assertEqual(saved["anchor"], "top-left")
		self.assertTrue(saved["updated"], "the server stamps the time")

	def test_angle_brackets_survive_the_http_door(self):
		"""Notes name components ("<Badge>"); the form data must reach the field as sent."""
		note = {**NOTE, "note": "Use <Badge> here & keep <b>bold</b>"}
		form = {
			"name": self.doc.name,
			"data": json.dumps({"notes": [note], "tweaks": []}),
			"epoch": str(annotations.epoch(self.doc.name)),
		}
		frappe.db.commit()  # the request reads this Prototype through its own connection
		sid, token = open_session(self.user)
		self.addCleanup(delete_session, sid)
		status = post(
			"/api/method/sketch.viewer_api.save_annotations",
			form,
			{"Cookie": f"sid={sid}", "X-Frappe-CSRF-Token": token},
		)
		self.assertEqual(status, 200)
		frappe.db.rollback()
		self.assertEqual(annotations.read(self.doc.name)["notes"][0]["note"], note["note"])

	def test_unknown_keys_are_dropped(self):
		self.save(body(extra="x", updated="1999"))
		saved = annotations.read(self.doc.name)
		self.assertNotIn("extra", saved)
		self.assertNotEqual(saved["updated"], "1999")

	def test_a_guest_is_refused(self):
		before = annotations.read(self.doc.name)
		with self.assertRaises(frappe.PermissionError):
			self.save(body(prompt="a guest's"), user="Guest")

		self.assertEqual(annotations.read(self.doc.name), before)

	def test_someone_else_is_a_404(self):
		"""Another signed-in person writes no notes on a Prototype that is not theirs."""
		before = annotations.read(self.doc.name)
		with self.assertRaises(frappe.DoesNotExistError):
			self.save(body(prompt="a stranger's"), user=self.stranger)

		frappe.db.set_value("Sketch Prototype", self.doc.name, "is_public", 1)
		self.addCleanup(frappe.db.set_value, "Sketch Prototype", self.doc.name, "is_public", 0)
		with self.assertRaises(frappe.DoesNotExistError):
			self.save(body(prompt="a stranger's"), user=self.stranger)

		self.assertEqual(annotations.read(self.doc.name), before)

	def test_the_old_guest_door_is_gone(self):
		self.assertFalse(hasattr(api, "save_annotations"))
		self.assertFalse(hasattr(signature, "ANNOTATE"))

	def test_an_oversize_body_is_413(self):
		huge = json.dumps({"notes": [{"id": "x", "pad": "a" * annotations.MAX_BYTES}]})
		with self.assertRaises(annotations.AnnotationsTooLarge) as caught:
			self.save(huge)

		self.assertEqual(caught.exception.http_status_code, 413)

	def test_a_bad_shape_is_refused(self):
		cases = [
			"not json",
			"[]",
			json.dumps({"notes": "x"}),
			json.dumps({"notes": ["x"]}),
			json.dumps({"tweaks": [1]}),
			json.dumps({"prompt": 5}),
			json.dumps({"prompt": "a" * (annotations.MAX_PROMPT_BYTES + 1)}),
			json.dumps({"anchor": "middle"}),
		]
		for data in cases:
			with self.subTest(data=data[:40]), self.assertRaises(frappe.ValidationError):
				self.save(data)

	def test_a_page_from_before_a_clear_is_409(self):
		"""A tab open through the agent's clear must not write the cleared rows back."""
		self.save(body())
		annotations.clear(self.doc.name)
		with self.assertRaises(annotations.AnnotationsStale) as caught:
			self.save(body(), epoch="0")

		self.assertEqual(caught.exception.http_status_code, 409)
		self.assertEqual(annotations.read(self.doc.name)["notes"], [])
		self.save(body(), epoch=str(annotations.epoch(self.doc.name)))
		self.assertEqual(len(annotations.read(self.doc.name)["notes"]), 1)

	def test_a_client_save_does_not_move_the_revision(self):
		"""Saving must never reload the page that saved."""
		before = prototype_files.revision(self.doc.name)
		self.save(body())
		self.assertEqual(before, prototype_files.revision(self.doc.name))


class TestAnnotationsPayload(IntegrationTestCase):
	"""The owner's notes reach the shell, on Sketch's origin, and never the frame."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_runtime()
		cls.user = utils.make_user("annpay", "d2tannpay")
		cls.addClassCleanup(utils.drop_user, cls.user)
		cls.username = utils.username_of(cls.user)
		cls.doc = utils.make_prototype(cls.user, "d2t-annpay", files=FILES, is_public=True)
		cls.addClassCleanup(utils.drop_prototype, cls.doc.name)

	@contextmanager
	def renderer(self, user, **params):
		saved = frappe.local.form_dict
		with set_user(user):
			frappe.local.form_dict = frappe._dict(params)
			try:
				renderer = SketchViewerRenderer(path=f"u/{self.username}/{self.doc.slug}")
				self.assertTrue(renderer.can_render())
				yield renderer
			finally:
				frappe.local.form_dict = saved

	def shell(self, user) -> dict:
		with self.renderer(user) as renderer:
			return renderer.shell_payload()

	def test_the_owners_shell_carries_annotations_and_their_epoch(self):
		annotations.save(self.doc.name, body(), 0)
		shell = self.shell(self.user)

		self.assertEqual(shell["annotations"]["notes"], [NOTE])
		self.assertEqual(shell["annotations_epoch"], 0)
		self.assertTrue(shell["csrf_token"], "the shell saves with the session and its token")

	def test_the_frame_carries_no_notes_and_nothing_to_save_with(self):
		annotations.save(self.doc.name, body(), 0)
		with self.renderer(self.user, frame="1") as renderer:
			data = renderer.frame_payload()

		self.assertNotIn("annotations", data)
		self.assertNotIn("Make it bigger", json.dumps(data))
		self.assertEqual(utils.credential_keys(data), [])

	def test_a_guest_carries_neither(self):
		annotations.save(self.doc.name, body(), 0)
		shell = self.shell("Guest")

		self.assertIsNone(shell["annotations"])
		self.assertEqual((shell["annotations_epoch"], shell["csrf_token"]), (0, ""))

	def test_a_check_request_carries_neither(self):
		annotations.save(self.doc.name, body(), 0)
		with self.renderer(self.user, **signature.mint(self.doc.name, ttl_seconds=600)) as renderer:
			self.assertEqual(renderer.mode, "check")
			data = renderer.frame_payload()

		self.assertNotIn("annotations", data)
		self.assertEqual(utils.credential_keys(data), [])


class TestAnnotationTools(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_runtime()
		cls.owner = utils.make_user("anntool", "d2tanntool")
		cls.addClassCleanup(utils.drop_user, cls.owner)
		cls.stranger = utils.make_user("annstranger", "d2tannstranger")
		cls.addClassCleanup(utils.drop_user, cls.stranger)

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self.doc = utils.make_prototype(self.owner, "d2t-anntool", files=FILES)
		self.addCleanup(utils.drop_prototype, self.doc.name)
		self.addCleanup(frappe.set_user, "Administrator")
		annotations.save(self.doc.name, body(notes=[NOTE, {**NOTE, "id": "n2"}]), 0)
		frappe.set_user(self.owner)

	def call(self, name, **arguments):
		return tools.call_tool(name, {"prototype": self.doc.slug, **arguments})

	def test_get_is_read_only_and_returns_the_rows(self):
		self.assertIn("get_annotations", tools.READ_ONLY)
		self.assertNotIn("clear_annotations", tools.READ_ONLY)
		reply = self.call("get_annotations")
		self.assertFalse(reply["isError"], reply)
		result = reply["structuredContent"]
		self.assertEqual([n["id"] for n in result["notes"]], ["n1", "n2"])
		self.assertEqual(result["prompt"], "do it")

	def test_a_prototype_with_none_returns_empty_lists(self):
		frappe.set_user("Administrator")
		other = utils.make_prototype(self.owner, "d2t-anntool-empty", files=FILES)
		self.addCleanup(utils.drop_prototype, other.name)
		frappe.set_user(self.owner)
		result = tools.call_tool("get_annotations", {"prototype": other.slug})["structuredContent"]
		self.assertEqual((result["notes"], result["tweaks"]), ([], []))

	def test_another_users_prototype_is_refused(self):
		frappe.set_user(self.stranger)
		for name in ("get_annotations", "clear_annotations"):
			with self.subTest(tool=name):
				self.assertTrue(self.call(name)["isError"])

	def test_clear_by_ids_removes_those_and_names_a_tweak_by_group(self):
		before = prototype_files.revision(self.doc.name)
		reply = self.call("clear_annotations", ids=["n1", "g1"])
		self.assertFalse(reply["isError"], reply)
		self.assertEqual(reply["structuredContent"], {"removed_notes": 1, "removed_tweaks": 1})
		left = self.call("get_annotations")["structuredContent"]
		self.assertEqual(([n["id"] for n in left["notes"]], left["tweaks"]), (["n2"], []))
		self.assertNotEqual(before, prototype_files.revision(self.doc.name), "the open page must reload")

	def test_clear_with_an_empty_list_removes_nothing(self):
		reply = self.call("clear_annotations", ids=[])
		self.assertEqual(reply["structuredContent"], {"removed_notes": 0, "removed_tweaks": 0})
		self.assertEqual(len(self.call("get_annotations")["structuredContent"]["notes"]), 2)

	def test_clear_without_ids_removes_everything(self):
		self.call("clear_annotations")
		left = self.call("get_annotations")["structuredContent"]
		self.assertEqual((left["notes"], left["tweaks"], left["prompt"]), ([], [], ""))

	def test_clearing_nothing_does_not_reload_the_page(self):
		self.call("clear_annotations")
		settled = prototype_files.revision(self.doc.name)
		self.call("clear_annotations")
		self.assertEqual(settled, prototype_files.revision(self.doc.name))
