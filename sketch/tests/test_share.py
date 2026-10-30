# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""Sharing: the owner invites people by username, their agents add variants.

The rules this file holds:

- Invite by exact username only; the three refusals read as the dialog prints them.
- An editor writes under `src/variants/@<own username>/` and nowhere else.
- "Made by" is the folder the token could write, never a name in the file.
- An editor never changes the default or the owner's files. Their notes are their own, both ways.
- A private Prototype is for the owner and the invited. A removed editor is out at once,
  and their variants stay.
- A restore brings editors' variants back and never deletes one added since. An editor's commit carries their name.
"""

import json

import frappe
from frappe.tests import IntegrationTestCase, set_user

from sketch import annotations, api, comments, editor_variants, prototype, prototype_files, sharing, signature, versions
from sketch.mcp import tools
from sketch.tests import utils
from sketch.viewer import SketchViewerRenderer

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
	"src/components/KpiStrip.vue": "<template><div>strip</div></template>\n",
}

PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
COMPACT = '<variant set="KPI strip" name="Compact" />\n<template><p>Compact</p></template>\n'
WRAP = '<variant component="src/components/KpiStrip.vue" name="Dense" />\n<template><p>Dense</p></template>\n'


class ShareCase(IntegrationTestCase):
	"""An owner, an editor-to-be, a reader and a prototype with one set."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_runtime()
		cls.owner = utils.make_user("shown", "d2tshown")
		cls.addClassCleanup(utils.drop_user, cls.owner)
		cls.ed = utils.make_user("shed", "d2tshed")
		cls.addClassCleanup(utils.drop_user, cls.ed)
		cls.other = utils.make_user("shoth", "d2tshoth")
		cls.addClassCleanup(utils.drop_user, cls.other)
		cls.reader = utils.make_user("shrd", "d2tshrd")
		cls.addClassCleanup(utils.drop_user, cls.reader)

	def setUp(self):
		super().setUp()
		self.doc = utils.make_prototype(self.owner, "d2t-share", files=FILES)
		self.addCleanup(utils.drop_prototype, self.doc.name)
		self.folder = "src/variants/@d2tshed/"

	def invite(self, user=None):
		with set_user(self.owner):
			return api.invite_editor(self.doc.slug, utils.username_of(user or self.ed))

	def agent(self, user, tool, **args):
		"""One MCP tool call as `user`. Returns the whole reply."""
		with set_user(user):
			if tool not in ("list_prototypes", "list_runtimes", "get_skill"):
				args.setdefault("prototype", self.ref(user))
			return tools.call_tool(tool, args)

	def ref(self, user):
		return self.doc.slug if user == self.owner else f"{utils.username_of(self.owner)}/{self.doc.slug}"

	def ok(self, reply):
		self.assertFalse(reply["isError"], reply["content"][0]["text"])
		return reply

	def refused(self, reply):
		self.assertTrue(reply["isError"], reply["content"][0]["text"])
		return reply["content"][0]["text"]

	def tree(self):
		return prototype_files.read_tree(self.doc.name)

	def page_data_for(self, user):
		"""The data slot the Viewer would carry for this person."""
		renderer = SketchViewerRenderer(path=f"u/d2tshown/{self.doc.slug}")
		with set_user(user):
			self.assertTrue(renderer.can_render(), user)
			return renderer.payload()

	def edit_credential(self, user):
		stamp = signature.mint(comments.subject(self.doc.name, utils.username_of(user)), 600, signature.VARIANT_EDIT)
		return {"username": utils.username_of(user), "exp": str(stamp["exp"]), "sig": stamp["sig"]}

	def delete_as(self, user, option):
		with set_user("Guest"):
			return api.delete_variant_signed(self.doc.name, option=option, **self.edit_credential(user))

	def undo_delete_as(self, user, option, sequence):
		with set_user("Guest"):
			return api.undo_delete_variant_signed(
				self.doc.name, option=option, sequence=str(sequence), **self.edit_credential(user)
			)

	def add_variant(self, content=COMPACT, name="compact.vue", commit=True):
		self.invite()
		self.ok(self.agent(self.ed, "write_files", files=[{"path": self.folder + name, "content": content}]))
		if commit:
			self.ok(self.agent(self.ed, "commit", prompt="Add a compact KPI strip"))


class TestInvite(ShareCase):
	def test_the_owner_invites_by_exact_username_and_the_editor_is_listed(self):
		state = self.invite()
		self.assertEqual([e["username"] for e in state["editors"]], ["d2tshed"])
		self.assertEqual(state["owner"]["username"], "d2tshown")
		self.assertFalse(state["is_public"])
		self.assertTrue(state["public_url"].endswith("/u/d2tshown/d2t-share"))
		with set_user(self.owner):
			self.assertEqual(api.share_info(self.doc.slug)["editors"], state["editors"])

	def test_an_at_sign_and_capitals_still_name_the_person(self):
		with set_user(self.owner):
			state = api.invite_editor(self.doc.slug, " @D2TSHED ")
		self.assertEqual(len(state["editors"]), 1)

	def test_the_refusals_read_as_the_dialog_prints_them(self):
		with set_user(self.owner):
			with self.assertRaises(frappe.ValidationError) as unknown:
				api.invite_editor(self.doc.slug, "xyz")
			self.assertIn("No Sketch user called “xyz”", str(unknown.exception))
			with self.assertRaises(frappe.ValidationError) as me:
				api.invite_editor(self.doc.slug, "d2tshown")
			self.assertIn("That's you", str(me.exception))
			api.invite_editor(self.doc.slug, "d2tshed")
			with self.assertRaises(frappe.ValidationError) as twice:
				api.invite_editor(self.doc.slug, "d2tshed")
			self.assertIn("Sketch Test shed is already an editor", str(twice.exception))

	def test_a_part_of_a_username_names_nobody(self):
		with set_user(self.owner):
			for typed in ("d2tsh", "d2tshe", "d2t%", "%", "*"):
				with self.subTest(typed=typed), self.assertRaises(frappe.ValidationError):
					api.invite_editor(self.doc.slug, typed)

		self.assertEqual(sharing.editors(self.doc.name), [])

	def test_only_the_owner_shares(self):
		self.invite()
		for user in (self.ed, self.reader):
			with set_user(user):
				for call in (
					lambda: api.share_info(self.doc.slug),
					lambda: api.invite_editor(self.doc.slug, "d2tshrd"),
					lambda: api.remove_editor(self.doc.slug, "d2tshed"),
				):
					with self.subTest(user=user), self.assertRaises(frappe.DoesNotExistError):
						call()

	def test_remove_then_invite_again_is_undo(self):
		self.invite()
		with set_user(self.owner):
			gone = api.remove_editor(self.doc.slug, "d2tshed")
			self.assertEqual(gone["editors"], [])
			with self.assertRaises(frappe.DoesNotExistError):
				api.remove_editor(self.doc.slug, "d2tshed")
			back = api.invite_editor(self.doc.slug, "d2tshed")
		self.assertEqual([e["username"] for e in back["editors"]], ["d2tshed"])

	def test_twenty_editors_all_list(self):
		made = []
		for n in range(20):
			email = utils.make_user(f"shmany{n}", f"d2tshmany{n}")
			made.append(email)
			self.addCleanup(utils.drop_user, email)
			with set_user(self.owner):
				api.invite_editor(self.doc.slug, f"d2tshmany{n}")

		with set_user(self.owner):
			self.assertEqual(len(api.share_info(self.doc.slug)["editors"]), 20)

	def test_deleting_the_prototype_drops_its_invitations(self):
		self.invite()
		utils.drop_prototype(self.doc.name)
		self.assertEqual(frappe.db.count("Sketch Prototype Editor", {"prototype": self.doc.name}), 0)


