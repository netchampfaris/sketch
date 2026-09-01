# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""Write quotas: one account cannot grow a tree, or a tree count, without end.

`write_files` used to write whatever it was given. A 25 MB body of one-byte
entries made hundreds of thousands of files in one request, and every reader of
a public tree (`viewer.payload`, `api.export_prototype`) loads the whole tree
into memory. Capping the write path is what bounds both.

The pre-flight is the point. It measures the whole batch before the first
`open()`, so a batch that breaks a quota writes no file at all. Each case here
asserts both halves: the call raises, and the tree on disk is unchanged.

The file counters alone left one hole open: depth. `_walk` yields files only,
so a directory was never counted, never sized and never capped, and
`delete_file` left every directory behind. 20 one-byte files at depth 800 made
16,020 directories and 63 MB that the tree quotas did not see, and deleting the
20 files put the count back to zero with the 63 MB still on disk. The tree
shape cases below hold that shut: depth and segment length in `safe_join`, a
folder count in `preflight`, and a prune in `delete_file`.

The last two cases are the path disclosure (3.10). A refused write must name
the relative path only, and a failed `open()` must not put the bench root in a
tool reply.
"""

import os
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from sketch import prototype, prototype_files
from sketch.mcp import tools
from sketch.tests import utils

#: The one Prototype every case drives. setUp makes it, tearDown drops it.
SLUG = "d2t-quota"

#: The tree each case starts from.
SEED = {"src/App.vue": "<template><div/></template>\n"}


class TestWriteQuotas(IntegrationTestCase):
	#: Every Prototype these cases create. tearDownClass clears them all.
	made: set = set()

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_runtime()
		cls.owner = utils.make_user("quota", "d2tquota")

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		for name in cls.made:
			utils.drop_prototype(name)
		utils.drop_user(cls.owner)
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
		name = frappe.db.get_value("Sketch Prototype", {"owner": self.owner, "slug": SLUG}, "name")
		if name:
			utils.drop_prototype(name)

	def write(self, files: dict):
		return prototype_files.write_files(
			self.doc.name, [{"path": path, "content": content} for path, content in files.items()]
		)

	def paths(self) -> list[str]:
		return [row["path"] for row in prototype_files.list_files(self.doc.name)]

	def base(self) -> str:
		return prototype_files.prototype_dir(self.doc.name)

	def folders(self) -> list[str]:
		return sorted(prototype_files._walk_dirs(self.doc.name))

	def assert_tree_is_the_seed(self):
		self.assertEqual(self.paths(), sorted(SEED))

	def assert_only_the_seed_folders(self):
		"""The seed is `src/App.vue`, so `src` is the one folder that belongs."""
		self.assertEqual(self.folders(), [os.path.join(self.base(), "src")])

	# ------------------------------------------------------------ the batch

	def test_a_batch_over_the_file_count_is_refused(self):
		files = {f"src/f{index}.txt": "x\n" for index in range(prototype_files.MAX_BATCH_FILES + 1)}

		with self.assertRaises(frappe.ValidationError):
			self.write(files)

		self.assert_tree_is_the_seed()

	def test_a_batch_at_the_file_count_is_written(self):
		"""The positive control. A guard that refuses everything is not a guard."""
		files = {f"src/f{index}.txt": "x\n" for index in range(prototype_files.MAX_BATCH_FILES)}

		self.write(files)

		self.assertEqual(len(self.paths()), prototype_files.MAX_BATCH_FILES + len(SEED))

	# ------------------------------------------------------------- one file

	def test_a_file_over_the_byte_limit_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			self.write({"src/big.txt": "x" * (prototype_files.MAX_FILE_BYTES + 1)})

		self.assert_tree_is_the_seed()

	def test_the_limit_counts_encoded_bytes_and_not_characters(self):
		"""One character is three bytes here, so a character count would pass."""
		with self.assertRaises(frappe.ValidationError):
			self.write({"src/big.txt": "中" * (prototype_files.MAX_FILE_BYTES // 2)})

		self.assert_tree_is_the_seed()

	def test_a_refused_batch_writes_no_file_at_all(self):
		"""The pre-flight. A per-entry check would leave the good file behind."""
		with self.assertRaises(frappe.ValidationError):
			self.write(
				{
					"src/good.txt": "small\n",
					"src/big.txt": "x" * (prototype_files.MAX_FILE_BYTES + 1),
				}
			)

		self.assert_tree_is_the_seed()

	# ------------------------------------------------------------- the tree

	def test_the_tree_file_count_is_capped(self):
		batch = prototype_files.MAX_BATCH_FILES
		for start in range(len(SEED), prototype_files.MAX_TREE_FILES, batch):
			count = min(batch, prototype_files.MAX_TREE_FILES - start)
			self.write({f"src/f{start + index}.txt": "x\n" for index in range(count)})

		self.assertEqual(len(self.paths()), prototype_files.MAX_TREE_FILES)

		with self.assertRaises(frappe.ValidationError):
			self.write({"src/one-too-many.txt": "x\n"})

		self.assertEqual(len(self.paths()), prototype_files.MAX_TREE_FILES)

	def test_the_tree_byte_total_is_capped(self):
		self.fill_to_the_byte_cap()

		with self.assertRaises(frappe.ValidationError):
			self.write({"src/one-too-many.txt": "x\n"})

		self.assertNotIn("src/one-too-many.txt", self.paths())

	def test_an_overwrite_is_not_counted_twice(self):
		"""The tree is full. Replacing a file with one the same size still fits.

		Without the subtraction the projection adds the new file to a tree that
		still holds the old one, and every rewrite of a full tree is refused.
		"""
		self.fill_to_the_byte_cap()

		self.write({"src/big0.txt": "y" * prototype_files.MAX_FILE_BYTES})

		self.assertEqual(
			prototype_files.read_files(self.doc.name, ["src/big0.txt"])[0]["content"][:1], "y"
		)

	def fill_to_the_byte_cap(self):
		"""Write files until the tree holds exactly MAX_TREE_BYTES."""
		size = prototype_files.MAX_FILE_BYTES
		room = prototype_files.MAX_TREE_BYTES - self.tree_bytes()
		files = {f"src/big{index}.txt": "x" * size for index in range(room // size)}
		if room % size:
			files[f"src/big{room // size}.txt"] = "x" * (room % size)

		self.write(files)
		self.assertEqual(self.tree_bytes(), prototype_files.MAX_TREE_BYTES)

	def tree_bytes(self) -> int:
		return sum(row["size"] for row in prototype_files.list_files(self.doc.name))

	# -------------------------------------------------------- the tree shape

	def deep_path(self, folders: int) -> str:
		"""A path with `folders` folders and one file at the bottom."""
		return "/".join(f"d{index}" for index in range(folders)) + "/f.txt"

	def test_a_path_deeper_than_the_cap_is_refused(self):
		"""Depth is what the file counters miss. One path made 800 folders."""
		with self.assertRaises(frappe.ValidationError):
			self.write({self.deep_path(prototype_files.MAX_PATH_DEPTH): "x\n"})

		self.assert_tree_is_the_seed()
		self.assert_only_the_seed_folders()

	def test_a_path_at_the_depth_cap_is_written(self):
		"""The positive control. The cap is far above any real Prototype."""
		path = self.deep_path(prototype_files.MAX_PATH_DEPTH - 1)

		self.write({path: "x\n"})

		self.assertIn(path, self.paths())

	def test_every_read_path_is_capped_too(self):
		"""`safe_join` is the one door, so a deep path is refused everywhere."""
		deep = self.deep_path(prototype_files.MAX_PATH_DEPTH)

		with self.assertRaises(frappe.ValidationError):
			prototype_files.safe_join(self.doc.name, deep)

	def test_a_segment_longer_than_the_cap_is_refused(self):
		"""Depth is one way to spend inodes. A 4000 byte name is the other."""
		name = "a" * (prototype_files.MAX_SEGMENT_BYTES + 1)

		with self.assertRaises(frappe.ValidationError):
			self.write({f"src/{name}.vue": "x\n"})

		self.assert_tree_is_the_seed()

	def test_the_segment_cap_counts_encoded_bytes_and_not_characters(self):
		"""One character is three bytes here, so a character count would pass."""
		name = "中" * prototype_files.MAX_SEGMENT_BYTES

		with self.assertRaises(frappe.ValidationError):
			self.write({f"src/{name}": "x\n"})

		self.assert_tree_is_the_seed()

	def test_a_refused_path_never_names_the_bench_root(self):
		with self.assertRaises(frappe.ValidationError) as caught:
			self.write({self.deep_path(prototype_files.MAX_PATH_DEPTH): "x\n"})

		self.assertNotIn(self.base(), str(caught.exception))

	def test_the_tree_folder_count_is_capped(self):
		"""One batch under the file and byte caps, over the folder cap.

		`src` plus one folder per file is MAX_TREE_DIRS + 1 folders, while the
		batch stays at MAX_BATCH_FILES files and a few hundred bytes.
		"""
		files = {f"src/d{index}/f.txt": "x\n" for index in range(prototype_files.MAX_TREE_DIRS)}
		self.assertLessEqual(len(files), prototype_files.MAX_BATCH_FILES)

		with self.assertRaises(frappe.ValidationError):
			self.write(files)

		self.assert_tree_is_the_seed()
		self.assert_only_the_seed_folders()

	def test_a_tree_at_the_folder_cap_is_written(self):
		"""The positive control for the folder cap."""
		files = {f"src/d{index}/f.txt": "x\n" for index in range(prototype_files.MAX_TREE_DIRS - 1)}

		self.write(files)

		self.assertEqual(len(self.folders()), prototype_files.MAX_TREE_DIRS)

	def test_the_folder_cap_counts_the_folders_already_on_disk(self):
		"""Two batches, each legal alone. The second sees the first's folders."""
		half = prototype_files.MAX_TREE_DIRS // 2 + 1
		self.write({f"src/a{index}/f.txt": "x\n" for index in range(half)})

		with self.assertRaises(frappe.ValidationError):
			self.write({f"src/b{index}/f.txt": "x\n" for index in range(half)})

		self.assertEqual(len(self.folders()), half + 1)

	# ------------------------------------------------------- delete and prune

	def test_deleting_the_last_file_removes_the_folders_it_leaves_empty(self):
		self.write({"src/a/b/c/deep.txt": "x\n"})

		prototype_files.delete_file(self.doc.name, "src/a/b/c/deep.txt")

		self.assertFalse(os.path.exists(os.path.join(self.base(), "src", "a")))
		self.assert_only_the_seed_folders()
		self.assert_tree_is_the_seed()

	def test_a_prune_stops_at_the_prototype_root(self):
		"""Delete every file. The root stays, and the folder above it stays."""
		self.write({"src/a/only.txt": "x\n"})

		prototype_files.delete_file(self.doc.name, "src/App.vue")
		prototype_files.delete_file(self.doc.name, "src/a/only.txt")

		self.assertEqual(self.paths(), [])
		self.assertEqual(self.folders(), [])
		self.assertTrue(os.path.isdir(self.base()))
		self.assertTrue(os.path.isdir(os.path.dirname(self.base())))

	def test_a_prune_keeps_a_folder_that_still_holds_a_file(self):
		self.write({"src/a/one.txt": "x\n", "src/a/two.txt": "x\n"})

		prototype_files.delete_file(self.doc.name, "src/a/one.txt")

		self.assertTrue(os.path.isdir(os.path.join(self.base(), "src", "a")))
		self.assertIn("src/a/two.txt", self.paths())

	def test_a_deleted_tree_gives_its_folder_quota_back(self):
		"""The bypass, end to end.

		Without the prune the folders survive the delete, the tree reads as
		empty, and the next batch of new folders goes over the cap. Repeating
		write and delete is how the disk runs out of inodes.
		"""
		half = prototype_files.MAX_TREE_DIRS // 2 + 1
		first = {f"src/a{index}/f.txt": "x\n" for index in range(half)}
		second = {f"src/b{index}/f.txt": "x\n" for index in range(half)}
		self.write(first)

		for path in first:
			prototype_files.delete_file(self.doc.name, path)

		self.write(second)

		self.assertEqual(len(self.paths()), half + len(SEED))
		self.assertEqual(len(self.folders()), half + 1)

	# ------------------------------------------------------------- edit_file

	def test_an_edit_cannot_grow_a_file_past_the_byte_limit(self):
		self.write({"src/grow.txt": "seed\n"})

		with self.assertRaises(frappe.ValidationError):
			prototype_files.edit_file(
				self.doc.name, "src/grow.txt", "seed", "x" * (prototype_files.MAX_FILE_BYTES + 1)
			)

		self.assertEqual(
			prototype_files.read_files(self.doc.name, ["src/grow.txt"])[0]["content"], "seed\n"
		)

	def test_an_edit_that_stays_inside_the_limits_is_applied(self):
		self.write({"src/grow.txt": "seed\n"})

		prototype_files.edit_file(self.doc.name, "src/grow.txt", "seed", "grown")

		self.assertEqual(
			prototype_files.read_files(self.doc.name, ["src/grow.txt"])[0]["content"], "grown\n"
		)

	# -------------------------------------------------- 3.10: the bench path

	def test_a_write_onto_a_directory_names_the_relative_path_only(self):
		"""`open()` on a directory answers with the absolute path of the tree."""
		with self.assertRaises(frappe.ValidationError) as caught:
			self.write({"src": "this is a directory\n"})

		message = str(caught.exception)
		self.assertIn("src is a directory", message)
		self.assertNotIn(prototype_files.prototype_dir(self.doc.name), message)
		self.assert_tree_is_the_seed()

	def test_a_failed_open_answers_the_agent_without_the_bench_path(self):
		"""A file where a folder must be. `os.makedirs` raises with the path.

		The tool reply carries one fixed line. The whole exception stays in the
		server log, where the site owner reads it.
		"""
		reply = tools.call_tool(
			"write_files",
			{"prototype": SLUG, "files": [{"path": "src/App.vue/child.txt", "content": "x\n"}]},
		)

		self.assertTrue(reply["isError"])
		text = reply["content"][0]["text"]
		self.assertEqual(text, "write_files failed: the file could not be written.")
		self.assertNotIn(prototype_files.prototype_dir(self.doc.name), text)
		self.assertNotIn("Errno", text)

	# --------------------------------------------- the per-user create limit

	def test_a_user_cannot_hold_more_prototypes_than_the_limit(self):
		"""The real limit is 100. The guard reads the same at any number, and
		100 inserts per run prove nothing more."""
		with patch.object(prototype, "MAX_PROTOTYPES_PER_USER", 1):
			with self.assertRaises(frappe.ValidationError):
				prototype.create("Over the limit")

		self.assertFalse(
			frappe.db.exists("Sketch Prototype", {"owner": self.owner, "slug": "over-the-limit"})
		)

	def test_a_user_under_the_limit_still_creates(self):
		"""The positive control for the create cap."""
		doc = prototype.create("Under the limit")
		self.made.add(doc.name)

		self.assertEqual(doc.owner, self.owner)
		self.assertEqual(doc.slug, "under-the-limit")


