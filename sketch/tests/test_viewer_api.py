# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The shell's session API: who is asking comes from the session, never from the page.

The rules this file holds:

- Every method is POST only, never open to a Guest, and a Guest who calls one anyway gets 403.
- A private Prototype answers 404 to anyone not invited, a removed editor included.
- On a public Prototype a signed-in reader comments; they never edit, delete or write notes.
- The owner writes the owner's notes, an editor their own; nobody else writes any.
- The owner deletes any variant, an editor their own; Make default and Keep only this stay the owner's.
- The owner's variant writes answer with what changed, so the shell's toast states the server's answer.
- A POST that carries the session but not its CSRF token is refused.
"""

import json
from threading import Thread
from unittest.mock import patch

import frappe
from frappe.sessions import delete_session
from frappe.tests import IntegrationTestCase, set_user

from sketch import annotations, api, comments, prototype_files, sharing, versions, viewer_api
from sketch.mcp import tools
from sketch.tests import utils

HOME = """<script setup>
import { Variants } from 'sketch:variants'
</script>

<template>
  <Variants name="KPI strip">
    <template #wide><p>Wide</p></template>
    <template #tall><p>Tall</p></template>
  </Variants>
</template>
"""

FILES = {
	"src/App.vue": "<template><RouterView /></template>\n",
	"src/router.ts": "export default []\n",
	"src/pages/Home.vue": HOME,
}

COMPACT = '<variant set="KPI strip" name="Compact" />\n<template><p>Compact</p></template>\n'
DENSE = '<variant set="KPI strip" name="Dense" />\n<template><p>Dense</p></template>\n'

ANCHOR = json.dumps(
	{
		"route": "/",
		"viewport": "1280x800",
		"selector": "#kpi",
		"component": "Home",
		"componentChain": ["App", "Home"],
		"element": "KPI card",
		"text": "Revenue",
		"offset": {"x": 0.5, "y": 0.25},
		"rect": {"x": 10, "y": 20, "w": 100, "h": 40},
	}
)

NOTES = json.dumps(
	{"notes": [{"id": "n1", "route": "/", "note": "Bigger", "offset": {"x": 0, "y": 0}, "rect": {}}]}
)

#: Every method, with arguments that would reach its body. A refusal must come before any of them is read.
CALLS = {
	"delete_variant": {"option": "@d2tvaed/compact"},
	"undo_delete_variant": {"option": "@d2tvaed/compact", "sequence": "1"},
	"save_annotations": {"data": NOTES, "epoch": "0"},
	"comments_list": {},
	"comment_add": {"anchor": ANCHOR, "text": "Hi"},
	"comment_reply": {"thread": "x", "text": "Hi"},
	"comment_edit": {"comment": "x", "text": "Hi"},
	"comment_delete": {"comment": "x"},
	"comment_restore": {"comment": "x"},
	"comment_resolve": {"thread": "x"},
	"comments_delete_resolved": {},
	"comment_note_draft": {"comment": "x"},
	"seen_mark": {"variants": "[]", "threads": "[]"},
	"dismiss_moved_notice": {},
}


class ViewerApiCase(IntegrationTestCase):
	"""An owner, two editors, a reader who was never invited, and a Prototype with one set."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_runtime()
		cls.owner = utils.make_user("vaown", "d2tvaown")
		cls.addClassCleanup(utils.drop_user, cls.owner)
		cls.ed = utils.make_user("vaed", "d2tvaed")
		cls.addClassCleanup(utils.drop_user, cls.ed)
		cls.ed2 = utils.make_user("vaedtwo", "d2tvaedtwo")
		cls.addClassCleanup(utils.drop_user, cls.ed2)
		cls.reader = utils.make_user("vard", "d2tvard")
		cls.addClassCleanup(utils.drop_user, cls.reader)

	def setUp(self):
		super().setUp()
		self.doc = utils.make_prototype(self.owner, "d2t-viewer-api", files=FILES)
		self.addCleanup(utils.drop_prototype, self.doc.name)

	# -- helpers

	def call(self, user, method, **fields):
		with set_user(user):
			return getattr(viewer_api, method)(self.doc.name, **fields)

	def invite(self, user):
		with set_user(self.owner):
			api.invite_editor(self.doc.slug, utils.username_of(user))

	def remove(self, user):
		with set_user(self.owner):
			api.remove_editor(self.doc.slug, utils.username_of(user))

	def go_public(self):
		frappe.db.set_value("Sketch Prototype", self.doc.name, "is_public", 1)

	def add_variant(self, user, name="compact.vue", content=COMPACT) -> str:
		"""An invited editor's agent writes and commits one variant. Returns its option value."""
		self.invite(user)
		folder = sharing.folder(utils.username_of(user))
		with set_user(user):
			ref = f"d2tvaown/{self.doc.slug}"
			for tool, args in (
				("write_files", {"files": [{"path": folder + name, "content": content}]}),
				("commit", {"prompt": "Add a variant"}),
			):
				reply = tools.call_tool(tool, {"prototype": ref, **args})
				self.assertFalse(reply["isError"], reply["content"][0]["text"])

		return f"@{utils.username_of(user)}/{name.removesuffix('.vue')}"

	def tree(self) -> dict:
		return prototype_files.read_tree(self.doc.name)

	def assert_every_method_refused(self, user, error):
		for method, fields in CALLS.items():
			with self.subTest(method=method), self.assertRaises(error):
				self.call(user, method, **fields)


