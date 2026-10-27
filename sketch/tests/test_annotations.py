# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The owner's notes and tweaks: the save door, the payload, and the agent's tools.

The Viewer toolbar writes through `sketch.api.save_annotations`, which a Guest
reaches with a signature and nothing else. The agent reads and clears the same
rows over MCP. Each case drives the method directly, as the signature tests do.
"""

import json
import time

import frappe
from frappe.tests import IntegrationTestCase, set_user

from sketch import annotations, api, prototype_files, signature
from sketch.mcp import tools
from sketch.tests import utils
from sketch.viewer import LIVE_TTL_SECONDS, SketchViewerRenderer

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
		cls.doc = utils.make_prototype(cls.user, "d2t-annsave", files=FILES)
		cls.addClassCleanup(utils.drop_prototype, cls.doc.name)
		cls.other = utils.make_prototype(cls.user, "d2t-annsave-two", files=FILES)
		cls.addClassCleanup(utils.drop_prototype, cls.other.name)

	def stamp(self, name=None, ttl_seconds=600, scope=signature.ANNOTATE) -> dict:
		return signature.mint(name or self.doc.name, ttl_seconds=ttl_seconds, scope=scope)

	def save(self, data: str, mark: dict | None = None, name: str | None = None, epoch: str | None = None) -> dict:
		"""A save from a page that loaded now, unless `epoch` says otherwise."""
		name = name or self.doc.name
		mark = mark or self.stamp(name)
		if epoch is None:
			epoch = str(annotations.epoch(name))

		with set_user("Guest"):
			return api.save_annotations(name, str(mark["exp"]), mark["sig"], data, epoch)

	def test_a_good_save_is_stored_and_read_back(self):
		self.save(body(anchor="top-left"))
		saved = annotations.read(self.doc.name)
		self.assertEqual(saved["notes"], [NOTE])
		self.assertEqual(saved["tweaks"], [TWEAK])
		self.assertEqual(saved["prompt"], "do it")
		self.assertEqual(saved["anchor"], "top-left")
		self.assertTrue(saved["updated"], "the server stamps the time")

	def test_the_answer_is_readable_from_an_opaque_origin(self):
		self.save(body())
		self.assertEqual(frappe.local.response_headers["Access-Control-Allow-Origin"], "*")

	def test_angle_brackets_survive_the_http_door(self):
		"""Notes name components ("<Badge>"); a Guest's form data must reach the field as sent."""
		utils.require_webserver()
		note = {**NOTE, "note": "Use <Badge> here & keep <b>bold</b>"}
		mark = self.stamp()
		form = {
			"name": self.doc.name,
			"exp": str(mark["exp"]),
			"sig": mark["sig"],
			"data": json.dumps({"notes": [note], "tweaks": []}),
			"epoch": str(annotations.epoch(self.doc.name)),
		}
		frappe.db.commit()  # the web server reads this Prototype through its own connection
		response = utils.request("POST", "/api/method/sketch.api.save_annotations", data=form)
		self.assertEqual(response.status_code, 200, response.text)
		frappe.db.rollback()
		self.assertEqual(annotations.read(self.doc.name)["notes"][0]["note"], note["note"])

	def test_unknown_keys_are_dropped(self):
		self.save(body(extra="x", updated="1999"))
		saved = annotations.read(self.doc.name)
		self.assertNotIn("extra", saved)
		self.assertNotEqual(saved["updated"], "1999")

	def test_a_revision_signature_is_a_404(self):
		mark = self.stamp(scope=signature.REVISION)
		with self.assertRaises(frappe.DoesNotExistError):
			self.save(body(), mark)

	def test_an_expired_signature_is_a_404(self):
		with self.assertRaises(frappe.DoesNotExistError):
			self.save(body(), self.stamp(ttl_seconds=-60))

	def test_another_prototypes_signature_is_a_404(self):
		with self.assertRaises(frappe.DoesNotExistError):
			self.save(body(), self.stamp(self.other.name))

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
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_runtime()
		cls.user = utils.make_user("annpay", "d2tannpay")
		cls.addClassCleanup(utils.drop_user, cls.user)
		cls.username = utils.username_of(cls.user)
		cls.doc = utils.make_prototype(cls.user, "d2t-annpay", files=FILES, is_public=True)
		cls.addClassCleanup(utils.drop_prototype, cls.doc.name)

	def payload(self) -> dict:
		renderer = SketchViewerRenderer(path=f"u/{self.username}/{self.doc.slug}")
		self.assertTrue(renderer.can_render())
		return renderer.payload()

	def test_the_owners_page_carries_annotations_and_the_signature(self):
		annotations.save(self.doc.name, body(), 0)
		with set_user(self.user):
			payload = self.payload()

		self.assertEqual(payload["annotations"]["notes"], [NOTE])
		self.assertEqual(payload["annotations_epoch"], 0)
		self.assertTrue(
			signature.verify(self.doc.name, payload["annotate_exp"], payload["annotate_sig"], signature.ANNOTATE)
		)
		self.assertGreater(int(payload["annotate_exp"]) - int(time.time()), LIVE_TTL_SECONDS - 60)

	def test_the_annotate_signature_opens_nothing_else(self):
		with set_user(self.user):
			payload = self.payload()

		for scope in (signature.VIEW, signature.REVISION):
			self.assertFalse(
				signature.verify(self.doc.name, payload["annotate_exp"], payload["annotate_sig"], scope)
			)

	def test_a_guest_carries_neither(self):
		with set_user("Guest"):
			payload = self.payload()

		self.assertIsNone(payload["annotations"])
		self.assertEqual((payload["annotate_exp"], payload["annotate_sig"]), ("", ""))

	def test_a_check_request_carries_neither(self):
		with set_user(self.user):
			mark = signature.mint(self.doc.name, ttl_seconds=600)
			frappe.form_dict.update({"exp": mark["exp"], "sig": mark["sig"]})
			payload = self.payload()

		self.assertIsNone(payload["annotations"])
		self.assertEqual(payload["annotate_sig"], "")


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


