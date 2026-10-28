# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""New badges and @mentions: what changed since a person last looked.

The rules this file holds:

- What is new is what somebody else made after you last saw it, per person and per Prototype.
- Your own actions are never new to you.
- A variant is seen when its set is opened, a thread when it is opened, and a new reply by
  someone else makes the thread unread again.
- The gallery counts are what is still unseen, not what the Prototype holds.
- A mention is stored as a username, and only people on the list can be mentioned.
- A Guest gets nothing, and a reader gets comments only.
"""

import json

import frappe
from frappe.tests import IntegrationTestCase, set_user

from sketch import api, badges, comments, editor_variants, signature
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
}

ANCHOR = {
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


def variant(label: str) -> str:
	return f'<variant set="KPI strip" name="{label}" />\n<template><p>{label}</p></template>\n'


class BadgeCase(IntegrationTestCase):
	"""An owner, two invited editors, a reader and a prototype with one set."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_runtime()
		for attr, suffix in (("owner", "bgown"), ("ed", "bged"), ("ed2", "bged2"), ("reader", "bgrd"), ("stranger", "bgstr")):
			email = utils.make_user(suffix, f"d2t{suffix}")
			cls.addClassCleanup(utils.drop_user, email)
			setattr(cls, attr, email)

	def setUp(self):
		super().setUp()
		self.doc = utils.make_prototype(self.owner, "d2t-badges", files=FILES, is_public=True)
		self.addCleanup(utils.drop_prototype, self.doc.name)
		self.name = self.doc.name

	# -- who and how

	def username(self, user):
		return utils.username_of(user)

	def invite(self, *users):
		for user in users:
			with set_user(self.owner):
				api.invite_editor(self.doc.slug, self.username(user))

	def agent(self, user, tool, **args):
		with set_user(user):
			ref = self.doc.slug if user == self.owner else f"{self.username(self.owner)}/{self.doc.slug}"
			reply = tools.call_tool(tool, {"prototype": ref, **args})
		self.assertFalse(reply["isError"], reply["content"][0]["text"])
		return reply

	def add_variant(self, user, label="Compact"):
		"""The user's agent adds one option to the KPI strip and commits."""
		path = f"src/variants/@{self.username(user)}/{label.lower()}.vue"
		self.agent(user, "write_files", files=[{"path": path, "content": variant(label)}])
		self.agent(user, "commit", prompt=f"Add {label}")
		return f"@{self.username(user)}/{label.lower()}"

	def say(self, user, text="Does this read better?", thread=None):
		"""A comment (or a reply, with `thread`) as `user`. Returns the thread id."""
		username = self.username(user)
		actor = comments.Actor(username, user, user == self.owner)
		if thread:
			comments.add_reply(self.name, actor, thread, text)
			return thread
		return comments.add_thread(self.name, actor, ANCHOR, text)

	def seen_by(self, user, variants=(), threads=()):
		return badges.mark(self.name, user, list(variants), list(threads))

	def page(self, user):
		return badges.page(self.name, user)

	def card(self, user):
		return badges.card(self.name, user)

	def mentions_of(self, thread):
		rows = frappe.get_all("Sketch Comment", filters={"prototype": self.name}, fields=["name", "thread", "mentions"])
		return {r.name: json.loads(r.mentions or "[]") for r in rows if (r.thread or r.name) == thread}