class TestTheDoor(ViewerApiCase):
	def test_every_method_is_post_only_and_closed_to_guests(self):
		for method in CALLS:
			fn = getattr(viewer_api, method)
			with self.subTest(method=method):
				self.assertIn(fn, frappe.whitelisted)
				self.assertNotIn(fn, frappe.guest_methods)
				self.assertEqual(list(frappe.allowed_http_methods_for_whitelisted_func[fn]), ["POST"])

	def test_a_guest_gets_403_even_on_a_public_prototype(self):
		self.assert_every_method_refused("Guest", frappe.PermissionError)
		self.go_public()
		self.assert_every_method_refused("Guest", frappe.PermissionError)

	def test_someone_not_invited_to_a_private_prototype_gets_404(self):
		self.assert_every_method_refused(self.reader, frappe.DoesNotExistError)

	def test_a_removed_editor_of_a_private_prototype_gets_404(self):
		self.add_variant(self.ed)
		self.remove(self.ed)
		self.assert_every_method_refused(self.ed, frappe.DoesNotExistError)
		self.assertIn("src/variants/@d2tvaed/compact.vue", self.tree())

	def test_a_missing_prototype_is_a_404(self):
		with set_user(self.owner), self.assertRaises(frappe.DoesNotExistError):
			viewer_api.comments_list("no-such-prototype")