class TestReaderComments(IntegrationTestCase):
	"""Signed-in readers leave their own notes on somebody else's public Prototype."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_runtime()
		cls.owner = utils.make_user("annowner", "d2tannowner")
		cls.addClassCleanup(utils.drop_user, cls.owner)
		cls.reader = utils.make_user("annreader", "d2tannreader")
		cls.addClassCleanup(utils.drop_user, cls.reader)
		cls.other_reader = utils.make_user("annreader2", "d2tannreadertwo")
		cls.addClassCleanup(utils.drop_user, cls.other_reader)
		cls.owner_name = utils.username_of(cls.owner)

	def setUp(self):
		super().setUp()
		self.doc = utils.make_prototype(self.owner, "d2t-anncomment", files=FILES, is_public=True)
		self.addCleanup(utils.drop_prototype, self.doc.name)

	def comment(self, username: str, notes: list, mark: dict | None = None, epoch: str | None = None) -> dict:
		subject = annotations.comment_subject(self.doc.name, username)
		mark = mark or signature.mint(subject, ttl_seconds=600, scope=signature.COMMENT)
		if epoch is None:
			epoch = str(annotations.epoch(self.doc.name))

		with set_user("Guest"):
			return api.save_comments(
				self.doc.name, username, str(mark["exp"]), mark["sig"], json.dumps({"notes": notes}), epoch
			)

	def notes(self) -> list[dict]:
		return annotations.read(self.doc.name)["notes"]

	def payload(self) -> dict:
		renderer = SketchViewerRenderer(path=f"u/{self.owner_name}/{self.doc.slug}")
		self.assertTrue(renderer.can_render())
		return renderer.payload()

	def test_a_readers_note_is_stamped_with_their_username(self):
		self.comment("d2tannreader", [{**NOTE, "author": "someone-else", "sent": True}])
		self.assertEqual(self.notes(), [{**NOTE, "author": "d2tannreader"}])

	def test_a_reader_never_touches_anybody_elses_row(self):
		annotations.save(self.doc.name, body(), 0)
		self.comment("d2tannreadertwo", [{**NOTE, "id": "r2"}])
		hijack = [{**NOTE, "id": "n1", "note": "hijack"}, {**NOTE, "id": "r2", "note": "hijack"}]
		self.comment("d2tannreader", hijack)
		authors = {n["id"]: n.get("author") for n in self.notes()}
		self.assertEqual(authors, {"n1": None, "r2": "d2tannreadertwo"})
		self.assertNotIn("hijack", [n["note"] for n in self.notes()])

	def test_a_reader_replaces_only_their_own_rows(self):
		self.comment("d2tannreader", [{**NOTE, "id": "a"}, {**NOTE, "id": "b"}])
		self.comment("d2tannreadertwo", [{**NOTE, "id": "c"}])
		self.comment("d2tannreader", [{**NOTE, "id": "b"}])
		self.assertEqual(sorted(n["id"] for n in self.notes()), ["b", "c"])

	def test_the_owner_keeps_new_reader_rows_and_deletes_known_ones(self):
		self.comment("d2tannreader", [{**NOTE, "id": "r1"}, {**NOTE, "id": "r2"}])
		# The owner's page loaded with r1 and r2, deleted r1, and marked r2 sent.
		self.comment("d2tannreadertwo", [{**NOTE, "id": "r3"}])
		sent = [NOTE, {**NOTE, "id": "r2", "note": "edited by owner", "sent": True}]
		annotations.save(self.doc.name, body(notes=sent, known=["r1", "r2"]), 0)
		rows = {n["id"]: n for n in self.notes()}
		self.assertEqual(sorted(rows), ["n1", "r2", "r3"], "r3 came after the owner's page loaded")
		self.assertEqual(rows["r2"]["note"], NOTE["note"], "the owner cannot edit a reader's words")
		self.assertTrue(rows["r2"]["sent"])

	def test_the_owner_cannot_sign_as_a_reader(self):
		annotations.save(self.doc.name, body(notes=[{**NOTE, "author": "d2tannreader"}]), 0)
		self.assertNotIn("author", self.notes()[0])

	def test_the_signature_speaks_for_one_reader(self):
		subject = annotations.comment_subject(self.doc.name, "d2tannreader")
		mark = signature.mint(subject, ttl_seconds=600, scope=signature.COMMENT)
		with self.assertRaises(frappe.DoesNotExistError):
			self.comment("d2tannreadertwo", [NOTE], mark=mark)

		annotate = signature.mint(self.doc.name, ttl_seconds=600, scope=signature.ANNOTATE)
		with self.assertRaises(frappe.DoesNotExistError):
			self.comment("d2tannreader", [NOTE], mark=annotate)

	def test_a_private_prototype_takes_no_comments(self):
		frappe.db.set_value("Sketch Prototype", self.doc.name, "is_public", 0)
		with self.assertRaises(frappe.DoesNotExistError):
			self.comment("d2tannreader", [NOTE])

	def test_a_reader_page_from_before_a_clear_is_409(self):
		self.comment("d2tannreader", [NOTE])
		annotations.clear(self.doc.name)
		with self.assertRaises(annotations.AnnotationsStale):
			self.comment("d2tannreader", [NOTE], epoch="0")

	def test_a_reader_keeps_a_bounded_number_of_notes(self):
		rows = [{**NOTE, "id": f"x{i}"} for i in range(annotations.MAX_COMMENTS + 1)]
		with self.assertRaises(annotations.AnnotationsTooLarge):
			self.comment("d2tannreader", rows)

	def test_a_readers_page_carries_every_note_and_their_signature(self):
		annotations.save(self.doc.name, body(), 0)
		with set_user(self.reader):
			payload = self.payload()

		self.assertEqual(payload["commenter"], "d2tannreader")
		self.assertEqual(payload["annotations"], {"notes": [NOTE]}, "no tweaks, no prompt")
		self.assertEqual(payload["annotate_sig"], "", "a reader never gets the owner's door")
		subject = annotations.comment_subject(self.doc.name, "d2tannreader")
		self.assertTrue(
			signature.verify(subject, payload["comment_exp"], payload["comment_sig"], signature.COMMENT)
		)

	def test_the_owner_a_guest_and_a_private_page_carry_no_comment_door(self):
		with set_user(self.owner):
			self.assertEqual(self.payload()["commenter"], "")

		with set_user("Guest"):
			payload = self.payload()
			self.assertEqual((payload["commenter"], payload["comment_sig"]), ("", ""))

		frappe.db.set_value("Sketch Prototype", self.doc.name, "is_public", 0)
		with set_user(self.reader):
			renderer = SketchViewerRenderer(path=f"u/{self.owner_name}/{self.doc.slug}")
			self.assertFalse(renderer.can_render())