class TestVariantsAreNew(BadgeCase):
	def test_a_variant_an_editor_adds_is_new_to_the_owner_and_not_to_its_author(self):
		self.invite(self.ed)
		option = self.add_variant(self.ed)
		self.assertEqual(self.page(self.owner)["variants"], [option])
		self.assertEqual(self.page(self.ed)["variants"], [])

	def test_it_is_new_to_another_editor_too(self):
		self.invite(self.ed, self.ed2)
		option = self.add_variant(self.ed)
		self.assertEqual(self.page(self.ed2)["variants"], [option])

	def test_the_owner_opening_the_set_clears_it_for_the_owner_only(self):
		self.invite(self.ed, self.ed2)
		option = self.add_variant(self.ed)
		self.seen_by(self.owner, variants=[option])
		self.assertEqual(self.page(self.owner)["variants"], [])
		self.assertEqual(self.page(self.ed2)["variants"], [option])

	def test_the_folder_names_the_author_not_the_writer(self):
		self.invite(self.ed)
		self.agent(self.owner, "write_files", files=[{"path": "src/variants/@d2tbged/a.vue", "content": variant("A")}])
		self.agent(self.owner, "commit", prompt="x")
		# The folder names its author, whoever wrote it: the editor's, so it is new to the owner.
		self.assertEqual(self.page(self.owner)["variants"], ["@d2tbged/a"])
		self.assertEqual(self.page(self.ed)["variants"], [])

	def test_a_variant_written_again_is_new_again(self):
		self.invite(self.ed)
		option = self.add_variant(self.ed)
		self.seen_by(self.owner, variants=[option])
		path = f"src/variants/@d2tbged/compact.vue"
		self.agent(self.ed, "delete_file", path=path)
		self.add_variant(self.ed)
		self.assertEqual(self.page(self.owner)["variants"], [option])

	def test_a_file_with_no_stamp_is_never_new(self):
		from sketch import prototype_files

		self.invite(self.ed)
		prototype_files.write_files(self.name, [{"path": "src/variants/@d2tbged/old.vue", "content": variant("Old")}])
		self.assertEqual(self.page(self.owner)["variants"], [])

	def test_a_file_that_declares_no_variant_is_not_one(self):
		self.invite(self.ed)
		self.agent(self.ed, "write_files", files=[{"path": "src/variants/@d2tbged/helper.ts", "content": "export const x = 1\n"}])
		self.assertEqual(self.page(self.owner)["variants"], [])

	def test_a_deleted_variant_is_no_longer_new(self):
		self.invite(self.ed)
		self.add_variant(self.ed)
		self.agent(self.ed, "delete_file", path="src/variants/@d2tbged/compact.vue")
		self.assertEqual(self.page(self.owner)["variants"], [])

	def test_what_was_made_before_an_editor_was_invited_is_not_new_to_them(self):
		self.invite(self.ed)
		option = self.add_variant(self.ed)
		self.invite(self.ed2)
		self.assertEqual(self.page(self.ed2)["variants"], [])
		self.assertEqual(self.page(self.owner)["variants"], [option])

	def test_marking_what_is_not_a_variant_records_nothing(self):
		self.assertEqual(self.seen_by(self.owner, variants=["../../etc/passwd", "wide", 3, ""]), 0)
		self.assertEqual(frappe.db.count("Sketch Seen", {"prototype": self.name}), 0)