class TestSharedWithMe(ShareCase):
	def test_an_editor_sees_it_with_the_owner_and_nobody_else_does(self):
		self.invite()
		with set_user(self.ed):
			rows = api.shared_prototypes()
		self.assertEqual([r["slug"] for r in rows], ["d2t-share"])
		self.assertEqual(rows[0]["owner"]["username"], "d2tshown")
		self.assertEqual(rows[0]["viewer_path"], "/u/d2tshown/d2t-share")
		for user in (self.reader, self.owner):
			with set_user(user):
				self.assertEqual(api.shared_prototypes(), [])

	def test_the_gallery_card_says_who_it_is_shared_with_and_a_shared_card_does_not(self):
		with set_user(self.owner):
			self.assertEqual(api.list_prototypes()[0]["editors"], [])

		self.invite()
		with set_user(self.owner):
			row = api.list_prototypes()[0]
		self.assertEqual([e["username"] for e in row["editors"]], ["d2tshed"])
		self.assertEqual(sorted(row["editors"][0]), ["full_name", "user_image", "username"], "no email goes out")
		with set_user(self.ed):
			self.assertEqual(api.shared_prototypes()[0]["editors"], [])

	def test_the_list_is_empty_for_a_user_nobody_invited(self):
		with set_user(self.reader):
			self.assertEqual(api.shared_prototypes(), [])

	def test_list_prototypes_for_an_editor_marks_the_role_and_the_owner(self):
		self.invite()
		mine = utils.make_prototype(self.ed, "d2t-share", files=FILES)
		self.addCleanup(utils.drop_prototype, mine.name)
		with set_user(self.ed):
			rows = tools.call_tool("list_prototypes", {})["structuredContent"]["prototypes"]

		by_slug = {r["slug"]: r for r in rows}
		self.assertEqual(by_slug["d2t-share"]["role"], "owner", "the editor's own, same slug")
		shared = by_slug["d2tshown/d2t-share"]
		self.assertEqual(shared["role"], "editor")
		self.assertEqual(shared["owner"]["username"], "d2tshown")
		self.assertEqual(shared["id"], self.doc.name)
		with set_user(self.owner):
			own = tools.call_tool("list_prototypes", {})["structuredContent"]["prototypes"]
		self.assertEqual([(r["slug"], r["role"]) for r in own], [("d2t-share", "owner")])


class TestWritePaths(ShareCase):
	def test_an_editor_writes_inside_their_folder(self):
		self.invite()
		self.ok(self.agent(self.ed, "write_files", files=[{"path": self.folder + "compact.vue", "content": COMPACT}]))
		self.assertEqual(self.tree()[self.folder + "compact.vue"], COMPACT)
		self.ok(
			self.agent(
				self.ed,
				"edit_file",
				path=self.folder + "compact.vue",
				old_string="Compact</p>",
				new_string="Compacter</p>",
			)
		)
		self.ok(self.agent(self.ed, "delete_file", path=self.folder + "compact.vue"))
		self.assertNotIn(self.folder + "compact.vue", self.tree())

	def test_an_editor_is_refused_everywhere_else(self):
		self.invite()
		before = self.tree()
		outside = (
			"src/App.vue",
			"src/pages/Home.vue",
			"src/variants/@d2tshown/x.vue",
			"src/variants/@d2tshoth/x.vue",
			"src/variants/@d2tshed/../../App.vue",
			"src/variants/@d2tshed/../@d2tshoth/x.vue",
			"src/variants/@d2tshedder/x.vue",
			"src/variants/@d2tshed",
			"src/variants/adopted/x.vue",
			"src/variants/adopted.json",
			"/etc/passwd",
			"src/variants/@d2tshed/x.css",
		)
		for path in outside:
			with self.subTest(path=path):
				self.refused(self.agent(self.ed, "write_files", files=[{"path": path, "content": COMPACT}]))

		self.refused(self.agent(self.ed, "edit_file", path="src/pages/Home.vue", old_string="Wide", new_string="x"))
		self.refused(
			self.agent(self.ed, "edit_files", edits=[{"path": "src/App.vue", "old_string": "Router", "new_string": "x"}])
		)
		self.refused(self.agent(self.ed, "delete_file", path="src/pages/Home.vue"))
		self.refused(
			self.agent(
				self.ed,
				"upload_asset",
				path="src/assets/logo.js",
				data_base64="iVBORw0KGgo=",
				mime_type="image/png",
			)
		)
		self.assertEqual(self.tree(), before, "not one byte of the owner's tree moved")

	def test_one_bad_path_in_a_batch_writes_none(self):
		self.invite()
		self.refused(
			self.agent(
				self.ed,
				"write_files",
				files=[
					{"path": self.folder + "good.vue", "content": COMPACT},
					{"path": "src/App.vue", "content": "x"},
				],
			)
		)
		self.assertNotIn(self.folder + "good.vue", self.tree())

	def test_a_variant_tag_that_cannot_work_is_refused_when_written(self):
		self.invite()
		for bad in (
			"<variant set='KPI strip' />",
			'<variant name="x" />',
			'<variant set="a" component="src/components/A.vue" name="x" />',
			'<variant component="components/A.vue" name="x" />',
			f'<variant set="a" name="{"x" * 61}" />',
		):
			with self.subTest(bad=bad):
				self.refused(self.agent(self.ed, "write_files", files=[{"path": self.folder + "a.vue", "content": bad}]))

		self.ok(self.agent(self.ed, "write_files", files=[{"path": self.folder + "helper.vue", "content": "<template><i/></template>"}]))

	def test_an_editors_folder_is_small(self):
		self.invite()
		files = [{"path": f"{self.folder}f{n}.vue", "content": "<template><i/></template>"} for n in range(31)]
		self.refused(self.agent(self.ed, "write_files", files=files))
		big = [{"path": self.folder + "big.vue", "content": "<template>" + "x" * 500_000 + "</template>"}]
		self.refused(self.agent(self.ed, "write_files", files=big))

	def test_an_editors_picture_goes_in_their_folder(self):
		self.invite()
		self.ok(
			self.agent(
				self.ed,
				"upload_asset",
				path=self.folder + "assets/logo.js",
				data_base64=PNG,
				mime_type="image/png",
			)
		)
		self.assertIn(self.folder + "assets/logo.js", self.tree())

	def test_a_reader_and_a_removed_editor_write_nothing(self):
		self.invite()
		with set_user(self.owner):
			api.remove_editor(self.doc.slug, "d2tshed")
		for user in (self.reader, self.ed):
			with self.subTest(user=user):
				text = self.refused(
					self.agent(
						user,
						"write_files",
						prototype=f"d2tshown/{self.doc.slug}",
						files=[{"path": self.folder + "a.vue", "content": COMPACT}],
					)
				)
				self.assertIn("No prototype", text)

		self.assertNotIn(self.folder + "a.vue", self.tree())

	def test_the_owners_agent_keeps_the_whole_tree_editor_folders_included(self):
		self.add_variant()
		self.ok(self.agent(self.owner, "edit_file", path=self.folder + "compact.vue", old_string="Compact</p>", new_string="Fixed</p>"))
		self.ok(self.agent(self.owner, "write_files", files=[{"path": "src/App.vue", "content": "<template>x</template>"}]))
		self.ok(self.agent(self.owner, "delete_file", path=self.folder + "compact.vue"))


