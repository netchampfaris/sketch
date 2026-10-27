# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""Comments: people talking on a live Prototype, apart from the owner's notes.

Every case drives the whitelisted method directly with a pass, the way the
toolbar does, so a wrong pass, a wrong person and a private Prototype all meet
the same door the page meets. Comments are their own rows: nothing here may
reach `get_annotations`, and nothing the agent clears may touch them.
"""

import json
from unittest import mock

import frappe
from frappe.tests import IntegrationTestCase, set_user

from sketch import annotations, api, comments, signature
from sketch.mcp import tools
from sketch.patches.v1_0 import move_reader_notes_to_comments
from sketch.tests import utils
from sketch.viewer import SketchViewerRenderer

FILES = {"src/App.vue": "<template><h1>hello</h1></template>\n"}

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


class CommentCase(IntegrationTestCase):
	"""One public Prototype with an owner and two readers."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_runtime()
		cls.owner = utils.make_user("cmowner", "d2tcmowner")
		cls.addClassCleanup(utils.drop_user, cls.owner)
		cls.reader = utils.make_user("cmreader", "d2tcmreader")
		cls.addClassCleanup(utils.drop_user, cls.reader)
		cls.other = utils.make_user("cmother", "d2tcmother")
		cls.addClassCleanup(utils.drop_user, cls.other)
		cls.owner_name, cls.reader_name, cls.other_name = "d2tcmowner", "d2tcmreader", "d2tcmother"

	def setUp(self):
		super().setUp()
		self.doc = utils.make_prototype(self.owner, "d2t-comments", files=FILES, is_public=True)
		self.addCleanup(utils.drop_prototype, self.doc.name)

	# -- the door, as the toolbar uses it

	def ticket(self, username: str, name: str | None = None) -> dict:
		return comments.mint_ticket(name or self.doc.name, username)

	def pass_for(self, username: str) -> dict:
		t = self.ticket(username)
		with set_user("Guest"):
			return api.comment_pass(self.doc.name, username, str(t["exp"]), t["sig"])

	def call(self, fn, username: str, **fields):
		p = self.pass_for(username)
		with set_user("Guest"):
			return fn(self.doc.name, username, str(p["exp"]), p["sig"], **fields)

	def start(self, username: str, text: str = "Looks off", anchor=None) -> dict:
		return self.call(api.comment_add, username, anchor=json.dumps(ANCHOR if anchor is None else anchor), text=text)

	def rows(self) -> list[str]:
		return frappe.get_all("Sketch Comment", filters={"prototype": self.doc.name}, pluck="name")


class TestPass(CommentCase):
	def test_a_ticket_buys_a_fifteen_minute_pass(self):
		p = self.pass_for(self.reader_name)
		self.assertEqual(p["ttl"], 15 * 60)
		self.assertAlmostEqual(int(p["exp"]) - signature._now(), 15 * 60, delta=5)

	def test_the_pass_expires(self):
		p = self.pass_for(self.reader_name)
		with set_user("Guest"), mock.patch.object(signature, "_now", return_value=int(p["exp"]) + 1):
			with self.assertRaises(frappe.DoesNotExistError):
				api.comments_list(self.doc.name, self.reader_name, str(p["exp"]), p["sig"])

	def test_a_ticket_opens_no_comment_and_a_pass_mints_no_pass(self):
		t = self.ticket(self.reader_name)
		p = self.pass_for(self.reader_name)
		with set_user("Guest"):
			with self.assertRaises(frappe.DoesNotExistError):
				api.comments_list(self.doc.name, self.reader_name, str(t["exp"]), t["sig"])

			with self.assertRaises(frappe.DoesNotExistError):
				api.comment_pass(self.doc.name, self.reader_name, str(p["exp"]), p["sig"])

	def test_a_pass_speaks_for_one_person_on_one_prototype(self):
		p = self.pass_for(self.reader_name)
		other_doc = utils.make_prototype(self.owner, "d2t-comments-two", files=FILES, is_public=True)
		self.addCleanup(utils.drop_prototype, other_doc.name)
		with set_user("Guest"):
			with self.assertRaises(frappe.DoesNotExistError):
				api.comments_list(self.doc.name, self.other_name, str(p["exp"]), p["sig"])

			with self.assertRaises(frappe.DoesNotExistError):
				api.comments_list(other_doc.name, self.reader_name, str(p["exp"]), p["sig"])

	def test_other_scopes_are_not_a_pass(self):
		for scope in (signature.ANNOTATE, signature.REVISION, signature.VIEW):
			with self.subTest(scope=scope):
				mark = signature.mint(comments.subject(self.doc.name, self.reader_name), 600, scope)
				with set_user("Guest"), self.assertRaises(frappe.DoesNotExistError):
					api.comments_list(self.doc.name, self.reader_name, str(mark["exp"]), mark["sig"])

	def test_nobody_gets_a_pass_for_a_name_that_is_not_theirs(self):
		with set_user("Guest"), self.assertRaises(frappe.DoesNotExistError):
			api.comment_pass(self.doc.name, "nobody-here", "1", "x")