class TestCommentsAreNew(BadgeCase):
	def unread(self, user):
		return {t["id"]: t["unread"] for t in self.page(user)["threads"]}

	def test_a_comment_by_somebody_else_is_unread_and_your_own_is_not(self):
		thread = self.say(self.reader)
		self.assertEqual(self.unread(self.owner), {thread: 1})
		self.assertEqual(self.unread(self.reader), {})

	def test_opening_a_thread_marks_it_read_for_that_person_only(self):
		self.invite(self.ed)
		thread = self.say(self.reader)
		self.seen_by(self.owner, threads=[thread])
		self.assertEqual(self.unread(self.owner), {})
		self.assertEqual(self.unread(self.ed), {thread: 1})

	def test_a_new_reply_makes_the_thread_unread_again(self):
		thread = self.say(self.reader)
		self.seen_by(self.owner, threads=[thread])
		self.assertEqual(self.unread(self.owner), {})
		self.say(self.reader, "And another thing", thread=thread)
		self.assertEqual(self.unread(self.owner), {thread: 1})

	def test_your_own_reply_counts_as_reading_everything_before_it(self):
		thread = self.say(self.reader)
		self.say(self.owner, "Agreed", thread=thread)
		self.assertEqual(self.unread(self.owner), {})
		# And the reader, who wrote the first one, now has the owner's reply to read.
		self.assertEqual(self.unread(self.reader), {thread: 1})

	def test_the_owners_own_reply_to_their_own_thread_is_not_new_to_them(self):
		thread = self.say(self.owner, "My note to the room")
		self.say(self.owner, "More", thread=thread)
		self.assertEqual(self.unread(self.owner), {})

	def test_a_thread_marks_only_ids_of_this_prototype(self):
		other = utils.make_prototype(self.owner, "d2t-badges-two", files=FILES, is_public=True)
		self.addCleanup(utils.drop_prototype, other.name)
		actor = comments.Actor(self.username(self.reader), self.reader, False)
		foreign = comments.add_thread(other.name, actor, ANCHOR, "elsewhere")
		self.assertEqual(self.seen_by(self.owner, threads=[foreign, "nope"]), 0)

	def test_comments_carry_unread_and_mentioned_for_the_person_asking(self):
		thread = self.say(self.reader)
		with set_user("Guest"):
			ticket = comments.mint_ticket(self.name, self.username(self.owner))
			door = api.comment_pass(self.name, self.username(self.owner), str(ticket["exp"]), ticket["sig"])
			listed = api.comments_list(self.name, self.username(self.owner), str(door["exp"]), door["sig"])
		row = next(t for t in listed["threads"] if t["id"] == thread)
		self.assertEqual((row["unread"], row["mentioned"]), (1, False))


class TestWhoGetsBadges(BadgeCase):
	def test_a_guest_gets_nothing(self):
		self.say(self.reader)
		self.assertIsNone(badges.page(self.name, "Guest"))
		self.assertIsNone(badges.card(self.name, "Guest"))

	def test_a_signed_in_stranger_who_never_commented_gets_nothing(self):
		self.say(self.reader)
		self.assertIsNone(self.page(self.stranger))
		self.assertIsNone(self.card(self.stranger))

	def test_a_reader_gets_comments_after_their_own_and_no_variants(self):
		self.invite(self.ed)
		first = self.say(self.owner, "Before the reader came")
		mine = self.say(self.reader, "My question")
		self.say(self.owner, "An answer", thread=mine)
		self.add_variant(self.ed)
		page = self.page(self.reader)
		self.assertEqual(page["variants"], [])
		self.assertEqual({t["id"] for t in page["threads"]}, {mine})
		self.assertNotIn(first, {t["id"] for t in page["threads"]})
		self.assertEqual(self.card(self.reader)["variants"], 0)

	def test_a_private_prototype_gives_badges_to_the_owner_and_editors_only(self):
		self.invite(self.ed)
		self.say(self.reader, "While it was public")
		with set_user(self.owner):
			api.set_public(self.doc.slug, False)
		self.assertIsNone(self.page(self.reader))
		self.assertIsNotNone(self.page(self.owner))
		self.assertIsNotNone(self.page(self.ed))

	def test_marking_as_somebody_with_no_standing_is_a_404(self):
		with self.assertRaises(frappe.DoesNotExistError):
			badges.mark(self.name, self.stranger, [], [])
		with self.assertRaises(frappe.DoesNotExistError):
			badges.mark(self.name, "Guest", [], [])


