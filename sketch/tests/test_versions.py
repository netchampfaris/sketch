# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""One user request must make one version, and the prompt must survive it.

A version is the unit a person reads back, so it has to match what they asked
for. Four traps sit here:

- One request calls `write_files`, then `edit_file`, then `delete_file`, then
  `commit`. The three write calls only note what changed. `commit` folds the
  notes into one row. A miss writes three versions for one message.
- `commit` clears the pending list. Without that a second call in the same
  request files the same files again under a second version.
- The prompt is stored word for word. A trim, a truncation or an HTML strip
  loses the text the person typed.
- `history` reads with `frappe.get_all`, which checks no permission. The owner
  filter lives in `prototype.resolve_owned`. `if_owner` is per role, so a
  System Manager must be refused there too, the same way the listing was.

The tool calls run through `tools.do_write_files` and friends with real
argument dicts. That is the path an agent takes, and the fold rules only run on
that path.
"""

import frappe
from frappe.tests import IntegrationTestCase

from sketch import api, versions
from sketch.mcp import tools
from sketch.tests import utils

#: The one Prototype every test drives. setUp makes it, tearDown drops it, so
#: no test reads a version another test wrote.
SLUG = "d2t-ver-work"

#: The tree each test starts from. These files are written straight to disk, so
#: they carry no pending change and no version.
SEED = {
	"src/App.vue": "<template><div>hi</div></template>\n",
	"src/one.txt": "one\n",
	"src/two.txt": "two\n",
}

#: A prompt with the shapes a naive store would break: a newline, two spaces, a
#: tab, and the three characters HTML escaping mangles.
VERBATIM = 'Make  the "hero" bigger\n\t& keep <Button> as it is\n'

BLANK_PROMPTS = ("", "   ", "\t", "\n  \t\n")


class TestVersions(IntegrationTestCase):
	#: Every Prototype these tests create. tearDownClass clears them all.
	made: set = set()

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_runtime()
		cls.owner = utils.make_user("verown", "d2tverown")
		cls.other = utils.make_user("veroth", "d2tveroth")

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		for name in cls.made:
			frappe.db.delete(versions.VERSION, {"prototype": name})
			utils.drop_prototype(name)
		for email in (cls.owner, cls.other):
			utils.drop_user(email)
		frappe.db.commit()
		super().tearDownClass()

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self.drop_work()
		self.doc = utils.make_prototype(self.owner, SLUG, files=SEED)
		self.made.add(self.doc.name)
		frappe.set_user(self.owner)

	def tearDown(self):
		frappe.set_user("Administrator")
		self.drop_work()
		super().tearDown()

	# ------------------------------------------------------------- fixtures

	def drop_work(self):
		"""Remove the working Prototype of this test, whoever owns it."""
		for email in (self.owner, self.other):
			name = frappe.db.get_value("Sketch Prototype", {"owner": email, "slug": SLUG}, "name")
			if name:
				frappe.db.delete(versions.VERSION, {"prototype": name})
				utils.drop_prototype(name)

	# ---------------------------------------------------------- tool drivers

	def write(self, files: dict):
		"""One `write_files` call, the way an agent sends it."""
		return tools.do_write_files(
			{
				"prototype": SLUG,
				"files": [{"path": path, "content": body} for path, body in files.items()],
			}
		)

	def edit(self, path, old_string, new_string):
		return tools.do_edit_file(
			{
				"prototype": SLUG,
				"path": path,
				"old_string": old_string,
				"new_string": new_string,
			}
		)

	def delete(self, path):
		return tools.do_delete_file({"prototype": SLUG, "path": path})

	def commit(self, prompt, summary=None):
		args = {"prototype": SLUG, "prompt": prompt}
		if summary is not None:
			args["summary"] = summary

		return tools.do_commit(args)

	# ---------------------------------------------------------------- probes

	def history(self) -> list[dict]:
		return versions.history(self.doc.name)

	def pending(self) -> list[dict]:
		return versions.pending(self.doc.name)

	def only_version(self) -> dict:
		"""The single version of the working Prototype. Fails when there are more."""
		rows = self.history()
		self.assertEqual(len(rows), 1, f"expected one version, got {len(rows)}")
		return rows[0]

	def changes(self) -> list[dict]:
		return self.only_version()["changes"]

	# ------------------------------------------------- one request, one version

	def test_three_tool_calls_then_one_commit_make_one_version(self):
		prompt = "add a hero and drop the old banner"
		self.write({"src/hero.vue": "<template><b/></template>\n"})
		self.edit("src/one.txt", "one", "uno")
		self.delete("src/two.txt")
		self.commit(prompt, summary="added the hero")

		row = self.only_version()
		self.assertEqual(row["sequence"], 1)
		self.assertEqual(row["prompt"], prompt)
		self.assertEqual(row["summary"], "added the hero")
		self.assertEqual(
			row["changes"],
			[
				{"path": "src/hero.vue", "action": versions.ADDED},
				{"path": "src/one.txt", "action": versions.MODIFIED},
				{"path": "src/two.txt", "action": versions.DELETED},
			],
		)
		self.assertEqual((row["files_added"], row["files_modified"], row["files_deleted"]), (1, 1, 1))

	def test_the_write_tools_record_nothing_on_their_own(self):
		self.write({"src/hero.vue": "<template><b/></template>\n"})
		self.edit("src/one.txt", "one", "uno")

		self.assertEqual(self.history(), [])
		self.assertEqual(
			self.pending(),
			[
				{"path": "src/hero.vue", "action": versions.ADDED},
				{"path": "src/one.txt", "action": versions.MODIFIED},
			],
		)

	def test_a_second_request_makes_a_second_version(self):
		self.write({"src/head.txt": "a\n"})
		self.commit("make the header sticky")
		self.write({"src/foot.txt": "b\n"})
		self.commit("now make the footer sticky")

		rows = self.history()
		self.assertEqual(len(rows), 2)
		self.assertEqual([row["sequence"] for row in rows], [2, 1])
		self.assertEqual(
			[row["prompt"] for row in rows],
			["now make the footer sticky", "make the header sticky"],
		)

	def test_history_is_newest_first(self):
		for index, prompt in enumerate(("first ask", "second ask", "third ask")):
			self.write({f"src/step{index}.txt": "x\n"})
			self.commit(prompt)

		rows = self.history()
		self.assertEqual([row["prompt"] for row in rows], ["third ask", "second ask", "first ask"])
		self.assertEqual([row["sequence"] for row in rows], [3, 2, 1])

	# ------------------------------------------------------------- commit clears

	def test_a_commit_clears_the_pending_list(self):
		self.write({"src/hero.txt": "x\n"})
		self.commit("add a hero")

		self.assertEqual(self.pending(), [])

	def test_a_second_commit_records_nothing(self):
		self.write({"src/hero.txt": "x\n"})
		self.commit("add a hero")

		reply = tools.call_tool("commit", {"prototype": SLUG, "prompt": "add a hero"})

		self.assertFalse(reply["isError"], "a no-op commit is not an error")
		self.assertEqual(
			reply["content"][0]["text"], "No file changed since the last version. Nothing recorded."
		)
		self.assertEqual(reply["structuredContent"], {"recorded": False})
		self.assertEqual(len(self.history()), 1)

	def test_a_commit_with_no_change_at_all_records_nothing(self):
		reply = tools.call_tool("commit", {"prototype": SLUG, "prompt": "do nothing"})

		self.assertFalse(reply["isError"])
		self.assertEqual(reply["structuredContent"], {"recorded": False})
		self.assertEqual(self.history(), [])

	def test_a_commit_reports_what_it_recorded(self):
		self.write({"src/a.txt": "a\n", "src/b.txt": "b\n"})
		self.edit("src/one.txt", "one", "uno")

		reply = tools.call_tool("commit", {"prototype": SLUG, "prompt": "add two files"})

		self.assertFalse(reply["isError"])
		self.assertEqual(reply["content"][0]["text"], "Recorded version 1. 2 added, 1 changed, 0 deleted.")
		self.assertEqual(
			reply["structuredContent"],
			{
				"recorded": True,
				"sequence": 1,
				"files_added": 2,
				"files_modified": 1,
				"files_deleted": 0,
				"changes": [
					{"path": "src/a.txt", "action": versions.ADDED},
					{"path": "src/b.txt", "action": versions.ADDED},
					{"path": "src/one.txt", "action": versions.MODIFIED},
				],
			},
		)

	# ------------------------------------------------------------- the fold rules

	def test_added_then_modified_stays_added(self):
		self.write({"src/card.txt": "old\n"})
		self.edit("src/card.txt", "old", "new")
		self.commit("add a card, then fix its title")

		self.assertEqual(self.changes(), [{"path": "src/card.txt", "action": versions.ADDED}])

	def test_added_then_deleted_drops_the_path(self):
		self.write({"src/card.txt": "old\n", "src/keep.txt": "keep\n"})
		self.delete("src/card.txt")
		self.commit("add a card, then take it back")

		self.assertEqual(self.changes(), [{"path": "src/keep.txt", "action": versions.ADDED}])

	def test_modified_then_deleted_becomes_deleted(self):
		self.edit("src/one.txt", "one", "uno")
		self.delete("src/one.txt")
		self.commit("edit the file, then remove it")

		self.assertEqual(self.changes(), [{"path": "src/one.txt", "action": versions.DELETED}])

	def test_deleted_then_added_becomes_modified(self):
		self.delete("src/one.txt")
		self.write({"src/one.txt": "back\n"})
		self.commit("remove the file, then write it again")

		self.assertEqual(self.changes(), [{"path": "src/one.txt", "action": versions.MODIFIED}])

	def test_a_path_keeps_the_position_it_first_appeared_at(self):
		self.edit("src/two.txt", "two", "dos")
		self.edit("src/one.txt", "one", "uno")
		self.delete("src/two.txt")
		self.commit("touch two, then one, then drop two")

		self.assertEqual(
			self.changes(),
			[
				{"path": "src/two.txt", "action": versions.DELETED},
				{"path": "src/one.txt", "action": versions.MODIFIED},
			],
		)

	# ------------------------------------------------------------- the prompt guard

	def test_commit_refuses_a_blank_prompt(self):
		self.write({"src/hero.txt": "x\n"})

		for prompt in BLANK_PROMPTS:
			with self.subTest(prompt=repr(prompt)):
				with self.assertRaises(frappe.ValidationError):
					versions.commit(self.doc, prompt)

		self.assertEqual(self.history(), [])

	def test_the_commit_tool_reports_a_blank_prompt_as_an_error(self):
		self.write({"src/hero.txt": "x\n"})

		for prompt in (None, *BLANK_PROMPTS):
			with self.subTest(prompt=repr(prompt)):
				args = {"prototype": SLUG}
				if prompt is not None:
					args["prompt"] = prompt

				reply = tools.call_tool("commit", args)
				self.assertTrue(reply["isError"], "commit accepted a blank prompt")
				self.assertIn("prompt", reply["content"][0]["text"])

		self.assertEqual(self.history(), [])
		# The refused call leaves the change pending, so the next commit files it.
		self.assertEqual(self.pending(), [{"path": "src/hero.txt", "action": versions.ADDED}])

	# ------------------------------------------------------------- the prompt text

	def test_the_prompt_is_stored_word_for_word(self):
		"""`ignore_xss_filter` on the field is what keeps `<`, `&` and the quote.

		Without it `_sanitize_content` rewrites the prompt on insert, and the
		person reads back text they never typed.
		"""
		self.write({"src/hero.txt": "x\n"})
		self.commit(VERBATIM)

		self.assertEqual(self.only_version()["prompt"], VERBATIM)

	def test_the_spa_returns_the_prompt_word_for_word(self):
		self.write({"src/hero.txt": "x\n"})
		self.commit(VERBATIM)

		rows = api.list_versions(SLUG)
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["prompt"], VERBATIM)

	# ------------------------------------------------------------- the check nudge

	def test_check_names_the_uncommitted_count_until_the_commit(self):
		self.write({"src/hero.txt": "x\n"})
		self.edit("src/one.txt", "one", "uno")

		before = tools.check_text({"status": "ok"}, versions.pending_count(self.doc.name))
		self.assertIn(
			"uncommitted: 2 file(s) changed since the last version. "
			"Call commit with the user's prompt.",
			before,
		)

		self.commit("add a hero")

		after = tools.check_text({"status": "ok"}, versions.pending_count(self.doc.name))
		self.assertNotIn("uncommitted", after)
		self.assertEqual(after, "status: ok")

	# ------------------------------------------------------------- owner scoping

	def test_the_owner_reads_their_own_history(self):
		self.write({"src/page.txt": "x\n"})
		self.commit("add a page")

		rows = api.list_versions(SLUG)
		self.assertEqual([row["sequence"] for row in rows], [1])

	def test_another_user_never_reads_that_history(self):
		self.write({"src/page.txt": "x\n"})
		self.commit("add a page")

		frappe.set_user(self.other)
		with self.assertRaises(frappe.DoesNotExistError):
			api.list_versions(SLUG)

	def test_a_system_manager_never_reads_that_history(self):
		"""`if_owner` is per role, and System Manager does not carry it."""
		self.write({"src/page.txt": "x\n"})
		self.commit("add a page")

		frappe.set_user("Administrator")
		self.assertTrue(frappe.has_permission(versions.VERSION, "read"))
		with self.assertRaises(frappe.DoesNotExistError):
			api.list_versions(SLUG)

	# ------------------------------------------------------------- the cascade

	def test_deleting_a_prototype_deletes_its_versions(self):
		self.write({"src/page.txt": "x\n"})
		self.commit("add a page")
		self.write({"src/page2.txt": "y\n"})
		self.commit("add a second page")
		name = self.doc.name
		self.assertEqual(frappe.db.count(versions.VERSION, {"prototype": name}), 2)

		frappe.set_user("Administrator")
		utils.drop_prototype(name)

		self.assertEqual(frappe.db.count(versions.VERSION, {"prototype": name}), 0)

	# ------------------------------------------------------------- the MCP surface

	def test_the_surface_is_twelve_tools(self):
		"""The eleven, and commit. Nothing else was added with it."""
		self.assertEqual(sorted(tools.TOOLS), sorted(tools.build_tools()))
		self.assertEqual(len(tools.TOOLS), 12)
		self.assertIn("commit", tools.TOOLS)

	def test_commit_requires_the_prototype_and_the_prompt(self):
		parameters = tools.TOOLS["commit"].parameters
		self.assertEqual(sorted(parameters["required"]), ["prompt", "prototype"])
		self.assertIn("summary", parameters["properties"])
		self.assertNotIn("summary", parameters["required"])

	def test_no_write_tool_takes_a_prompt(self):
		for name in ("write_files", "edit_file", "delete_file"):
			with self.subTest(tool=name):
				parameters = tools.TOOLS[name].parameters
				self.assertNotIn("prompt", parameters["properties"])
				self.assertNotIn("prompt", parameters["required"])
