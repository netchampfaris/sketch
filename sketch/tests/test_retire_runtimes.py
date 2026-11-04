# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""Retiring a Runtime: every Prototype still opens, and its owner is told once.

The rules this file holds:

- The patch moves a Prototype on a retired Pin to 1.1.0 and keeps the old Pin in `moved_from_pin`. One on 1.1.0
  stays as it is. `modified` does not change, and a rerun moves nothing.
- Only the owner's shell boot carries the notice. Only the owner may dismiss it, and then it is gone for good.
- A fork, a restore and set_runtime never put a Pin this server does not build back on a Prototype.
- build-all.sh removes the output of a version that is no longer in runtime/versions/, and nothing else.
"""

import os
import shutil
import subprocess
import tempfile

import frappe
from frappe.tests import IntegrationTestCase, set_user

from sketch import api, prototype, versions, viewer_api
from sketch.mcp import tools
from sketch.patches.v1_0 import retire_old_runtimes
from sketch.tests import utils
from sketch.viewer import SketchViewerRenderer

FILES = {
	"src/App.vue": "<template><RouterView /></template>\n",
	"src/router.ts": "export default []\n",
	"src/pages/Home.vue": "<template><h1>hi</h1></template>\n",
}

RETIRED = ("1.0.0-beta.55", "1.0.0-rc.2", "1.0.0")


def pin_of(name: str) -> tuple[str, str | None]:
	return tuple(frappe.db.get_value("Sketch Prototype", name, ["pin", "moved_from_pin"]))


class RetireCase(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_runtime()
		cls.owner = utils.make_user("rtown", "d2trtown")
		cls.addClassCleanup(utils.drop_user, cls.owner)
		cls.ed = utils.make_user("rted", "d2trted")
		cls.addClassCleanup(utils.drop_user, cls.ed)
		cls.reader = utils.make_user("rtrd", "d2trtrd")
		cls.addClassCleanup(utils.drop_user, cls.reader)

	def make(self, slug: str, pin: str | None = None, **kwargs):
		doc = utils.make_prototype(self.owner, slug, files=FILES, **kwargs)
		self.addCleanup(utils.drop_prototype, doc.name)
		if pin:
			frappe.db.set_value("Sketch Prototype", doc.name, "pin", pin, update_modified=False)
		return doc


class TestPatch(RetireCase):
	def test_it_moves_every_retired_pin_to_1_1_0_and_leaves_1_1_0_alone(self):
		docs = {pin: self.make(f"d2t-rt-{i}", pin) for i, pin in enumerate((*RETIRED, "1.1.0"))}
		before = {pin: frappe.db.get_value("Sketch Prototype", d.name, "modified") for pin, d in docs.items()}

		retire_old_runtimes.move([d.name for d in docs.values()])

		for pin in RETIRED:
			with self.subTest(pin=pin):
				self.assertEqual(pin_of(docs[pin].name), ("1.1.0", pin))
		self.assertEqual(pin_of(docs["1.1.0"].name), ("1.1.0", None))
		for pin, doc in docs.items():
			self.assertEqual(frappe.db.get_value("Sketch Prototype", doc.name, "modified"), before[pin])

	def test_a_rerun_moves_nothing(self):
		doc = self.make("d2t-rt-again", "1.0.0-rc.2")
		retire_old_runtimes.move([doc.name])
		retire_old_runtimes.move([doc.name])
		self.assertEqual(pin_of(doc.name), ("1.1.0", "1.0.0-rc.2"))

	def test_the_target_is_the_one_version_left_to_build(self):
		root = os.path.join(frappe.get_app_path("sketch"), "..", "runtime", "versions")
		self.assertEqual(sorted(os.listdir(root)), [retire_old_runtimes.TARGET])


class TestNotice(RetireCase):
	def setUp(self):
		super().setUp()
		self.doc = self.make("d2t-rt-notice", is_public=True)
		frappe.db.set_value("Sketch Prototype", self.doc.name, "moved_from_pin", "1.0.0-rc.2")
		with set_user(self.owner):
			api.invite_editor(self.doc.slug, utils.username_of(self.ed))

	def moved(self, user):
		saved = frappe.local.form_dict
		with set_user(user):
			frappe.local.form_dict = frappe._dict()
			try:
				renderer = SketchViewerRenderer(path=f"u/{utils.username_of(self.owner)}/{self.doc.slug}")
				self.assertTrue(renderer.can_render())
				return renderer.shell_payload()["moved"]
			finally:
				frappe.local.form_dict = saved

	def test_only_the_owner_is_told(self):
		self.assertEqual(self.moved(self.owner), {"from": "1.0.0-rc.2", "to": self.doc.pin})
		for user in (self.ed, self.reader, "Guest"):
			with self.subTest(user=user):
				self.assertIsNone(self.moved(user))

	def test_nobody_is_told_about_a_prototype_that_never_moved(self):
		frappe.db.set_value("Sketch Prototype", self.doc.name, "moved_from_pin", None)
		self.assertIsNone(self.moved(self.owner))

	def test_only_the_owner_dismisses_it_and_it_stays_gone(self):
		for user in (self.ed, self.reader):
			with self.subTest(user=user), set_user(user), self.assertRaises(frappe.DoesNotExistError):
				viewer_api.dismiss_moved_notice(self.doc.name)
		self.assertEqual(pin_of(self.doc.name)[1], "1.0.0-rc.2")

		with set_user(self.owner):
			viewer_api.dismiss_moved_notice(self.doc.name)
		self.assertEqual(pin_of(self.doc.name), (self.doc.pin, None))
		self.assertIsNone(self.moved(self.owner))


class TestNoRetiredPinComesBack(RetireCase):
	def test_a_fork_of_a_prototype_on_a_retired_pin_gets_a_built_one(self):
		source = self.make("d2t-rt-forksrc", "1.0.0-rc.2", is_public=True)
		with set_user(self.reader):
			row = api.fork_prototype(utils.username_of(self.owner), source.slug)
		self.addCleanup(utils.drop_prototype, row["name"])
		self.assertEqual(pin_of(row["name"])[0], prototype.newest_pin())

	def test_a_restore_keeps_the_current_pin(self):
		doc = self.make("d2t-rt-restore")
		with set_user(self.owner):
			for prompt, body in (("First", "a"), ("Second", "b")):
				tools.do_write_files(
					{"prototype": doc.slug, "files": [{"path": "src/pages/Home.vue", "content": f"<template>{body}</template>\n"}]}
				)
				tools.do_commit({"prototype": doc.slug, "prompt": prompt})
			first = versions.history(doc.name)[-1]["sequence"]
			frappe.db.set_value("Sketch Prototype", doc.name, "pin", prototype.newest_pin())
			versions.restore(frappe.get_doc("Sketch Prototype", doc.name), first, False)
		self.assertEqual(pin_of(doc.name)[0], prototype.newest_pin())

	def test_set_runtime_refuses_a_retired_pin(self):
		doc = self.make("d2t-rt-setrt")
		with set_user(self.owner), self.assertRaises(frappe.ValidationError):
			tools.do_set_runtime({"prototype": doc.slug, "version": "1.0.0-rc.2"})
		self.assertEqual(pin_of(doc.name)[0], prototype.newest_pin())


class TestBuildAllCleanup(IntegrationTestCase):
	def test_it_removes_only_retired_version_output(self):
		"""Runs the real build-all.sh in a copy of the layout, with build.sh stubbed out."""
		src = os.path.join(frappe.get_app_path("sketch"), "..", "runtime", "build-all.sh")
		with tempfile.TemporaryDirectory() as root:
			versions = os.path.join(root, "runtime", "versions")
			os.makedirs(os.path.join(versions, "1.1.0"))
			open(os.path.join(versions, "1.1.0", "yarn.lock"), "w").close()
			# What git leaves of a retired version on a server: untracked files, no yarn.lock.
			os.makedirs(os.path.join(versions, "1.0.0-rc.2", "node_modules"))
			shutil.copy(src, os.path.join(root, "runtime", "build-all.sh"))
			with open(os.path.join(root, "runtime", "build.sh"), "w") as f:
				f.write('echo "built $1"\n')
			out = os.path.join(root, "sketch", "public", "runtimes")
			for name in ("1.1.0", "1.0.0", "1.0.0-rc.2", ".1.1.0.building"):
				os.makedirs(os.path.join(out, name))
			elsewhere = os.path.join(root, "elsewhere")
			os.makedirs(elsewhere)
			os.symlink(elsewhere, os.path.join(out, "9.9.9"))
			open(os.path.join(out, "stray.txt"), "w").close()

			run = subprocess.run(
				["sh", os.path.join(root, "runtime", "build-all.sh")], capture_output=True, text=True, check=True
			)

			self.assertIn("built 1.1.0", run.stdout)
			self.assertNotIn("built 1.0.0-rc.2", run.stdout)
			self.assertEqual(sorted(os.listdir(out)), [".1.1.0.building", "1.1.0", "9.9.9", "stray.txt"])
			self.assertTrue(os.path.isdir(elsewhere))