class TestVariants(ViewerApiCase):
	def test_an_editor_deletes_their_own_and_undoes_it(self):
		option = self.add_variant(self.ed)
		done = self.call(self.ed, "delete_variant", option=option)
		self.assertEqual(
			{k: done[k] for k in ("file", "set", "option", "label")},
			{
				"file": "src/variants/@d2tvaed/compact.vue",
				"set": "KPI strip",
				"option": option,
				"label": "Compact",
			},
		)
		self.assertNotIn("src/variants/@d2tvaed/compact.vue", self.tree())

		back = self.call(self.ed, "undo_delete_variant", option=option, sequence=str(done["sequence"]))
		self.assertEqual((back["file"], back["set"], back["label"]), (done["file"], "KPI strip", "Compact"))
		self.assertTrue(back["sequence"])
		self.assertEqual(self.tree()["src/variants/@d2tvaed/compact.vue"], COMPACT)

	def test_an_editor_cannot_delete_another_editors_or_undo_the_owners(self):
		theirs = self.add_variant(self.ed2, "dense.vue", DENSE)
		mine = self.add_variant(self.ed)
		with self.assertRaises(frappe.PermissionError):
			self.call(self.ed, "delete_variant", option=theirs)
		self.assertIn("src/variants/@d2tvaedtwo/dense.vue", self.tree())

		done = self.call(self.owner, "delete_variant", option=mine)
		with self.assertRaises(frappe.PermissionError):
			self.call(self.ed, "undo_delete_variant", option=mine, sequence=str(done["sequence"]))

		self.call(self.owner, "undo_delete_variant", option=mine, sequence=str(done["sequence"]))
		self.assertIn("src/variants/@d2tvaed/compact.vue", self.tree())

	def test_the_owner_deletes_any_editors_variant(self):
		option = self.add_variant(self.ed2, "dense.vue", DENSE)
		done = self.call(self.owner, "delete_variant", option=option)
		self.assertEqual(done["label"], "Dense")
		self.assertNotIn("src/variants/@d2tvaedtwo/dense.vue", self.tree())

	def test_a_reader_and_a_removed_editor_delete_nothing_on_a_public_prototype(self):
		option = self.add_variant(self.ed)
		self.go_public()
		with self.assertRaises(frappe.PermissionError):
			self.call(self.reader, "delete_variant", option=option)

		self.remove(self.ed)
		with self.assertRaises(frappe.PermissionError):
			self.call(self.ed, "delete_variant", option=option)

		self.assertIn("src/variants/@d2tvaed/compact.vue", self.tree())

	def test_an_editor_cannot_make_default_or_keep_only(self):
		option = self.add_variant(self.ed)
		file = "src/pages/Home.vue"
		with set_user(self.ed):
			for call in (
				lambda: api.set_variant_default(self.doc.slug, file, "KPI strip", "tall"),
				lambda: api.set_variant_default(self.doc.slug, file, "KPI strip", option),
				lambda: api.keep_variant(self.doc.slug, file, "KPI strip", "tall"),
				lambda: api.undo_variant_default(self.doc.slug, file, 1, "KPI strip", "tall"),
				lambda: api.undo_keep_variant(self.doc.slug, file, 1, "KPI strip", "tall"),
			):
				with self.assertRaises(frappe.DoesNotExistError):
					call()

		self.assertEqual(self.tree()[file], HOME)

	def test_the_owners_variant_writes_say_what_changed(self):
		file = "src/pages/Home.vue"
		with set_user(self.owner):
			versions.record_created(self.doc, "Created")
			made = api.set_variant_default(self.doc.slug, file, "KPI strip", "tall")
			self.assertEqual(
				{k: made[k] for k in ("file", "set", "option", "label", "name")},
				{"file": file, "set": "KPI strip", "option": "tall", "label": "Tall", "name": "KPI strip"},
			)
			undone = api.undo_variant_default(self.doc.slug, file, made["sequence"], "KPI strip", "tall")
			self.assertEqual(
				(undone["file"], undone["set"], undone["option"], undone["label"]),
				(file, "KPI strip", "tall", "Tall"),
			)
			self.assertTrue(undone["sequence"])

			kept = api.keep_variant(self.doc.slug, file, "KPI strip", "wide")
			self.assertEqual(
				(kept["file"], kept["set"], kept["option"], kept["label"]),
				(file, "KPI strip", "wide", "Wide"),
			)
			self.assertEqual(kept["removed"], 1)
			back = api.undo_keep_variant(self.doc.slug, file, kept["sequence"], "KPI strip", "wide")
			self.assertEqual(
				(back["file"], back["set"], back["option"], back["label"]),
				(file, "KPI strip", "wide", "Wide"),
			)

		self.assertEqual(self.tree()[file], HOME)

	def test_making_an_editors_option_the_default_names_it(self):
		option = self.add_variant(self.ed)
		with set_user(self.owner):
			made = api.set_variant_default(self.doc.slug, "src/pages/Home.vue", "KPI strip", option)
		self.assertEqual((made["set"], made["label"]), ("KPI strip", "Compact"))