class TestEditorsCannotDecide(ShareCase):
	def test_every_owner_only_tool_refuses_an_editor(self):
		self.invite()
		for tool, args in (
			("set_public", {"is_public": True}),
			("set_name", {"name": "Mine now"}),
			("set_runtime", {"version": utils.newest_runtime()}),
			("restore_version", {"sequence": 1}),
		):
			with self.subTest(tool=tool):
				text = self.refused(self.agent(self.ed, tool, **args))
				self.assertIn("Only the owner", text)

		self.doc.reload()
		self.assertFalse(self.doc.is_public)
		self.assertEqual(self.doc.title, "d2t-share")

	def test_an_editor_cannot_make_a_default_by_any_door(self):
		self.add_variant()
		with set_user(self.ed):
			with self.assertRaises(frappe.DoesNotExistError):
				api.set_variant_default(self.doc.slug, "src/pages/Home.vue", "KPI strip", "tall")

			with self.assertRaises(frappe.DoesNotExistError):
				api.set_variant_default("d2tshown/d2t-share", "src/pages/Home.vue", "KPI strip", "tall")

		# The signed door wants a credential only the owner's live page carries.
		editor_page = self.page_data_for(self.ed)
		self.assertEqual(editor_page["variant_sig"], "")
		with set_user("Guest"), self.assertRaises(frappe.DoesNotExistError):
			api.set_variant_default_signed(
				self.doc.name,
				exp=str(signature.mint(self.doc.name, 600, signature.VARIANT_EDIT)["exp"]),
				sig=signature.mint(self.doc.name, 600, signature.VARIANT_EDIT)["sig"],
				file="src/pages/Home.vue",
				set_name="KPI strip",
				option="tall",
			)

		self.assertEqual(self.tree()["src/pages/Home.vue"], HOME)



class TestEditorNotes(ShareCase):
	"""An editor keeps notes of their own. Theirs and the owner's never meet, by any door."""

	NOTE = {"id": "n1", "route": "/", "note": "owner's", "offset": {"x": 0, "y": 0}, "rect": {}}

	def body(self, note: str, id: str = "n1") -> str:
		return json.dumps({"notes": [{**self.NOTE, "id": id, "note": note}], "tweaks": [], "prompt": ""})

	def save_as_editor(self, page: dict, note: str, id: str = "e1"):
		with set_user("Guest"):
			return api.save_annotations(
				self.doc.name,
				str(page["annotate_exp"]),
				page["annotate_sig"],
				self.body(note, id),
				str(page["annotations_epoch"]),
				username="d2tshed",
			)

	def setUp(self):
		super().setUp()
		self.invite()
		annotations.save(self.doc.name, self.body("owner's"), 0)

	def notes(self, reply) -> list[str]:
		return [n["note"] for n in self.ok(reply)["structuredContent"]["notes"]]

	def test_the_editors_page_carries_their_own_notes_and_a_signature_for_them(self):
		page = self.page_data_for(self.ed)
		self.assertTrue(page["annotate_sig"])
		self.assertEqual(page["annotations"]["notes"], [])
		self.assertTrue(
			signature.verify(comments.subject(self.doc.name, "d2tshed"), page["annotate_exp"], page["annotate_sig"], signature.ANNOTATE)
		)
		self.assertFalse(
			signature.verify(self.doc.name, page["annotate_exp"], page["annotate_sig"], signature.ANNOTATE),
			"an editor's signature never writes the owner's notes",
		)

	def test_an_editor_saves_their_own_and_the_owner_never_sees_them(self):
		self.save_as_editor(self.page_data_for(self.ed), "editor's")
		self.assertEqual(self.notes(self.agent(self.owner, "get_annotations")), ["owner's"])
		self.assertEqual(self.notes(self.agent(self.ed, "get_annotations")), ["editor's"])
		self.assertEqual(self.page_data_for(self.owner)["annotations"]["notes"][0]["note"], "owner's")
		self.assertEqual(self.page_data_for(self.ed)["annotations"]["notes"][0]["note"], "editor's")

	def test_clearing_touches_only_the_callers_notes(self):
		self.save_as_editor(self.page_data_for(self.ed), "editor's")
		self.ok(self.agent(self.ed, "clear_annotations"))
		self.assertEqual(self.notes(self.agent(self.ed, "get_annotations")), [])
		self.assertEqual(self.notes(self.agent(self.owner, "get_annotations")), ["owner's"])

		self.save_as_editor(self.page_data_for(self.ed), "again")
		self.ok(self.agent(self.owner, "clear_annotations"))
		self.assertEqual(self.notes(self.agent(self.owner, "get_annotations")), [])
		self.assertEqual(self.notes(self.agent(self.ed, "get_annotations")), ["again"])

	def test_the_owners_signature_cannot_write_as_an_editor(self):
		owner_page = self.page_data_for(self.owner)
		with self.assertRaises(frappe.DoesNotExistError):
			self.save_as_editor(owner_page, "forged")
		self.assertEqual(self.notes(self.agent(self.ed, "get_annotations")), [])

	def test_a_removed_editors_signature_saves_nothing(self):
		page = self.page_data_for(self.ed)
		with set_user(self.owner):
			api.remove_editor(self.doc.slug, "d2tshed")
		with self.assertRaises(frappe.DoesNotExistError):
			self.save_as_editor(page, "late")

	def test_a_disabled_editors_signature_saves_nothing(self):
		page = self.page_data_for(self.ed)
		frappe.db.set_value("User", self.ed, "enabled", 0)
		self.addCleanup(frappe.db.set_value, "User", self.ed, "enabled", 1)
		with self.assertRaises(frappe.DoesNotExistError):
			self.save_as_editor(page, "late")

	def test_a_reader_and_a_stranger_get_no_notes(self):
		for user in (self.reader, self.other):
			with self.subTest(user=user):
				self.refused(self.agent(user, "get_annotations"))
				self.refused(self.agent(user, "clear_annotations"))