class TestGalleryCard(BadgeCase):
	def test_first_use_has_nothing_to_say(self):
		self.assertIsNone(self.card(self.owner))
		with set_user(self.owner):
			rows = api.list_prototypes()
		self.assertIsNone(next(r for r in rows if r["name"] == self.name)["new"])

	def test_the_counts_are_what_is_unseen(self):
		self.invite(self.ed)
		one = self.add_variant(self.ed, "One")
		self.add_variant(self.ed, "Two")
		a = self.say(self.reader)
		self.say(self.reader, "second", thread=a)
		self.say(self.reader, "other thread")
		card = self.card(self.owner)
		self.assertEqual((card["variants"], card["comments"]), (2, 3))
		self.seen_by(self.owner, variants=[one], threads=[a])
		card = self.card(self.owner)
		self.assertEqual((card["variants"], card["comments"]), (1, 1))

	def test_opening_everything_empties_the_card(self):
		self.invite(self.ed)
		option = self.add_variant(self.ed)
		thread = self.say(self.reader)
		self.seen_by(self.owner, variants=[option], threads=[thread])
		self.assertIsNone(self.card(self.owner))

	def test_the_card_names_who_made_the_new_things_three_at_most(self):
		people = []
		for n in range(10):
			email = utils.make_user(f"bgmany{n}", f"d2tbgmany{n}")
			self.addCleanup(utils.drop_user, email)
			people.append(email)
			self.say(email, f"hello {n}")

		card = self.card(self.owner)
		self.assertEqual(len(card["by"]), 3)
		self.assertEqual(card["more"], 7)
		self.assertEqual(card["comments"], 10)
		# Newest first.
		self.assertEqual(card["by"][0]["username"], "d2tbgmany9")

	def test_the_gallery_row_carries_the_card_for_the_owner_and_for_shared_with_me(self):
		self.invite(self.ed)
		self.add_variant(self.ed)
		with set_user(self.owner):
			mine = next(r for r in api.list_prototypes() if r["name"] == self.name)
		self.assertEqual(mine["new"]["variants"], 1)
		self.assertEqual(mine["new"]["by"][0]["username"], "d2tbged")
		self.say(self.owner, "From the owner")
		with set_user(self.ed):
			shared = next(r for r in api.shared_prototypes() if r["name"] == self.name)
		self.assertEqual((shared["new"]["variants"], shared["new"]["comments"]), (0, 1))

	def test_nothing_is_new_for_the_author_of_everything(self):
		self.invite(self.ed)
		badges.opened(self.name, self.ed)
		self.add_variant(self.ed)
		self.say(self.ed)
		self.assertIsNone(self.card(self.ed))