class TestNotes(ViewerApiCase):
	def test_the_owner_writes_the_owners_notes_and_an_editor_their_own(self):
		self.invite(self.ed)
		self.call(self.owner, "save_annotations", data=NOTES, epoch=str(annotations.epoch(self.doc.name)))
		self.assertEqual(annotations.read(self.doc.name)["notes"][0]["note"], "Bigger")
		self.assertEqual(annotations.read(self.doc.name, editor=self.ed)["notes"], [])

		theirs = json.dumps(
			{"notes": [{"id": "e1", "route": "/", "note": "Mine", "offset": {"x": 0, "y": 0}, "rect": {}}]}
		)
		self.call(
			self.ed, "save_annotations", data=theirs, epoch=str(annotations.epoch(self.doc.name, self.ed))
		)
		self.assertEqual(annotations.read(self.doc.name, editor=self.ed)["notes"][0]["note"], "Mine")
		self.assertEqual(annotations.read(self.doc.name)["notes"][0]["note"], "Bigger")

	def test_a_reader_and_a_removed_editor_write_no_notes(self):
		self.invite(self.ed)
		self.go_public()
		with self.assertRaises(frappe.DoesNotExistError):
			self.call(self.reader, "save_annotations", data=NOTES, epoch="0")

		self.remove(self.ed)
		with self.assertRaises(frappe.DoesNotExistError):
			self.call(self.ed, "save_annotations", data=NOTES, epoch="0")

		self.assertEqual(annotations.read(self.doc.name)["notes"], [])

	def test_the_cap_the_shape_and_the_epoch_still_hold(self):
		huge = json.dumps({"notes": [{"id": "x", "pad": "a" * annotations.MAX_BYTES}]})
		with self.assertRaises(annotations.AnnotationsTooLarge):
			self.call(self.owner, "save_annotations", data=huge, epoch="0")

		with self.assertRaises(frappe.ValidationError):
			self.call(self.owner, "save_annotations", data="not json", epoch="0")

		self.call(self.owner, "save_annotations", data=NOTES, epoch=str(annotations.epoch(self.doc.name)))
		annotations.clear(self.doc.name)
		with self.assertRaises(annotations.AnnotationsStale) as caught:
			self.call(self.owner, "save_annotations", data=NOTES, epoch="0")
		self.assertEqual(caught.exception.http_status_code, 409)


class TestComments(ViewerApiCase):
	def test_a_reader_comments_on_a_public_prototype(self):
		self.go_public()
		thread = self.call(self.reader, "comment_add", anchor=ANCHOR, text="Looks off")
		tid = thread["id"]
		listed = self.call(self.reader, "comments_list")
		self.assertEqual(listed["me"], "d2tvard")
		self.assertFalse(listed["is_owner"])
		self.assertEqual([t["id"] for t in listed["threads"]], [tid])

		self.call(self.owner, "comment_reply", thread=tid, text="Fixed")
		self.call(self.reader, "comment_edit", comment=tid, text="Looks off, still")
		self.call(self.reader, "comment_resolve", thread=tid, resolved="1")
		self.assertEqual(self.call(self.reader, "seen_mark", threads=json.dumps([tid]))["marked"], 1)

		with self.assertRaises(frappe.PermissionError):
			self.call(self.reader, "comments_delete_resolved")
		with self.assertRaises(frappe.PermissionError):
			self.call(self.reader, "comment_note_draft", comment=tid)

		self.assertIsNone(self.call(self.reader, "comment_delete", comment=tid))
		self.assertEqual(self.call(self.reader, "comment_restore", comment=tid)["id"], tid)

	def test_a_reader_cannot_touch_someone_elses_comment(self):
		self.go_public()
		thread = self.call(self.owner, "comment_add", anchor=ANCHOR, text="Mine")
		for method, fields in (
			("comment_edit", {"comment": thread["id"], "text": "Theirs"}),
			("comment_delete", {"comment": thread["id"]}),
			("comment_resolve", {"thread": thread["id"]}),
		):
			with self.subTest(method=method), self.assertRaises(frappe.PermissionError):
				self.call(self.reader, method, **fields)

	def test_the_owner_drafts_a_note_and_deletes_resolved(self):
		self.invite(self.ed)
		thread = self.call(self.ed, "comment_add", anchor=ANCHOR, text="Try @[d2tvaown]")
		listed = self.call(self.owner, "comments_list")
		self.assertTrue(listed["is_owner"])
		self.assertIn("d2tvaed", [p["username"] for p in listed["mentionable"]])

		draft = self.call(self.owner, "comment_note_draft", comment=thread["id"])
		self.assertIn("Try", draft["note"])
		self.assertEqual(annotations.read(self.doc.name)["notes"], [], "a draft saves nothing")

		self.call(self.ed, "comment_resolve", thread=thread["id"])
		self.assertEqual(self.call(self.owner, "comments_delete_resolved", also="not json")["deleted"], 1)
		self.assertEqual(self.call(self.owner, "comments_list")["threads"], [])

	def test_a_removed_editor_still_comments_on_a_public_prototype_as_a_reader(self):
		self.invite(self.ed)
		self.go_public()
		self.remove(self.ed)
		self.assertTrue(self.call(self.ed, "comment_add", anchor=ANCHOR, text="Still here")["id"])

	def test_a_comment_made_private_closes_the_door_at_once(self):
		self.go_public()
		self.call(self.reader, "comment_add", anchor=ANCHOR, text="Hi")
		frappe.db.set_value("Sketch Prototype", self.doc.name, "is_public", 0)
		with self.assertRaises(frappe.DoesNotExistError):
			self.call(self.reader, "comments_list")

	def test_comments_are_never_notes(self):
		self.go_public()
		self.call(self.reader, "comment_add", anchor=ANCHOR, text="Hi")
		self.assertEqual(annotations.read(self.doc.name)["notes"], [])
		self.assertEqual(len(frappe.get_all(comments.COMMENT, filters={"prototype": self.doc.name})), 1)