class TestPayload(CommentCase):
	def payload(self) -> dict:
		renderer = SketchViewerRenderer(path=f"u/{self.owner_name}/{self.doc.slug}")
		self.assertTrue(renderer.can_render())
		return renderer.payload()

	def test_a_reader_carries_a_ticket_and_never_a_pass_or_a_comment(self):
		self.start(self.other_name, "secret words")
		with set_user(self.reader):
			payload = self.payload()

		self.assertEqual(payload["commenter"], self.reader_name)
		self.assertEqual(payload["comments_open"], 1)
		self.assertIsNone(payload["annotations"], "no notes for a reader")
		self.assertEqual(payload["annotate_sig"], "")
		subject = comments.subject(self.doc.name, self.reader_name)
		args = (subject, payload["comment_exp"], payload["comment_sig"])
		self.assertTrue(signature.verify(*args, signature.COMMENT_MINT))
		self.assertFalse(signature.verify(*args, signature.COMMENT), "the payload holds no pass")
		self.assertNotIn("secret words", json.dumps(payload))

	def test_the_owners_notes_never_reach_a_reader(self):
		annotations.save(self.doc.name, json.dumps({"notes": [{"id": "n1", "note": "mine"}]}), 0)
		with set_user(self.reader):
			self.assertNotIn("mine", json.dumps(self.payload()))

		with set_user(self.owner):
			payload = self.payload()

		self.assertEqual(payload["annotations"]["notes"][0]["note"], "mine")
		self.assertEqual(payload["commenter"], self.owner_name)

	def test_a_guest_is_offered_sign_in_and_nothing_else(self):
		with set_user("Guest"):
			payload = self.payload()

		self.assertTrue(payload["sign_in"])
		self.assertEqual((payload["commenter"], payload["comment_sig"], payload["comments_open"]), ("", "", 0))

	def test_a_private_prototype_offers_nobody_else_anything(self):
		frappe.db.set_value("Sketch Prototype", self.doc.name, "is_public", 0)
		with set_user(self.reader):
			renderer = SketchViewerRenderer(path=f"u/{self.owner_name}/{self.doc.slug}")
			self.assertFalse(renderer.can_render(), "the same 404 as before")