class TestInvitedAndAdoptedNews(BadgeCase):
	"""Two more lines on the card of someone invited to edit (decision 44)."""

	def open_page(self, user):
		with set_user(user):
			renderer = SketchViewerRenderer(path=f"u/{self.username(self.owner)}/{self.doc.slug}")
			self.assertTrue(renderer.can_render())
			return renderer.render()

	def adopt(self, user, label="Compact"):
		"""The owner makes the editor's option the default: the file moves into the owner's tree and the registry says whose."""
		path = f"src/components/{label}.vue"
		self.agent(self.owner, "write_files", files=[{"path": path, "content": variant(label)}])
		registry = editor_variants.read_registry(self.name)
		registry[path] = {"author": self.username(user), "default": True, "at": str(frappe.utils.now_datetime())}
		editor_variants.write_registry(self.name, registry)
		return path

	def test_an_invited_editor_is_told_who_invited_them_until_they_open_it(self):
		self.invite(self.ed)
		news = self.card(self.ed)
		self.assertEqual(news["invited"]["by"]["username"], self.username(self.owner))
		self.assertEqual((news["variants"], news["comments"]), (0, 0), "the invitation is news on its own")
		self.open_page(self.ed)
		self.assertIsNone(self.card(self.ed))

	def test_the_owner_and_a_reader_are_never_invited(self):
		self.invite(self.ed)
		self.assertIsNone(self.card(self.owner))
		self.say(self.reader)
		self.assertIsNone(self.card(self.reader))

	def test_someone_else_opening_it_is_not_the_editor_opening_it(self):
		self.invite(self.ed)
		self.open_page(self.stranger)
		self.assertIsNotNone(self.card(self.ed)["invited"])
		badges.opened(self.name, self.stranger)
		self.assertIsNotNone(self.card(self.ed)["invited"])

	def test_the_invitation_shows_in_shared_with_me(self):
		self.invite(self.ed)
		with set_user(self.ed):
			row = next(r for r in api.shared_prototypes() if r["name"] == self.name)
		self.assertEqual(row["new"]["invited"]["by"]["username"], self.username(self.owner))

	def test_making_an_editors_option_the_default_is_news_to_that_editor_only(self):
		self.invite(self.ed, self.ed2)
		self.open_page(self.ed)
		self.add_variant(self.ed)
		path = self.adopt(self.ed)
		news = self.card(self.ed)
		self.assertEqual(news["adopted"]["label"], "Compact")
		self.assertEqual(news["adopted"]["by"]["username"], self.username(self.owner))
		self.assertIsNone(self.card(self.owner)["adopted"], "the owner made it")
		self.open_page(self.ed2)
		self.assertIsNone((self.card(self.ed2) or {}).get("adopted"), "another editor's option was not the one")
		self.assertTrue(path)

	def test_opening_the_prototype_clears_it_and_the_next_default_brings_it_back(self):
		self.invite(self.ed)
		self.open_page(self.ed)
		self.adopt(self.ed, "Compact")
		self.assertIsNotNone(self.card(self.ed)["adopted"])
		self.open_page(self.ed)
		self.assertIsNone(self.card(self.ed))
		frappe.db.set_value(
			"Sketch Seen",
			{"prototype": self.name, "user": self.ed, "kind": "Opened"},
			"seen_at",
			frappe.utils.add_to_date(frappe.utils.now_datetime(), minutes=-5),
		)
		self.adopt(self.ed, "Roomy")
		self.assertEqual(self.card(self.ed)["adopted"]["label"], "Roomy", "the newest default leads")

	def test_a_default_that_names_no_time_is_not_news(self):
		self.invite(self.ed)
		self.open_page(self.ed)
		registry = {"src/components/Old.vue": {"author": self.username(self.ed), "default": True}}
		editor_variants.write_registry(self.name, registry)
		self.assertIsNone(self.card(self.ed))