# ------------------------------------------------------------------ over HTTP


#: The `frappe.local` names `LoginManager` writes over, put back after a session is opened.
BORROWED_LOCALS = (
	"request",
	"cookie_manager",
	"login_manager",
	"session",
	"session_obj",
	"form_dict",
	"response",
)


def open_session(user: str) -> tuple[str, str]:
	"""A real session for `user`, with a CSRF token. Returns (sid, token). See test_mcp_token_only.open_session."""
	from frappe.auth import CookieManager, LoginManager

	borrowed = {name: getattr(frappe.local, name, None) for name in BORROWED_LOCALS}
	try:
		frappe.utils.set_request(path="/")
		frappe.local.form_dict = frappe._dict()
		frappe.local.cookie_manager = CookieManager()
		frappe.local.login_manager = LoginManager()
		frappe.local.login_manager.login_as(user)
		token = frappe.generate_hash()
		frappe.local.session.data.csrf_token = token
		frappe.local.session_obj.update(force=True)
		sid = frappe.session.sid
	finally:
		for name, value in borrowed.items():
			setattr(frappe.local, name, value)

	frappe.db.commit()
	return sid, token


def post(path: str, data: dict, headers: dict) -> int:
	"""One POST through Frappe's own WSGI app, in a thread of its own as a web worker is. Returns the status."""
	site = frappe.local.site
	answer = {}

	def run():
		with patch("frappe.app.get_site_name", return_value=site):
			response = frappe.utils.get_test_client(use_cookies=False).post(path, data=data, headers=headers)
			try:
				response.get_data()
			finally:
				response.close()
			answer["status"] = response.status_code

	worker = Thread(target=run)
	worker.start()
	worker.join()
	return answer["status"]


class TestCsrf(ViewerApiCase):
	def test_a_session_without_its_csrf_token_is_refused(self):
		self.go_public()
		frappe.db.commit()  # the request runs on its own connection
		sid, token = open_session(self.owner)
		self.addCleanup(delete_session, sid)
		path = "/api/method/sketch.viewer_api.comments_list"
		form = {"name": self.doc.name}

		self.assertEqual(post(path, form, {"Cookie": f"sid={sid}"}), 400)
		self.assertEqual(post(path, form, {"Cookie": f"sid={sid}", "X-Frappe-CSRF-Token": "wrong"}), 400)
		self.assertEqual(post(path, form, {"Cookie": f"sid={sid}", "X-Frappe-CSRF-Token": token}), 200)
		self.assertEqual(post(path, form, {}), 403, "no session is a Guest")
