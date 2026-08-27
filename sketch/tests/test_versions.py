# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""One user request must make one version, and the prompt must survive it.

A version is the unit a person reads back, so it has to match what they asked
for. Three traps sit here:

- One request calls `write_files`, then `edit_file`, then `delete_file`. Each
  call records at once, so all three must fold into one row. A miss writes
  three versions for one message.
- The prompt is stored word for word. A trim, a truncation or an HTML strip
  loses the text the person typed.
- `history` reads with `frappe.get_all`, which checks no permission. The owner
  filter lives in `prototype.resolve_owned`. `if_owner` is per role, so a
  System Manager must be refused there too, the same way the listing was.

The tool calls run through `tools.do_write_files` and friends with real
argument dicts. That is the path an agent takes, and the fold rules only run on
that path.
"""

import os

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_to_date, now_datetime

from sketch import api, prototype_files, versions
from sketch.mcp import tools
from sketch.tests import utils

#: The one Prototype every test drives. setUp makes it, tearDown drops it, so
#: no test reads a version another test wrote.
SLUG = "d2t-ver-work"

#: The tree each test starts from. These files are written straight to disk, so
#: they carry no version of their own.
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
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_runtime()
		cls.owner = utils.make_user("verown", "d2tverown")
		cls.other = utils.make_user("veroth", "d2tveroth")

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		for email in (cls.owner, cls.other):
			utils.drop_user(email)
		super().tearDownClass()

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self.drop_work()
		self.doc = utils.make_prototype(self.owner, SLUG, files=SEED)
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
				utils.drop_prototype(name)

	# ---------------------------------------------------------- tool drivers

	def write(self, prompt, files: dict):
		"""One `write_files` call, the way an agent sends it."""
		return tools.do_write_files(
			{
				"prototype": SLUG,
				"prompt": prompt,
				"files": [{"path": path, "content": body} for path, body in files.items()],
			}
		)

	def edit(self, prompt, path, old_string, new_string):
		return tools.do_edit_file(
			{
				"prototype": SLUG,
				"prompt": prompt,
				"path": path,
				"old_string": old_string,
				"new_string": new_string,
			}
		)

	def delete(self, prompt, path):
		return tools.do_delete_file({"prototype": SLUG, "prompt": prompt, "path": path})

	# ---------------------------------------------------------------- probes

	def history(self) -> list[dict]:
		return versions.history(self.doc.name)

	def only_version(self) -> dict:
		"""The single version of the working Prototype. Fails when there are more."""
		rows = self.history()
		self.assertEqual(len(rows), 1, f"expected one version, got {len(rows)}")
		return rows[0]

	def changes(self) -> list[dict]:
		return self.only_version()["changes"]

	def on_disk(self, path: str) -> str:
		return prototype_files.safe_join(self.doc.name, path)

	def content(self, path: str) -> str:
		with open(self.on_disk(path), encoding="utf-8") as handle:
			return handle.read()

	def age_version(self, name: str, minutes: int) -> None:
		"""Push one version's `creation` that many minutes into the past."""
		stamp = add_to_date(now_datetime(), minutes=-minutes)
		frappe.db.set_value(versions.VERSION, name, "creation", stamp, update_modified=False)
		frappe.db.commit()

	# ------------------------------------------------------- one request, one version

	def test_three_tool_calls_under_one_prompt_make_one_version(self):
		prompt = "add a hero and drop the old banner"
		self.write(prompt, {"src/hero.vue": "<template><b/></template>\n"})
		self.edit(prompt, "src/one.txt", "one", "uno")
		self.delete(prompt, "src/two.txt")

		row = self.only_version()
		self.assertEqual(row["sequence"], 1)
		self.assertEqual(row["prompt"], prompt)
		self.assertEqual(
			row["changes"],
			[
				{"path": "src/hero.vue", "action": versions.ADDED},
				{"path": "src/one.txt", "action": versions.MODIFIED},
				{"path": "src/two.txt", "action": versions.DELETED},
			],
		)
		self.assertEqual((row["files_added"], row["files_modified"], row["files_deleted"]), (1, 1, 1))

	def test_a_different_prompt_starts_a_second_version(self):
		self.write("make the header sticky", {"src/head.txt": "a\n"})
		self.write("now make the footer sticky", {"src/foot.txt": "b\n"})

		rows = self.history()
		self.assertEqual(len(rows), 2)
		self.assertEqual([row["sequence"] for row in rows], [2, 1])
		self.assertEqual(
			[row["prompt"] for row in rows],
			["now make the footer sticky", "make the header sticky"],
		)

	def test_history_is_newest_first(self):
		for index, prompt in enumerate(("first ask", "second ask", "third ask")):
			self.write(prompt, {f"src/step{index}.txt": "x\n"})

		rows = self.history()
		self.assertEqual([row["prompt"] for row in rows], ["third ask", "second ask", "first ask"])
		self.assertEqual([row["sequence"] for row in rows], [3, 2, 1])

	# ------------------------------------------------------------- the fold rules

	def test_added_then_modified_stays_added(self):
		prompt = "add a card, then fix its title"
		self.write(prompt, {"src/card.txt": "old\n"})
		self.edit(prompt, "src/card.txt", "old", "new")

		self.assertEqual(self.changes(), [{"path": "src/card.txt", "action": versions.ADDED}])

	def test_added_then_deleted_drops_the_path(self):
		prompt = "add a card, then take it back"
		self.write(prompt, {"src/card.txt": "old\n", "src/keep.txt": "keep\n"})
		self.delete(prompt, "src/card.txt")

		self.assertEqual(self.changes(), [{"path": "src/keep.txt", "action": versions.ADDED}])

	def test_modified_then_deleted_becomes_deleted(self):
		prompt = "edit the file, then remove it"
		self.edit(prompt, "src/one.txt", "one", "uno")
		self.delete(prompt, "src/one.txt")

		self.assertEqual(self.changes(), [{"path": "src/one.txt", "action": versions.DELETED}])

	def test_deleted_then_added_becomes_modified(self):
		prompt = "remove the file, then write it again"
		self.delete(prompt, "src/one.txt")
		self.write(prompt, {"src/one.txt": "back\n"})

		self.assertEqual(self.changes(), [{"path": "src/one.txt", "action": versions.MODIFIED}])

	def test_a_path_keeps_the_position_it_first_appeared_at(self):
		prompt = "touch two, then one, then drop two"
		self.edit(prompt, "src/two.txt", "two", "dos")
		self.edit(prompt, "src/one.txt", "one", "uno")
		self.delete(prompt, "src/two.txt")

		self.assertEqual(
			self.changes(),
			[
				{"path": "src/two.txt", "action": versions.DELETED},
				{"path": "src/one.txt", "action": versions.MODIFIED},
			],
		)

	# ------------------------------------------------------------- the prompt guard

	def test_every_write_tool_reports_a_missing_prompt_as_an_error(self):
		calls = {
			"write_files": {"prototype": SLUG, "files": [{"path": "src/ghost.txt", "content": "x\n"}]},
			"edit_file": {
				"prototype": SLUG,
				"path": "src/one.txt",
				"old_string": "one",
				"new_string": "uno",
			},
			"delete_file": {"prototype": SLUG, "path": "src/one.txt"},
		}
		for name, args in calls.items():
			with self.subTest(tool=name):
				reply = tools.call_tool(name, args)
				self.assertTrue(reply["isError"], f"{name} accepted a call with no prompt")
				self.assertIn("prompt", reply["content"][0]["text"])

		self.assertEqual(self.history(), [])

	def test_every_write_tool_reports_a_blank_prompt_as_an_error(self):
		for prompt in BLANK_PROMPTS:
			for name, args in (
				(
					"write_files",
					{"files": [{"path": "src/ghost.txt", "content": "x\n"}]},
				),
				(
					"edit_file",
					{"path": "src/one.txt", "old_string": "one", "new_string": "uno"},
				),
				("delete_file", {"path": "src/one.txt"}),
			):
				with self.subTest(tool=name, prompt=repr(prompt)):
					reply = tools.call_tool(name, {"prototype": SLUG, "prompt": prompt, **args})
					self.assertTrue(reply["isError"], f"{name} accepted a blank prompt")

		self.assertEqual(self.history(), [])

	def test_a_missing_prompt_leaves_every_file_alone(self):
		before = self.content("src/one.txt")

		tools.call_tool(
			"write_files", {"prototype": SLUG, "files": [{"path": "src/ghost.txt", "content": "x\n"}]}
		)
		tools.call_tool(
			"edit_file",
			{"prototype": SLUG, "path": "src/one.txt", "old_string": "one", "new_string": "uno"},
		)
		tools.call_tool("delete_file", {"prototype": SLUG, "path": "src/two.txt"})

		self.assertFalse(os.path.exists(self.on_disk("src/ghost.txt")), "write_files wrote a file")
		self.assertEqual(self.content("src/one.txt"), before, "edit_file changed a file")
		self.assertTrue(os.path.isfile(self.on_disk("src/two.txt")), "delete_file removed a file")

	# ------------------------------------------------------------- the prompt text

	def test_the_prompt_is_stored_word_for_word(self):
		self.write(VERBATIM, {"src/hero.txt": "x\n"})

		self.assertEqual(self.only_version()["prompt"], VERBATIM)

	def test_a_prompt_with_markup_still_makes_one_version(self):
		"""The fold compares the stored prompt with the sent one, character for
		character. A prompt that does not round-trip cannot ever match, so every
		call of the request writes its own version."""
		self.write(VERBATIM, {"src/hero.txt": "x\n"})
		self.edit(VERBATIM, "src/one.txt", "one", "uno")
		self.delete(VERBATIM, "src/two.txt")

		self.assertEqual(len(self.history()), 1)

	def test_the_spa_returns_the_prompt_word_for_word(self):
		self.write(VERBATIM, {"src/hero.txt": "x\n"})

		rows = api.list_versions(SLUG)
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["prompt"], VERBATIM)

	# ------------------------------------------------------------- the merge window

	def test_the_same_prompt_after_the_merge_window_starts_a_new_version(self):
		prompt = "make the sidebar collapsible"
		self.write(prompt, {"src/side.txt": "a\n"})
		first = self.only_version()

		past = int(versions.MERGE_WINDOW.total_seconds() / 60) + 15
		self.age_version(first["name"], past)

		self.write(prompt, {"src/side2.txt": "b\n"})

		rows = self.history()
		self.assertEqual(len(rows), 2, "the aged version was appended to, not superseded")
		self.assertEqual([row["sequence"] for row in rows], [2, 1])
		self.assertEqual(rows[0]["changes"], [{"path": "src/side2.txt", "action": versions.ADDED}])
		self.assertEqual(rows[1]["changes"], [{"path": "src/side.txt", "action": versions.ADDED}])

	def test_the_same_prompt_inside_the_merge_window_joins_the_version(self):
		"""The positive control. A window that never merges is not a window."""
		prompt = "make the sidebar collapsible"
		self.write(prompt, {"src/side.txt": "a\n"})
		self.age_version(self.only_version()["name"], 5)

		self.write(prompt, {"src/side2.txt": "b\n"})

		self.assertEqual(
			self.changes(),
			[
				{"path": "src/side.txt", "action": versions.ADDED},
				{"path": "src/side2.txt", "action": versions.ADDED},
			],
		)

	# ------------------------------------------------------------- owner scoping

	def test_the_owner_reads_their_own_history(self):
		self.write("add a page", {"src/page.txt": "x\n"})

		rows = api.list_versions(SLUG)
		self.assertEqual([row["sequence"] for row in rows], [1])

	def test_another_user_never_reads_that_history(self):
		self.write("add a page", {"src/page.txt": "x\n"})

		frappe.set_user(self.other)
		with self.assertRaises(frappe.DoesNotExistError):
			api.list_versions(SLUG)

	def test_a_system_manager_never_reads_that_history(self):
		"""`if_owner` is per role, and System Manager does not carry it."""
		self.write("add a page", {"src/page.txt": "x\n"})

		frappe.set_user("Administrator")
		self.assertTrue(frappe.has_permission(versions.VERSION, "read"))
		with self.assertRaises(frappe.DoesNotExistError):
			api.list_versions(SLUG)

	# ------------------------------------------------------------- the cascade

	def test_deleting_a_prototype_deletes_its_versions(self):
		self.write("add a page", {"src/page.txt": "x\n"})
		self.write("add a second page", {"src/page2.txt": "y\n"})
		name = self.doc.name
		self.assertEqual(frappe.db.count(versions.VERSION, {"prototype": name}), 2)

		frappe.set_user("Administrator")
		utils.drop_prototype(name)

		self.assertEqual(frappe.db.count(versions.VERSION, {"prototype": name}), 0)

	# ------------------------------------------------------------- the MCP surface

	def test_the_surface_is_still_eleven_tools(self):
		"""No twelfth tool. The prompt rides on the write tools, not on a new one."""
		self.assertEqual(sorted(tools.TOOLS), sorted(tools.build_tools()))
		self.assertEqual(len(tools.TOOLS), 11)

	def test_every_write_tool_declares_prompt_as_required(self):
		for name in ("write_files", "edit_file", "delete_file"):
			with self.subTest(tool=name):
				parameters = tools.TOOLS[name].parameters
				self.assertIn("prompt", parameters["properties"])
				self.assertIn("prompt", parameters["required"])