class TestStamping(ShareCase):
	def test_made_by_is_the_folder_and_the_page_gets_the_name_from_the_user_row(self):
		self.add_variant()
		page = self.page_data_for(self.owner)
		self.assertEqual(page["authors"]["d2tshed"]["name"], "Sketch Test shed")
		self.assertEqual(page["role"], "owner")

	def test_a_file_cannot_name_another_author(self):
		self.invite()
		forged = '<variant set="KPI strip" name="Compact" author="d2tshown" by="d2tshown" made-by="@d2tshown" />\n<template><p>x</p></template>\n'
		self.ok(self.agent(self.ed, "write_files", files=[{"path": self.folder + "forged.vue", "content": forged}]))
		page = self.page_data_for(self.owner)
		self.assertEqual(sharing.author_of_path(self.folder + "forged.vue"), "d2tshed")
		self.assertNotIn("d2tshown", page["authors"], "the file's claim is never read")
		self.assertIn("d2tshed", page["authors"])

	def test_an_editor_cannot_write_into_another_editors_folder(self):
		self.invite()
		with set_user(self.owner):
			api.invite_editor(self.doc.slug, "d2tshoth")
		self.refused(
			self.agent(self.ed, "write_files", files=[{"path": "src/variants/@d2tshoth/x.vue", "content": COMPACT}])
		)
		self.assertNotIn("src/variants/@d2tshoth/x.vue", self.tree())

	def test_a_folder_that_matches_no_user_has_no_author(self):
		prototype_files.write_files(self.doc.name, [{"path": "src/variants/@d2tnobody/a.vue", "content": COMPACT}])
		page = self.page_data_for(self.owner)
		self.assertNotIn("d2tnobody", page["authors"])

	def test_the_owners_variants_carry_no_author(self):
		self.assertIsNone(sharing.author_of_path("src/pages/Home.vue"))
		self.assertIsNone(sharing.author_of_path("src/variants/adopted/a.vue"))
		self.assertEqual(sharing.author_of_path("src/variants/@a-b/x/y.vue"), "a-b")


class TestPrivate(ShareCase):
	def test_the_owner_and_the_invited_see_it_and_a_reader_does_not(self):
		self.invite()
		for user, sees in ((self.owner, True), (self.ed, True), (self.reader, False), ("Guest", False)):
			with self.subTest(user=user):
				renderer = SketchViewerRenderer(path=f"u/d2tshown/{self.doc.slug}")
				with set_user(user):
					self.assertEqual(renderer.can_render(), sees)
					self.assertEqual(sharing.can_view(self.doc.name, user), sees)

	def test_the_editor_reads_the_source_and_the_reader_cannot(self):
		self.invite()
		with set_user(self.ed):
			self.assertTrue(api.list_prototype_files(self.doc.slug, "d2tshown"))
		with set_user(self.reader), self.assertRaises(frappe.DoesNotExistError):
			api.list_prototype_files(self.doc.slug, "d2tshown")

	def test_the_editor_comments_on_a_private_prototype_and_the_reader_cannot(self):
		self.invite()
		for user, ok in ((self.ed, True), (self.reader, False)):
			username = utils.username_of(user)
			ticket = comments.mint_ticket(self.doc.name, username)
			with set_user("Guest"):
				if ok:
					got = api.comment_pass(self.doc.name, username, str(ticket["exp"]), ticket["sig"])
					self.assertTrue(got["sig"])
				else:
					with self.assertRaises(frappe.DoesNotExistError):
						api.comment_pass(self.doc.name, username, str(ticket["exp"]), ticket["sig"])

	def test_a_removed_editor_loses_everything_at_once_and_their_variants_stay(self):
		self.add_variant()
		ticket = comments.mint_ticket(self.doc.name, "d2tshed")
		with set_user("Guest"):
			held = api.comment_pass(self.doc.name, "d2tshed", str(ticket["exp"]), ticket["sig"])
		with set_user(self.owner):
			api.remove_editor(self.doc.slug, "d2tshed")

		renderer = SketchViewerRenderer(path=f"u/d2tshown/{self.doc.slug}")
		with set_user(self.ed):
			self.assertFalse(renderer.can_render())
			self.assertEqual(api.shared_prototypes(), [])
			with self.assertRaises(frappe.DoesNotExistError):
				api.list_prototype_files(self.doc.slug, "d2tshown")

		with set_user("Guest"):
			with self.assertRaises(frappe.DoesNotExistError):
				api.comments_list(self.doc.name, "d2tshed", str(held["exp"]), held["sig"])
			with self.assertRaises(frappe.DoesNotExistError):
				self.delete_as(self.ed, "@d2tshed/compact")

		listed = self.agent(self.ed, "list_prototypes")["structuredContent"]["prototypes"]
		self.assertEqual(listed, [])
		self.assertIn(self.folder + "compact.vue", self.tree(), "their variants stay")

	def test_making_it_public_opens_it_to_a_reader_again(self):
		with set_user(self.owner):
			api.set_public(self.doc.slug, True)
		with set_user(self.reader):
			self.assertTrue(sharing.can_view(self.doc.name, self.reader))
			self.assertEqual(sharing.role_of(self.doc.name, self.reader), "viewer")

	def test_the_five_standings(self):
		self.invite()
		roles = {
			self.owner: "owner",
			self.ed: "editor",
			self.reader: "viewer",
			"Guest": "guest",
		}
		for user, role in roles.items():
			with self.subTest(user=user):
				self.assertEqual(sharing.role_of(self.doc.name, user), role)

	def test_the_viewer_over_http_serves_the_editor_and_not_the_reader(self):
		utils.require_webserver()
		self.invite()
		path = f"/u/d2tshown/{self.doc.slug}"
		editor = utils.request("GET", path, headers=utils.api_auth_header(self.ed))
		reader = utils.request("GET", path, headers=utils.api_auth_header(self.reader))
		guest = utils.request("GET", path)
		self.assertEqual((editor.status_code, reader.status_code, guest.status_code), (200, 404, 404))
		slot = utils.data_slot(editor.text)
		self.assertEqual(slot["role"], "editor")
		self.assertFalse(slot["is_owner"])
		self.assertTrue(slot["annotate_sig"], "an editor keeps notes of their own")
		self.assertEqual(slot["variant_sig"], "")
		self.assertTrue(slot["edit_sig"], "an editor may delete their own variants")