class TestMentions(BadgeCase):
	def setUp(self):
		super().setUp()
		self.invite(self.ed)

	def token(self, user):
		return f"@[{self.username(user)}]"

	def test_a_mention_is_stored_as_the_username_and_the_person_sees_it_on_the_card(self):
		thread = self.say(self.ed, f"{self.token(self.owner)} does this read better?")
		self.assertEqual(self.mentions_of(thread)[thread], ["d2tbgown"])
		card = self.card(self.owner)
		self.assertEqual(card["mention"]["by"]["username"], "d2tbged")
		self.assertEqual(card["mention"]["thread"], thread)
		badges.opened(self.name, self.ed)
		self.assertIsNone(self.card(self.ed))

	def test_the_mention_stays_on_the_card_until_the_thread_is_opened(self):
		thread = self.say(self.ed, f"{self.token(self.owner)} hi")
		self.seen_by(self.owner, threads=[thread])
		self.assertIsNone(self.card(self.owner))

	def test_the_thread_keeps_its_mark_after_it_is_read(self):
		thread = self.say(self.ed, f"{self.token(self.owner)} hi")
		self.seen_by(self.owner, threads=[thread])
		with set_user(self.owner):
			listed = comments.list_threads(self.name)
		badges.decorate(self.name, self.owner, listed)
		self.assertEqual((listed[0]["unread"], listed[0]["mentioned"]), (0, True))

	def test_a_reply_can_mention_too(self):
		thread = self.say(self.reader)
		self.say(self.ed, f"{self.token(self.owner)} and {self.token(self.reader)}", thread=thread)
		replies = [v for k, v in self.mentions_of(thread).items() if k != thread][0]
		self.assertEqual(sorted(replies), ["d2tbgown", "d2tbgrd"])

	def test_only_people_on_the_list_can_be_mentioned(self):
		# The list is the owner, the editors and everyone who has commented here.
		listed = {p["username"] for p in comments.mentionable(self.name)}
		self.assertEqual(listed, {"d2tbgown", "d2tbged"})
		thread = self.say(self.ed, f"{self.token(self.stranger)} and {self.token(self.owner)}")
		self.assertEqual(self.mentions_of(thread)[thread], ["d2tbgown"])
		row = frappe.db.get_value("Sketch Comment", thread, "text")
		self.assertEqual(row, "@d2tbgstr and @[d2tbgown]")

	def test_anybody_who_has_commented_can_be_mentioned_on_a_public_prototype(self):
		self.say(self.reader)
		listed = {p["username"] for p in comments.mentionable(self.name)}
		self.assertEqual(listed, {"d2tbgown", "d2tbged", "d2tbgrd"})
		thread = self.say(self.ed, self.token(self.reader))
		self.assertEqual(self.mentions_of(thread)[thread], ["d2tbgrd"])

	def test_a_private_prototype_limits_mentions_to_the_owner_and_editors(self):
		self.say(self.reader)
		with set_user(self.owner):
			api.set_public(self.doc.slug, False)

		listed = {p["username"] for p in comments.mentionable(self.name)}
		self.assertEqual(listed, {"d2tbgown", "d2tbged"})
		thread = self.say(self.ed, f"{self.token(self.reader)} {self.token(self.owner)}")
		self.assertEqual(self.mentions_of(thread)[thread], ["d2tbgown"])

	def test_plain_at_text_stays_plain(self):
		thread = self.say(self.ed, "@xyz and @d2tbgown, no brackets")
		self.assertEqual(self.mentions_of(thread)[thread], [])
		self.assertEqual(frappe.db.get_value("Sketch Comment", thread, "text"), "@xyz and @d2tbgown, no brackets")

	def test_a_made_up_token_is_stripped_of_its_brackets(self):
		thread = self.say(self.ed, "@[nobody-here] and @[../x]")
		self.assertEqual(self.mentions_of(thread)[thread], [])
		self.assertEqual(frappe.db.get_value("Sketch Comment", thread, "text"), "@nobody-here and @[../x]")

	def test_a_person_is_kept_once_however_often_they_are_named(self):
		thread = self.say(self.ed, f"{self.token(self.owner)} {self.token(self.owner)}")
		self.assertEqual(self.mentions_of(thread)[thread], ["d2tbgown"])

	def test_editing_a_comment_rechecks_its_mentions(self):
		thread = self.say(self.ed, "hello")
		actor = comments.Actor("d2tbged", self.ed, False)
		comments.edit(self.name, actor, thread, f"{self.token(self.owner)} {self.token(self.stranger)}")
		self.assertEqual(self.mentions_of(thread)[thread], ["d2tbgown"])

	def test_the_menu_list_leaves_out_the_person_asking(self):
		with set_user("Guest"):
			ticket = comments.mint_ticket(self.name, "d2tbged")
			door = api.comment_pass(self.name, "d2tbged", str(ticket["exp"]), ticket["sig"])
			listed = api.comments_list(self.name, "d2tbged", str(door["exp"]), door["sig"])
		self.assertEqual([p["username"] for p in listed["mentionable"]], ["d2tbgown"])

	def test_a_mention_reads_as_a_name_in_a_note(self):
		thread = self.say(self.ed, f"{self.token(self.owner)} look")
		actor = comments.Actor("d2tbgown", self.owner, True)
		draft = comments.note_draft(self.name, actor, thread)
		self.assertNotIn("@[", draft["note"])
		self.assertIn("@Sketch Test bgown", draft["note"])

	def test_the_names_of_people_mentioned_reach_the_page(self):
		self.say(self.ed, f"{self.token(self.owner)} look")
		people = comments.people_in(comments.list_threads(self.name))
		self.assertIn("d2tbgown", people)