class TestEveryRecipeStillFits(IntegrationTestCase):
	"""A Recipe tree goes to disk through `write_files`, in one batch.

	A cap under the largest Recipe would make a starter Prototype impossible to
	create, and the failure would only show at signup. This is the guard on
	that, for a Recipe added later as much as for the nine vendored today.
	"""

	def test_every_recipe_tree_is_inside_every_cap(self):
		root = frappe.get_app_path("sketch", "recipes")
		if not os.path.isdir(root):
			self.skipTest("no recipes folder in this app")

		for slug in sorted(os.listdir(root)):
			tree = os.path.join(root, slug)
			if not os.path.isdir(tree):
				continue

			sizes = []
			depths = []
			segments = []
			folders = 0
			for dirpath, dirnames, filenames in os.walk(tree):
				folders += len(dirnames)
				for filename in filenames:
					rel = os.path.relpath(os.path.join(dirpath, filename), tree)
					parts = rel.split(os.sep)
					sizes.append(os.path.getsize(os.path.join(dirpath, filename)))
					depths.append(len(parts))
					segments.extend(len(part.encode("utf-8")) for part in parts)

			with self.subTest(recipe=slug):
				self.assertLessEqual(len(sizes), prototype_files.MAX_BATCH_FILES)
				self.assertLessEqual(len(sizes), prototype_files.MAX_TREE_FILES)
				self.assertLessEqual(max(sizes, default=0), prototype_files.MAX_FILE_BYTES)
				self.assertLessEqual(sum(sizes), prototype_files.MAX_TREE_BYTES)
				self.assertLessEqual(max(depths, default=0), prototype_files.MAX_PATH_DEPTH)
				self.assertLessEqual(max(segments, default=0), prototype_files.MAX_SEGMENT_BYTES)
				self.assertLessEqual(folders, prototype_files.MAX_TREE_DIRS)