class TestVersions(ShareCase):
	def test_an_editors_commit_carries_their_name_and_leaves_the_owners_pending(self):
		self.invite()
		self.ok(self.agent(self.owner, "write_files", files=[{"path": "src/pages/New.vue", "content": "<template>n</template>"}]))
		self.ok(self.agent(self.ed, "write_files", files=[{"path": self.folder + "a.vue", "content": COMPACT}]))
		made = self.ok(self.agent(self.ed, "commit", prompt="Add a compact strip"))["structuredContent"]
		self.assertEqual(made["changes"], [{"path": self.folder + "a.vue", "action": "added"}])
		row = versions.history(self.doc.name)[0]
		self.assertEqual(row["author"], "d2tshed")
		self.assertEqual(versions.pending(self.doc.name), [{"path": "src/pages/New.vue", "action": "added"}])
		owner_made = self.ok(self.agent(self.owner, "commit", prompt="Add a page"))["structuredContent"]
		self.assertEqual([c["path"] for c in owner_made["changes"]], ["src/pages/New.vue"])
		self.assertIsNone(versions.history(self.doc.name)[0]["author"])

	def test_the_owner_sees_the_author_in_the_list_and_an_editor_sees_only_their_own(self):
		self.add_variant()
		self.ok(self.agent(self.owner, "write_files", files=[{"path": "src/pages/New.vue", "content": "<template>n</template>"}]))
		self.ok(self.agent(self.owner, "commit", prompt="Owner private prompt"))
		with set_user(self.owner):
			rows = api.list_versions(self.doc.slug)
		self.assertEqual(rows[1]["author"], {"username": "d2tshed", "full_name": "Sketch Test shed"})
		self.assertIsNone(rows[0]["author"])
		mine = self.ok(self.agent(self.ed, "list_versions"))["structuredContent"]["versions"]
		self.assertEqual([v["prompt"] for v in mine], ["Add a compact KPI strip"])
		self.assertEqual(mine[0]["author"], "d2tshed")

	def test_changes_noted_one_call_at_a_time_all_reach_the_version(self):
		"""Each write, edit and delete notes one file. A later note must not drop an earlier one, or from another person."""
		self.invite()
		self.ok(self.agent(self.owner, "write_files", files=[{"path": "src/pages/New.vue", "content": "<template>n</template>"}]))
		for name in ("a", "b", "c"):
			self.ok(self.agent(self.ed, "write_files", files=[{"path": self.folder + name + ".vue", "content": COMPACT}]))
		self.ok(self.agent(self.ed, "commit", prompt="Three"))
		for name in ("a", "b", "c"):
			self.ok(self.agent(self.ed, "delete_file", path=self.folder + name + ".vue"))
		made = self.ok(self.agent(self.ed, "commit", prompt="Remove them"))["structuredContent"]
		self.assertEqual(sorted(c["path"] for c in made["changes"]), [self.folder + n + ".vue" for n in "abc"])
		self.assertEqual(versions.pending(self.doc.name), [{"path": "src/pages/New.vue", "action": "added"}])

	def test_an_editors_uncommitted_count_is_their_own(self):
		self.invite()
		self.ok(self.agent(self.owner, "write_files", files=[{"path": "src/pages/New.vue", "content": "<template>n</template>"}]))
		self.assertEqual(versions.pending_count(self.doc.name, "d2tshed"), 0)
		self.ok(self.agent(self.ed, "write_files", files=[{"path": self.folder + "a.vue", "content": COMPACT}]))
		self.assertEqual(versions.pending_count(self.doc.name, "d2tshed"), 1)
		self.assertEqual(versions.pending_count(self.doc.name), 1)


class TestRestore(ShareCase):
	def test_a_restore_never_deletes_or_reverts_an_editors_variant(self):
		self.ok(self.agent(self.owner, "commit", prompt="start") if versions.pending(self.doc.name) else self._first())
		v1 = versions.history(self.doc.name)[0]["sequence"]
		self.add_variant()
		self.ok(self.agent(self.owner, "write_files", files=[{"path": "src/pages/Home.vue", "content": HOME + "<!-- later -->\n"}]))
		self.ok(self.agent(self.owner, "commit", prompt="Later change"))

		with set_user(self.owner):
			preview = api.restore_version(self.doc.slug, v1, 1)
			self.assertEqual(preview["kept_editor_files"], 1)
			self.assertEqual([c["path"] for c in preview["changes"]], ["src/pages/Home.vue"])
			done = api.restore_version(self.doc.slug, v1)

		self.assertEqual(done["kept_editor_files"], 1)
		tree = self.tree()
		self.assertEqual(tree["src/pages/Home.vue"], HOME, "the owner's file went back")
		self.assertEqual(tree[self.folder + "compact.vue"], COMPACT, "the editor's variant stayed")

	def test_an_editor_file_changed_since_goes_back_as_the_version_held_it(self):
		self.add_variant()
		v_with = versions.history(self.doc.name)[0]["sequence"]
		self.ok(self.agent(self.ed, "edit_file", path=self.folder + "compact.vue", old_string="Compact</p>", new_string="Newer</p>"))
		self.ok(self.agent(self.ed, "commit", prompt="Tweak it"))
		with set_user(self.owner):
			api.restore_version(self.doc.slug, v_with)

		self.assertEqual(self.tree()[self.folder + "compact.vue"], COMPACT)

	def test_restoring_back_forward_leaves_the_editor_alone_too(self):
		self._first()
		v1 = versions.history(self.doc.name)[0]["sequence"]
		self.add_variant()
		with set_user(self.owner):
			restored = api.restore_version(self.doc.slug, v1)
			self.assertFalse(restored["recorded"] is True and restored["files_deleted"], "no file of the editor's was deleted")
		self.assertIn(self.folder + "compact.vue", self.tree())

	def _first(self):
		self.ok(self.agent(self.owner, "write_files", files=[{"path": "src/extra.vue", "content": "<template>e</template>"}]))
		return self.ok(self.agent(self.owner, "commit", prompt="start"))