class TestTheSeenCredential(BadgeCase):
	def credential(self, user, name=None):
		stamp = signature.mint(comments.subject(name or self.name, self.username(user)), 600, signature.SEEN)
		return {"username": self.username(user), "exp": str(stamp["exp"]), "sig": stamp["sig"]}

	def mark(self, user, **fields):
		with set_user("Guest"):
			return api.seen_mark(self.name, **self.credential(user), **fields)

	def test_a_signed_mark_records_what_the_person_saw(self):
		thread = self.say(self.reader)
		done = self.mark(self.owner, threads=json.dumps([thread]), variants="[]")
		self.assertEqual(done["marked"], 1)
		self.assertEqual(self.page(self.owner)["threads"], [])

	def test_the_credential_speaks_for_one_person_and_one_prototype(self):
		thread = self.say(self.reader)
		stolen = self.credential(self.owner)
		with set_user("Guest"):
			with self.assertRaises(frappe.DoesNotExistError):
				api.seen_mark(self.name, **{**stolen, "username": self.username(self.reader)}, threads=json.dumps([thread]))
			with self.assertRaises(frappe.DoesNotExistError):
				api.seen_mark(self.name, **{**stolen, "sig": "0" * 64}, threads=json.dumps([thread]))
			with self.assertRaises(frappe.DoesNotExistError):
				api.seen_mark(self.name, username=self.username(self.owner), exp="", sig="")

		self.assertEqual(len(self.page(self.owner)["threads"]), 1)

	def test_a_comment_pass_does_not_open_it(self):
		stamp = signature.mint(comments.subject(self.name, self.username(self.owner)), 600, signature.COMMENT)
		with set_user("Guest"), self.assertRaises(frappe.DoesNotExistError):
			api.seen_mark(self.name, username=self.username(self.owner), exp=str(stamp["exp"]), sig=stamp["sig"])

	def test_garbage_in_the_lists_marks_nothing_and_does_not_fail(self):
		self.assertEqual(self.mark(self.owner, threads="not json", variants="{}")["marked"], 0)

	def test_a_stranger_with_a_valid_credential_still_gets_a_404(self):
		with set_user("Guest"), self.assertRaises(frappe.DoesNotExistError):
			api.seen_mark(self.name, **self.credential(self.stranger), threads="[]")

	def test_marking_the_same_thing_twice_is_one_row(self):
		thread = self.say(self.reader)
		self.mark(self.owner, threads=json.dumps([thread]))
		self.mark(self.owner, threads=json.dumps([thread]))
		self.assertEqual(frappe.db.count("Sketch Seen", {"prototype": self.name}), 1)


class TestThePage(BadgeCase):
	def payload_for(self, user):
		renderer = SketchViewerRenderer(path=f"u/{self.username(self.owner)}/{self.doc.slug}")
		with set_user(user):
			self.assertTrue(renderer.can_render())
			return renderer.payload()

	def test_the_payload_carries_what_is_new_and_the_right_to_mark_it(self):
		self.invite(self.ed)
		option = self.add_variant(self.ed)
		thread = self.say(self.reader)
		data = self.payload_for(self.owner)
		self.assertEqual(data["badges"]["variants"], [option])
		self.assertEqual([(t["id"], t["route"]) for t in data["badges"]["threads"]], [(thread, "/")])
		self.assertTrue(data["seen_sig"])
		stamp = {"username": self.username(self.owner), "exp": str(data["seen_exp"]), "sig": data["seen_sig"]}
		with set_user("Guest"):
			self.assertEqual(api.seen_mark(self.name, **stamp, threads=json.dumps([thread]))["marked"], 1)

	def test_a_guest_page_carries_nothing(self):
		self.say(self.reader)
		data = self.payload_for("Guest")
		self.assertIsNone(data["badges"])
		self.assertEqual((data["seen_exp"], data["seen_sig"]), ("", ""))

	def test_first_use_carries_empty_lists(self):
		data = self.payload_for(self.owner)
		self.assertEqual(data["badges"], {"variants": [], "threads": []})