class TestThreads(CommentCase):
	def test_the_server_stamps_the_author(self):
		thread = self.start(self.reader_name, anchor={**ANCHOR, "author": "someone-else", "evil": "x"})
		self.assertEqual(thread["author"], self.reader_name)
		self.assertNotIn("author", thread["anchor"])
		self.assertNotIn("evil", thread["anchor"])
		reply = self.call(api.comment_reply, self.other_name, thread=thread["id"], text="Agreed")
		self.assertEqual([r["author"] for r in reply["replies"]], [self.other_name])

	def test_a_thread_needs_an_element(self):
		for anchor in ({}, {**ANCHOR, "selector": ""}, {**ANCHOR, "route": ""}):
			with self.subTest(anchor=anchor), self.assertRaises(frappe.ValidationError):
				self.start(self.reader_name, anchor=anchor)

	def test_the_list_carries_everyones_threads_and_their_pictures(self):
		self.start(self.reader_name, "one")
		reply_to = self.start(self.other_name, "two")
		self.call(api.comment_reply, self.reader_name, thread=reply_to["id"], text="three")
		listed = self.call(api.comments_list, self.owner_name)
		self.assertEqual(sorted(t["text"] for t in listed["threads"]), ["one", "two"])
		self.assertTrue(listed["is_owner"])
		self.assertEqual(set(listed["people"]), {self.reader_name, self.other_name})
		self.assertEqual(comments.open_count(self.doc.name), 2)

	def test_every_comment_carries_its_authors_full_name(self):
		thread = self.start(self.reader_name, "one")
		after = self.call(api.comment_reply, self.other_name, thread=thread["id"], text="two")
		self.assertEqual(after["name"], "Sketch Test cmreader")
		self.assertEqual(after["replies"][0]["name"], "Sketch Test cmother")

	def test_a_person_with_no_full_name_shows_as_their_username(self):
		thread = self.start(self.reader_name, "one")
		reader = frappe.db.get_value("User", {"username": self.reader_name}, ["name", "full_name"], as_dict=True)
		self.addCleanup(frappe.db.set_value, "User", reader.name, "full_name", reader.full_name)
		frappe.db.set_value("User", reader.name, "full_name", "")
		self.assertEqual(comments.one_thread(self.doc.name, thread["id"])["name"], self.reader_name)

	def test_editing_is_for_the_author_alone_the_owner_included(self):
		thread = self.start(self.reader_name, "mine")
		with self.assertRaises(frappe.PermissionError):
			self.call(api.comment_edit, self.owner_name, comment=thread["id"], text="owner edit")

		with self.assertRaises(frappe.PermissionError):
			self.call(api.comment_edit, self.other_name, comment=thread["id"], text="other edit")

		edited = self.call(api.comment_edit, self.reader_name, comment=thread["id"], text="changed")
		self.assertEqual((edited["text"], edited["edited"]), ("changed", True))

	def test_deleting_is_for_the_author_and_the_owner(self):
		thread = self.start(self.reader_name)
		with self.assertRaises(frappe.PermissionError):
			self.call(api.comment_delete, self.other_name, comment=thread["id"])

		self.assertIsNone(self.call(api.comment_delete, self.reader_name, comment=thread["id"]))
		again = self.start(self.reader_name)
		self.call(api.comment_reply, self.other_name, thread=again["id"], text="reply")
		self.assertEqual(len(self.rows()), 2)
		self.assertIsNone(self.call(api.comment_delete, self.owner_name, comment=again["id"]))
		self.assertEqual(self.rows(), [], "a thread takes its replies with it")

	def test_a_reply_can_be_deleted_alone(self):
		thread = self.start(self.reader_name)
		after = self.call(api.comment_reply, self.other_name, thread=thread["id"], text="reply")
		left = self.call(api.comment_delete, self.other_name, comment=after["replies"][0]["id"])
		self.assertEqual((left["id"], left["replies"]), (thread["id"], []))

	def test_resolving_is_for_the_starter_and_the_owner(self):
		thread = self.start(self.reader_name)
		with self.assertRaises(frappe.PermissionError):
			self.call(api.comment_resolve, self.other_name, thread=thread["id"])

		resolved = self.call(api.comment_resolve, self.reader_name, thread=thread["id"])
		self.assertTrue(resolved["resolved"])
		reopened = self.call(api.comment_resolve, self.owner_name, thread=thread["id"], resolved="0")
		self.assertFalse(reopened["resolved"])
		self.assertTrue(self.call(api.comment_resolve, self.owner_name, thread=thread["id"])["resolved"])
		self.assertEqual(comments.open_count(self.doc.name), 0)

	def test_a_stale_page_cannot_bring_a_deleted_comment_back(self):
		thread = self.start(self.reader_name, "gone soon")
		self.call(api.comment_delete, self.reader_name, comment=thread["id"])
		# A tab that still shows it: every write it can make now meets a 404, and nothing is created.
		attempts = (
			(api.comment_reply, {"thread": thread["id"], "text": "late"}),
			(api.comment_edit, {"comment": thread["id"], "text": "late"}),
			(api.comment_resolve, {"thread": thread["id"]}),
			(api.comment_delete, {"comment": thread["id"]}),
		)
		for fn, fields in attempts:
			with self.subTest(fn=fn.__name__), self.assertRaises(frappe.DoesNotExistError):
				self.call(fn, self.reader_name, **fields)

		self.assertEqual(self.rows(), [])
		self.assertEqual(self.call(api.comments_list, self.reader_name)["threads"], [])

	def test_a_write_only_ever_names_one_comment(self):
		"""No door takes a whole set, so a stale set has nothing to replace."""
		import inspect

		allowed = {"name", "username", "exp", "sig", "anchor", "text", "thread", "comment", "resolved"}
		doors = [n for n in dir(api) if n.startswith("comment_") and n != "comment_pass"]
		self.assertEqual(len(doors), 6)
		for name in doors:
			self.assertLessEqual(set(inspect.signature(getattr(api, name)).parameters), allowed, name)

	def test_an_id_from_another_prototype_is_a_404(self):
		other = utils.make_prototype(self.owner, "d2t-comments-other", files=FILES, is_public=True)
		self.addCleanup(utils.drop_prototype, other.name)
		thread = self.start(self.reader_name)
		p = comments.mint_ticket(other.name, self.owner_name)
		with set_user("Guest"):
			mint = api.comment_pass(other.name, self.owner_name, str(p["exp"]), p["sig"])
			with self.assertRaises(frappe.DoesNotExistError):
				api.comment_delete(other.name, self.owner_name, str(mint["exp"]), mint["sig"], thread["id"])

		self.assertEqual(len(self.rows()), 1)

	def test_every_write_takes_the_prototype_lock_first(self):
		thread = self.start(self.reader_name)
		writes = (
			(api.comment_add, {"anchor": json.dumps(ANCHOR), "text": "a"}),
			(api.comment_reply, {"thread": thread["id"], "text": "b"}),
			(api.comment_edit, {"comment": thread["id"], "text": "c"}),
			(api.comment_resolve, {"thread": thread["id"]}),
			(api.comment_to_note, {"comment": thread["id"]}),
			(api.comment_delete, {"comment": thread["id"]}),
		)
		for fn, fields in writes:
			who = self.owner_name if fn is api.comment_to_note else self.reader_name
			with self.subTest(fn=fn.__name__), mock.patch.object(comments, "_lock", wraps=comments._lock) as lock:
				self.call(fn, who, **fields)
				lock.assert_called_once_with(self.doc.name)

	def test_the_epoch_is_checked_after_the_lock(self):
		"""A page's save waits for the row, then compares: a clear that landed meanwhile is seen."""
		order = []
		real_read, real_epoch = annotations.read, annotations.epoch
		with (
			mock.patch.object(annotations, "read", side_effect=lambda *a, **k: order.append("lock") or real_read(*a, **k)),
			mock.patch.object(annotations, "epoch", side_effect=lambda *a, **k: order.append("epoch") or real_epoch(*a, **k)),
		):
			annotations.save(self.doc.name, json.dumps({"notes": []}), 0)

		self.assertEqual(order[:2], ["lock", "epoch"])