class TestDeleteAndDefault(ShareCase):
	def test_an_editor_deletes_their_own_and_undo_brings_it_back(self):
		self.add_variant()
		done = self.delete_as(self.ed, "@d2tshed/compact")
		self.assertNotIn(self.folder + "compact.vue", self.tree())
		self.assertEqual(done["label"], "Compact")
		self.assertEqual(versions.history(self.doc.name)[0]["author"], "d2tshed")
		self.undo_delete_as(self.ed, "@d2tshed/compact", done["sequence"])
		self.assertEqual(self.tree()[self.folder + "compact.vue"], COMPACT)

	def test_an_editor_cannot_delete_the_owners_or_another_editors(self):
		self.add_variant()
		with set_user(self.owner):
			api.invite_editor(self.doc.slug, "d2tshoth")
		other = "src/variants/@d2tshoth/theirs.vue"
		prototype_files.write_files(self.doc.name, [{"path": other, "content": COMPACT}])
		with self.assertRaises(frappe.PermissionError):
			self.delete_as(self.other, "@d2tshed/compact")

		with self.assertRaises((frappe.PermissionError, frappe.ValidationError)):
			self.delete_as(self.ed, "../../pages/Home")

		with self.assertRaises((frappe.PermissionError, frappe.ValidationError)):
			self.delete_as(self.ed, "adopted/anything")

		self.assertIn(self.folder + "compact.vue", self.tree())
		self.assertIn("src/pages/Home.vue", self.tree())

	def test_the_owner_deletes_any_and_an_editor_cannot_undo_it(self):
		self.add_variant()
		done = self.delete_as(self.owner, "@d2tshed/compact")
		self.assertIsNone(versions.history(self.doc.name)[0]["author"])
		with self.assertRaises(frappe.PermissionError):
			self.undo_delete_as(self.ed, "@d2tshed/compact", done["sequence"])

		self.undo_delete_as(self.owner, "@d2tshed/compact", done["sequence"])
		self.assertIn(self.folder + "compact.vue", self.tree())

	def test_undo_is_refused_when_the_file_came_back_changed(self):
		self.add_variant()
		done = self.delete_as(self.ed, "@d2tshed/compact")
		self.ok(self.agent(self.ed, "write_files", files=[{"path": self.folder + "compact.vue", "content": "<template>again</template>"}]))
		with self.assertRaises(frappe.ValidationError):
			self.undo_delete_as(self.ed, "@d2tshed/compact", done["sequence"])

	def test_make_default_copies_the_variant_into_the_owners_files_and_keeps_the_author(self):
		self.add_variant()
		with set_user(self.owner):
			done = api.set_variant_default(self.doc.slug, "src/pages/Home.vue", "KPI strip", "@d2tshed/compact")

		tree = self.tree()
		self.assertNotIn(self.folder + "compact.vue", tree)
		self.assertEqual(tree["src/variants/adopted/compact.vue"], COMPACT)
		registry = json.loads(tree["src/variants/adopted.json"])
		self.assertEqual(list(registry), ["src/variants/adopted/compact.vue"])
		# `at` is when the owner adopted it: the editor's card says so until they next open the prototype.
		self.assertEqual({k: v for k, v in registry["src/variants/adopted/compact.vue"].items() if k != "at"}, {"author": "d2tshed", "default": True})
		self.assertTrue(registry["src/variants/adopted/compact.vue"]["at"])
		self.assertEqual(done["option"], "adopted/compact")
		self.assertEqual(tree["src/pages/Home.vue"], HOME, "the page's source is not rewritten")
		self.assertEqual(versions.history(self.doc.name)[0]["prompt"], "Made “Compact” the default for KPI strip")
		page = self.page_data_for(self.owner)
		self.assertEqual(page["authors"]["d2tshed"]["name"], "Sketch Test shed")

		with set_user(self.owner):
			api.undo_variant_default(self.doc.slug, "src/pages/Home.vue", done["sequence"], "KPI strip", "wide")

		tree = self.tree()
		self.assertEqual(tree[self.folder + "compact.vue"], COMPACT)
		self.assertNotIn("src/variants/adopted/compact.vue", tree)
		self.assertNotIn("src/variants/adopted.json", tree)

	def test_the_owners_own_option_takes_the_lead_back_from_an_adopted_one(self):
		self.add_variant()
		with set_user(self.owner):
			api.set_variant_default(self.doc.slug, "src/pages/Home.vue", "KPI strip", "@d2tshed/compact")
			api.set_variant_default(self.doc.slug, "src/pages/Home.vue", "KPI strip", "wide")

		registry = json.loads(self.tree()["src/variants/adopted.json"])
		self.assertFalse(registry["src/variants/adopted/compact.vue"]["default"])
		# The owner's pick is recorded on the tag, even for the first slot: no slot moves.
		self.assertEqual(self.tree()["src/pages/Home.vue"], HOME.replace('name="KPI strip"', 'name="KPI strip" default="wide"'))

	def test_make_default_on_a_component_variant_and_back_to_the_original(self):
		self.add_variant(WRAP, "dense.vue")
		with set_user(self.owner):
			api.set_variant_default(self.doc.slug, "src/components/KpiStrip.vue", "Kpi strip", "@d2tshed/dense")
			registry = json.loads(self.tree()["src/variants/adopted.json"])
			self.assertTrue(registry["src/variants/adopted/dense.vue"]["default"])
			api.set_variant_default(self.doc.slug, "src/components/KpiStrip.vue", "Kpi strip", "original")

		registry = json.loads(self.tree()["src/variants/adopted.json"])
		self.assertFalse(registry["src/variants/adopted/dense.vue"]["default"])

	def test_a_variant_cannot_be_made_default_of_a_set_it_does_not_target(self):
		self.add_variant()
		with set_user(self.owner), self.assertRaises(frappe.ValidationError):
			api.set_variant_default(self.doc.slug, "src/pages/Home.vue", "Another set", "@d2tshed/compact")

		self.assertIn(self.folder + "compact.vue", self.tree())

	def test_the_option_value_is_a_name_never_a_place(self):
		for bad in ("../../App", "@d2tshed/../../App", "src/App", "/etc/passwd", "@d2tshed", ""):
			with self.subTest(bad=bad):
				self.assertFalse(editor_variants.is_extra(bad))