class TestCaps(CommentCase):
	def test_a_comment_is_four_kilobytes_at_most(self):
		exact = "a" * comments.MAX_TEXT_BYTES
		thread = self.start(self.reader_name, exact)
		self.assertEqual(thread["text"], exact, "4 KB wraps in the thread and is stored whole")
		over = exact + "a"
		with self.assertRaises(comments.CommentTooLarge) as caught:
			self.start(self.reader_name, over)

		self.assertEqual(caught.exception.http_status_code, 413)
		with self.assertRaises(comments.CommentTooLarge):
			self.call(api.comment_reply, self.reader_name, thread=thread["id"], text=over)

		with self.assertRaises(comments.CommentTooLarge):
			self.call(api.comment_edit, self.reader_name, comment=thread["id"], text=over)

	def test_the_cap_counts_bytes_not_characters(self):
		with self.assertRaises(comments.CommentTooLarge):
			self.start(self.reader_name, "€" * (comments.MAX_TEXT_BYTES // 3 + 1))

	def test_empty_and_odd_text_is_refused(self):
		for text in ("", "   \n ", "\x00"):
			with self.subTest(text=text), self.assertRaises(frappe.ValidationError):
				self.start(self.reader_name, text)

	def test_a_person_keeps_a_bounded_number_of_threads(self):
		with mock.patch.object(comments, "MAX_THREADS", 3):
			for i in range(3):
				self.start(self.reader_name, f"t{i}")

			with self.assertRaises(comments.TooManyThreads) as caught:
				self.start(self.reader_name, "one too many")

			self.assertEqual(caught.exception.http_status_code, 429)
			self.start(self.other_name, "someone else is unaffected")

	def test_replies_do_not_count_as_threads(self):
		thread = self.start(self.reader_name)
		with mock.patch.object(comments, "MAX_THREADS", 1):
			self.call(api.comment_reply, self.reader_name, thread=thread["id"], text="still fine")

	def test_text_with_angle_brackets_survives_the_http_door(self):
		utils.require_webserver()
		p = self.pass_for(self.reader_name)
		form = {
			"name": self.doc.name,
			"username": self.reader_name,
			"exp": str(p["exp"]),
			"sig": p["sig"],
			"anchor": json.dumps(ANCHOR),
			"text": "Use <Badge> & <b>bold</b>",
		}
		frappe.db.commit()  # the web server reads through its own connection
		response = utils.request("POST", "/api/method/sketch.api.comment_add", data=form)
		self.assertEqual(response.status_code, 200, response.text)
		self.assertEqual(response.json()["message"]["text"], "Use <Badge> & <b>bold</b>")
		self.assertEqual(response.headers["Access-Control-Allow-Origin"], "*")
		self.assertNotIn("Access-Control-Allow-Credentials", response.headers)
		frappe.db.rollback()


class TestPrivate(CommentCase):
	def test_a_reader_loses_comments_at_once_and_gets_them_back(self):
		thread = self.start(self.reader_name, "still here")
		p = self.pass_for(self.reader_name)
		frappe.db.set_value("Sketch Prototype", self.doc.name, "is_public", 0)
		with set_user("Guest"):
			for fn, fields in (
				(api.comments_list, {}),
				(api.comment_add, {"anchor": json.dumps(ANCHOR), "text": "x"}),
				(api.comment_reply, {"thread": thread["id"], "text": "x"}),
				(api.comment_delete, {"comment": thread["id"]}),
			):
				with self.subTest(fn=fn.__name__), self.assertRaises(frappe.DoesNotExistError):
					fn(self.doc.name, self.reader_name, str(p["exp"]), p["sig"], **fields)

			t = self.ticket(self.reader_name)
			with self.assertRaises(frappe.DoesNotExistError):
				api.comment_pass(self.doc.name, self.reader_name, str(t["exp"]), t["sig"])

		self.assertEqual(self.rows(), [thread["id"]], "hidden, not deleted")
		seen = self.call(api.comments_list, self.owner_name)
		self.assertEqual([t["id"] for t in seen["threads"]], [thread["id"]], "the owner keeps seeing them")
		frappe.db.set_value("Sketch Prototype", self.doc.name, "is_public", 1)
		again = self.call(api.comments_list, self.reader_name)
		self.assertEqual([t["id"] for t in again["threads"]], [thread["id"]])


class TestAddToNotes(CommentCase):
	def test_only_the_owner_copies_a_comment_into_notes(self):
		thread = self.start(self.reader_name, "Labels are hard to scan")
		with self.assertRaises(frappe.PermissionError):
			self.call(api.comment_to_note, self.reader_name, comment=thread["id"])

		self.assertEqual(annotations.read(self.doc.name)["notes"], [])
		note = self.call(api.comment_to_note, self.owner_name, comment=thread["id"])
		self.assertEqual(note["note"], "Sketch Test cmreader: “Labels are hard to scan”")
		self.assertEqual((note["selector"], note["route"]), (ANCHOR["selector"], ANCHOR["route"]))
		self.assertNotIn("author", note)
		stored = annotations.read(self.doc.name)["notes"]
		self.assertEqual([n["id"] for n in stored], [note["id"]])
		self.assertEqual(len(self.rows()), 1, "the comment stays where it is")

	def test_a_reply_is_credited_to_its_own_author_on_the_threads_element(self):
		thread = self.start(self.reader_name, "first")
		after = self.call(api.comment_reply, self.other_name, thread=thread["id"], text="second")
		note = self.call(api.comment_to_note, self.owner_name, comment=after["replies"][0]["id"])
		self.assertTrue(note["note"].startswith("Sketch Test cmother: "))
		self.assertEqual(note["selector"], ANCHOR["selector"])


class TestComments_vs_Annotations(CommentCase):
	def setUp(self):
		super().setUp()
		annotations.save(self.doc.name, json.dumps({"notes": [{"id": "n1", "route": "/", "note": "own"}]}), 0)
		self.start(self.reader_name, "a comment")
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user(self.owner)

	def test_get_annotations_never_returns_a_comment(self):
		reply = tools.call_tool("get_annotations", {"prototype": self.doc.slug})
		text = json.dumps(reply["structuredContent"])
		self.assertNotIn("a comment", text)
		self.assertNotIn(self.reader_name, text)
		self.assertEqual([n["id"] for n in reply["structuredContent"]["notes"]], ["n1"])

	def test_clear_annotations_keeps_every_comment(self):
		tools.call_tool("clear_annotations", {"prototype": self.doc.slug})
		self.assertEqual(annotations.read(self.doc.name)["notes"], [])
		self.assertEqual(len(self.rows()), 1)
		tools.call_tool("clear_annotations", {"prototype": self.doc.slug, "ids": ["n1"]})
		self.assertEqual(len(self.rows()), 1)

	def test_the_owner_cannot_sign_a_note_as_somebody_else(self):
		annotations.save(self.doc.name, json.dumps({"notes": [{"id": "n2", "author": self.reader_name}]}), 0)
		self.assertNotIn("author", annotations.read(self.doc.name)["notes"][0])

	def test_deleting_a_prototype_deletes_its_comments(self):
		doc = utils.make_prototype(self.owner, "d2t-comments-doomed", files=FILES, is_public=True)
		comments._insert(doc.name, self.reader_name, "bye", anchor="{}")
		utils.drop_prototype(doc.name)
		self.assertEqual(frappe.db.count("Sketch Comment", {"prototype": doc.name}), 0)


class TestMigration(CommentCase):
	def test_reader_notes_become_comments_and_owner_notes_stay(self):
		mine = {"id": "own1", "route": "/", "selector": "#a", "note": "owner note", "offset": {}, "rect": {}}
		theirs = {
			**mine,
			"id": "r1",
			"selector": "#kpi",
			"note": "Reader note",
			"author": self.reader_name,
			"createdAt": 1793100000000,
			"offset": {"x": 0.1, "y": 0.2},
			"rect": {"x": 1, "y": 2, "w": 3, "h": 4},
		}
		frappe.db.set_value("Sketch Prototype", self.doc.name, "annotations", json.dumps({"notes": [mine, theirs]}))
		move_reader_notes_to_comments.execute()
		threads = comments.list_threads(self.doc.name)
		self.assertEqual([(t["author"], t["text"]) for t in threads], [(self.reader_name, "Reader note")])
		self.assertEqual(threads[0]["anchor"]["selector"], "#kpi")
		self.assertEqual(threads[0]["anchor"]["offset"], {"x": 0.1, "y": 0.2})
		self.assertEqual(threads[0]["ts"], 1793100000, "the time it was written")
		self.assertEqual([n["id"] for n in annotations.read(self.doc.name)["notes"]], ["own1"])
		move_reader_notes_to_comments.execute()
		self.assertEqual(len(comments.list_threads(self.doc.name)), 1, "a second run adds nothing")

	def test_no_stored_note_still_carries_an_author(self):
		for raw in frappe.get_all("Sketch Prototype", pluck="annotations"):
			notes = json.loads(raw).get("notes", []) if raw else []
			self.assertFalse([n for n in notes if isinstance(n, dict) and n.get("author")])