class TestKeepOnly(ShareCase):
	def owner_page(self):
		return self.page_data_for(self.owner)

	def keep_as_page(self, option, sig=None, exp=None, name="KPI strip", file="src/pages/Home.vue"):
		page = self.owner_page()
		with set_user("Guest"):
			return api.keep_variant_signed(
				self.doc.name,
				exp=str(page["variant_exp"]) if exp is None else exp,
				sig=page["variant_sig"] if sig is None else sig,
				file=file,
				set_name=name,
				option=option,
			)

	def test_a_restore_brings_back_an_editors_option_that_keep_only_this_deleted(self):
		self.add_variant()
		v_with = versions.history(self.doc.name)[0]["sequence"]
		self.keep_as_page("tall")
		self.assertNotIn(self.folder + "compact.vue", self.tree(), "Keep only this removed the editor's option")
		with set_user(self.owner):
			done = api.restore_version(self.doc.slug, v_with)

		self.assertEqual(self.tree()[self.folder + "compact.vue"], COMPACT, "the owner's restore wrote in the editor's folder")
		self.assertEqual(done["kept_editor_files"], 0)

	def test_keep_only_cuts_the_other_slots_and_every_editor_variant(self):
		self.add_variant()
		with set_user(self.owner):
			api.set_variant_default(self.doc.slug, "src/pages/Home.vue", "KPI strip", "@d2tshed/compact")

		self.ok(self.agent(self.ed, "write_files", files=[{"path": self.folder + "again.vue", "content": COMPACT}]))
		done = self.keep_as_page("tall")
		tree = self.tree()
		self.assertEqual(done["label"], "Tall")
		self.assertIn("<template #tall><p>Tall</p></template>", tree["src/pages/Home.vue"])
		self.assertNotIn("#wide", tree["src/pages/Home.vue"])
		self.assertIn("<Variants name=\"KPI strip\">\n    <template #tall>", tree["src/pages/Home.vue"])
		self.assertEqual([p for p in tree if p.startswith("src/variants/")], [])
		self.assertEqual(versions.history(self.doc.name)[0]["prompt"], "Kept \u201cTall\u201d as the only option of KPI strip")

	def test_keep_only_a_wrapped_component_removes_its_variants_and_leaves_the_file(self):
		self.add_variant(WRAP, "dense.vue")
		done = self.keep_as_page("original", name="Kpi strip", file="src/components/KpiStrip.vue")
		self.assertEqual(done["label"], "Original")
		self.assertEqual(self.tree()["src/components/KpiStrip.vue"], FILES["src/components/KpiStrip.vue"])
		self.assertNotIn(self.folder + "dense.vue", self.tree())

	def test_only_the_owners_signature_keeps_only_this(self):
		self.add_variant()
		before = self.tree()
		page = self.owner_page()
		stamp = signature.mint(self.doc.name, 600, signature.VARIANT_EDIT)
		editor = self.edit_credential(self.ed)
		for who, args in {
			"an editor's own signature": {"exp": editor["exp"], "sig": editor["sig"]},
			"the edit scope for the page": {"exp": str(stamp["exp"]), "sig": stamp["sig"]},
			"a bad signature": {"exp": str(page["variant_exp"]), "sig": "0" * len(page["variant_sig"])},
			"no signature": {"exp": "", "sig": ""},
		}.items():
			with self.subTest(who), self.assertRaises(frappe.DoesNotExistError):
				self.keep_as_page("tall", **args)

		self.assertEqual(self.editor_page_signature(), "")
		for user in (self.ed, self.reader):
			with set_user(user):
				with self.assertRaises(frappe.DoesNotExistError):
					api.keep_variant(self.doc.slug, "src/pages/Home.vue", "KPI strip", "tall")

		self.assertEqual(self.tree(), before)

	def editor_page_signature(self):
		return self.page_data_for(self.ed)["variant_sig"]

	def test_keep_only_refuses_an_option_the_set_does_not_have_and_a_set_with_one(self):
		self.add_variant()
		with self.assertRaises(frappe.ValidationError):
			self.keep_as_page("missing")

		with self.assertRaises(frappe.ValidationError):
			self.keep_as_page("@d2tshed/gone")

		with self.assertRaises(frappe.ValidationError):
			self.keep_as_page("adopted/gone")

		self.keep_as_page("wide")
		with self.assertRaises(frappe.ValidationError):
			self.keep_as_page("wide")

	def test_keep_only_says_how_many_options_went(self):
		self.add_variant()
		done = self.keep_as_page("tall")
		self.assertEqual(done["removed"], 2, "wide and the editor's Compact")

	def test_keep_only_on_an_editors_option_adopts_it_then_keeps_it(self):
		self.add_variant()
		done = self.keep_as_page("@d2tshed/compact")
		tree = self.tree()
		self.assertEqual(done["label"], "Compact")
		self.assertEqual(done["option"], "adopted/compact")
		self.assertEqual(done["removed"], 2, "wide and tall")
		self.assertEqual(tree["src/variants/adopted/compact.vue"], COMPACT)
		entry = json.loads(tree["src/variants/adopted.json"])["src/variants/adopted/compact.vue"]
		self.assertEqual((entry["author"], entry["default"]), ("d2tshed", True))
		self.assertTrue(entry["at"], "when it was adopted")
		self.assertEqual([p for p in tree if p.startswith(self.folder)], [])
		# One version holds the adoption and the cut: the history has no half step.
		history = versions.history(self.doc.name)
		self.assertEqual(history[0]["prompt"], "Kept \u201cCompact\u201d as the only option of KPI strip")
		self.assertNotIn("Made", history[1]["prompt"])

	def test_a_set_left_with_one_option_keeps_its_wrapper_and_editors_can_add_again(self):
		self.add_variant()
		self.keep_as_page("@d2tshed/compact")
		home = self.tree()["src/pages/Home.vue"]
		self.assertIn('<Variants name="KPI strip">', home)
		self.assertNotIn("<template #", home, "no slot of the owner's is left")

		self.ok(self.agent(self.ed, "write_files", files=[{"path": self.folder + "second.vue", "content": COMPACT}]))
		found = editor_variants.targeting(self.doc.name, "src/pages/Home.vue", "KPI strip")
		self.assertEqual(sorted(found), [self.folder + "second.vue", "src/variants/adopted/compact.vue"])

	def test_keep_only_on_an_adopted_option_removes_the_rest(self):
		self.add_variant()
		with set_user(self.owner):
			api.set_variant_default(self.doc.slug, "src/pages/Home.vue", "KPI strip", "@d2tshed/compact")

		self.ok(self.agent(self.ed, "write_files", files=[{"path": self.folder + "again.vue", "content": COMPACT}]))
		done = self.keep_as_page("adopted/compact")
		tree = self.tree()
		self.assertEqual(done["removed"], 3, "wide, tall and the editor's second")
		self.assertEqual(done["label"], "Compact")
		self.assertEqual([p for p in tree if p.startswith("src/variants/")], ["src/variants/adopted.json", "src/variants/adopted/compact.vue"])
		self.assertNotIn("<template #", tree["src/pages/Home.vue"])

	def test_keep_only_on_an_editors_option_of_a_wrapped_component_replaces_the_component(self):
		self.add_variant(WRAP, "dense.vue")
		self.ok(self.agent(self.ed, "write_files", files=[{"path": self.folder + "more.vue", "content": WRAP}]))
		done = self.keep_as_page("@d2tshed/dense", name="Kpi strip", file="src/components/KpiStrip.vue")
		tree = self.tree()
		self.assertEqual(done["removed"], 2, "the component's own version and the other variant")
		self.assertEqual(done["label"], "Dense")
		self.assertEqual(done["option"], "original")
		self.assertTrue(done["replaced"], "no set is left, so the toast names the component")
		self.assertEqual(tree["src/components/KpiStrip.vue"], "<template><p>Dense</p></template>\n")
		self.assertEqual([p for p in tree if p.startswith("src/variants/")], [], "no variant, no registry, so no set")
		self.assertEqual(versions.history(self.doc.name)[0]["prompt"], "Kept \u201cDense\u201d as the only option of Kpi strip")

	def test_keeping_a_wrapped_components_option_leaves_one_other_to_report_when_it_was_alone(self):
		self.add_variant(WRAP, "dense.vue")
		done = self.keep_as_page("@d2tshed/dense", name="Kpi strip", file="src/components/KpiStrip.vue")
		self.assertEqual(done["removed"], 1, "the owner's original")

	def test_a_replacement_that_reads_as_the_component_still_removes_the_variant(self):
		self.add_variant('<variant component="src/components/KpiStrip.vue" name="Dense" />\n' + FILES["src/components/KpiStrip.vue"], "same.vue")
		done = self.keep_as_page("@d2tshed/same", name="Kpi strip", file="src/components/KpiStrip.vue")
		tree = self.tree()
		self.assertEqual(done["removed"], 1)
		self.assertEqual(tree["src/components/KpiStrip.vue"], FILES["src/components/KpiStrip.vue"])
		self.assertEqual([p for p in tree if p.startswith("src/variants/")], [])

	def test_the_replacement_keeps_its_relative_imports_pointing_at_the_same_files(self):
		wrap = (
			'<variant component="src/components/KpiStrip.vue" name="Dense" />\n'
			'<script setup>\nimport Tile from "../../components/Tile.vue"\nimport { x } from \'./local.ts\'\n'
			'import Alias from "@/components/Alias.vue"\n</script>\n<template><Tile /></template>\n'
		)
		self.add_variant(wrap, "dense.vue")
		self.keep_as_page("@d2tshed/dense", name="Kpi strip", file="src/components/KpiStrip.vue")
		component = self.tree()["src/components/KpiStrip.vue"]
		self.assertNotIn("<variant", component)
		self.assertIn('import Tile from "./Tile.vue"', component)
		self.assertIn("import { x } from '../variants/@d2tshed/local.ts'", component)
		self.assertIn('import Alias from "@/components/Alias.vue"', component)

	def test_keep_only_on_an_adopted_option_of_a_wrapped_component_replaces_it_too(self):
		self.add_variant(WRAP, "dense.vue")
		with set_user(self.owner):
			api.set_variant_default(self.doc.slug, "src/components/KpiStrip.vue", "Kpi strip", "@d2tshed/dense")

		done = self.keep_as_page("adopted/dense", name="Kpi strip", file="src/components/KpiStrip.vue")
		tree = self.tree()
		self.assertEqual(done["removed"], 1)
		self.assertEqual(tree["src/components/KpiStrip.vue"], "<template><p>Dense</p></template>\n")
		self.assertEqual([p for p in tree if p.startswith("src/variants/")], [])

	def test_undo_after_replacing_a_wrapped_component_restores_every_file_exactly(self):
		self.add_variant(WRAP, "dense.vue")
		self.ok(self.agent(self.ed, "write_files", files=[{"path": self.folder + "more.vue", "content": WRAP}]))
		self.ok(self.agent(self.ed, "commit", prompt="Add another"))
		before = self.tree()
		done = self.keep_as_page("@d2tshed/dense", name="Kpi strip", file="src/components/KpiStrip.vue")
		self.assertNotEqual(self.tree(), before)
		page = self.owner_page()
		with set_user("Guest"):
			api.undo_keep_variant_signed(
				self.doc.name,
				exp=str(page["variant_exp"]),
				sig=page["variant_sig"],
				file="src/components/KpiStrip.vue",
				sequence=str(done["sequence"]),
				set_name="Kpi strip",
				option=done["option"],
			)

		self.assertEqual(self.tree(), before)
		self.assertEqual(versions.history(self.doc.name)[0]["prompt"], "Undid keeping only \u201cDense\u201d in Kpi strip")

	def test_keep_only_on_another_sets_variant_is_refused(self):
		self.add_variant()
		before = self.tree()
		with self.assertRaises(frappe.ValidationError):
			self.keep_as_page("@d2tshed/compact", name="Another set")

		self.assertEqual(self.tree(), before)

	def test_undo_restores_the_slots_and_the_editors_variants_exactly(self):
		self.add_variant()
		with set_user(self.owner):
			api.set_variant_default(self.doc.slug, "src/pages/Home.vue", "KPI strip", "@d2tshed/compact")

		self.ok(self.agent(self.ed, "write_files", files=[{"path": self.folder + "second.vue", "content": COMPACT}]))
		self.ok(self.agent(self.ed, "commit", prompt="Add another"))
		before = self.tree()
		done = self.keep_as_page("tall")
		self.assertNotEqual(self.tree(), before)
		page = self.owner_page()
		with set_user("Guest"):
			api.undo_keep_variant_signed(
				self.doc.name,
				exp=str(page["variant_exp"]),
				sig=page["variant_sig"],
				file="src/pages/Home.vue",
				sequence=str(done["sequence"]),
				set_name="KPI strip",
				option="tall",
			)

		self.assertEqual(self.tree(), before)
		self.assertEqual(versions.history(self.doc.name)[0]["prompt"], "Undid keeping only \u201cTall\u201d in KPI strip")

	def test_undo_after_keeping_an_editors_option_restores_every_file_exactly(self):
		self.add_variant()
		self.ok(self.agent(self.ed, "write_files", files=[{"path": self.folder + "second.vue", "content": COMPACT}]))
		self.ok(self.agent(self.ed, "commit", prompt="Add another"))
		before = self.tree()
		done = self.keep_as_page("@d2tshed/compact")
		self.assertNotEqual(self.tree(), before)
		page = self.owner_page()
		with set_user("Guest"):
			api.undo_keep_variant_signed(
				self.doc.name,
				exp=str(page["variant_exp"]),
				sig=page["variant_sig"],
				file="src/pages/Home.vue",
				sequence=str(done["sequence"]),
				set_name="KPI strip",
				option=done["option"],
			)

		self.assertEqual(self.tree(), before)
		self.assertEqual(versions.history(self.doc.name)[0]["prompt"], "Undid keeping only \u201cCompact\u201d in KPI strip")

	def test_undo_is_refused_when_the_page_changed_since_and_to_anyone_but_the_owner(self):
		self.add_variant()
		done = self.keep_as_page("tall")
		args = {"file": "src/pages/Home.vue", "sequence": str(done["sequence"]), "set_name": "KPI strip", "option": "tall"}
		editor = self.edit_credential(self.ed)
		with set_user("Guest"), self.assertRaises(frappe.DoesNotExistError):
			api.undo_keep_variant_signed(self.doc.name, exp=editor["exp"], sig=editor["sig"], **args)

		prototype_files.write_files(self.doc.name, [{"path": "src/pages/Home.vue", "content": HOME.replace("Tall", "Taller")}])
		page = self.owner_page()
		with set_user("Guest"), self.assertRaises(frappe.ValidationError):
			api.undo_keep_variant_signed(self.doc.name, exp=str(page["variant_exp"]), sig=page["variant_sig"], **args)

		self.assertNotIn(self.folder + "compact.vue", self.tree())

	def test_undo_keep_refuses_a_version_that_kept_nothing(self):
		self.add_variant()
		done = self.delete_as(self.owner, "@d2tshed/compact")
		page = self.owner_page()
		with set_user("Guest"), self.assertRaises(frappe.ValidationError):
			api.undo_keep_variant_signed(
				self.doc.name,
				exp=str(page["variant_exp"]),
				sig=page["variant_sig"],
				file="src/pages/Home.vue",
				sequence=str(done["sequence"]),
				set_name="KPI strip",
				option="wide",
			)


class TestFork(ShareCase):
	def test_a_fork_does_not_carry_what_other_people_added(self):
		self.add_variant()
		with set_user(self.owner):
			api.set_public(self.doc.slug, True)

		with set_user(self.reader):
			forked = api.fork_prototype("d2tshown", self.doc.slug)

		self.addCleanup(utils.drop_prototype, frappe.db.get_value("Sketch Prototype", {"owner": self.reader, "slug": forked["slug"]}))
		name = frappe.db.get_value("Sketch Prototype", {"owner": self.reader, "slug": forked["slug"]})
		paths = set(prototype_files.read_tree(name))
		self.assertIn("src/pages/Home.vue", paths)
		self.assertFalse([p for p in paths if sharing.is_editor_path(p)])
