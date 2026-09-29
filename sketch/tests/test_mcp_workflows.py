"""Agent workflows through MCP tool calls, with real prototype files."""

import frappe
from frappe.tests import IntegrationTestCase

from sketch.mcp import tools
from sketch.tests import utils


class TestMcpWorkflows(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_runtime()
		cls.owner = utils.make_user("workflow", "d2tworkflow")
		cls.addClassCleanup(utils.drop_user, cls.owner)

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self.doc = utils.make_prototype(
			self.owner,
			"d2t-workflow",
			files={
				"src/one.js": "export default 'one'\n",
				"src/two.js": "export default 'two'\n",
			},
		)
		self.addCleanup(utils.drop_prototype, self.doc.name)
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user(self.owner)

	def call(self, name, **arguments):
		return tools.call_tool(name, {"prototype": self.doc.slug, **arguments})

	def read(self, *paths):
		reply = self.call("read_files", paths=list(paths))
		self.assertFalse(reply["isError"], reply)
		return {f["path"]: f["content"] for f in reply["structuredContent"]["files"]}

	def test_invalid_arguments_name_the_field_and_leave_files_unchanged(self):
		cases = [
			("read_files", {"files": ["src/one.js"]}, "paths"),
			("write_files", {"files": ["not an object"]}, "arguments.files[0]"),
			("write_files", {"files": [{"path": "src/one.js", "content": 42}]}, "arguments.files[0].content"),
			("check", {"screenshot": "false"}, "arguments.screenshot"),
			("commit", {"prompt": "Keep my prompt", "summary": "x" * 141}, "arguments.summary"),
		]
		for name, arguments, field in cases:
			with self.subTest(tool=name, field=field):
				reply = self.call(name, **arguments)
				self.assertTrue(reply["isError"], reply)
				self.assertIn(field, reply["content"][0]["text"])
		self.assertEqual(self.read("src/one.js"), {"src/one.js": "export default 'one'\n"})

	def test_rpc_refuses_non_object_arguments(self):
		import json

		from sketch.mcp import rpc

		for arguments in ([], False, "", None):
			status, reply = rpc.handle(
				json.dumps(
					{
						"jsonrpc": "2.0",
						"id": 1,
						"method": "tools/call",
						"params": {"name": "get_skill", "arguments": arguments},
					}
				).encode(),
				{},
			)
			self.assertEqual(status, 200)
			self.assertEqual(reply["error"]["code"], -32602)
			self.assertEqual(reply["error"]["message"], "arguments must be an object")

	def test_summary_limit_preserves_the_complete_prompt(self):
		self.assertFalse(
			self.call("write_files", files=[{"path": "src/one.js", "content": "changed"}])["isError"]
		)
		prompt = "Keep  spacing\nand <Button> exactly."
		reply = self.call("commit", prompt=prompt, summary="x" * 140)
		self.assertFalse(reply["isError"], reply)
		from sketch import api

		self.assertEqual(api.list_versions(self.doc.slug)[0]["prompt"], prompt)

	def test_batch_edits_validate_every_match_before_writing(self):
		edits = [
			{"path": "src/one.js", "old_string": "one", "new_string": "first"},
			{"path": "src/two.js", "old_string": "absent", "new_string": "second"},
		]
		reply = self.call("edit_files", edits=edits)
		self.assertTrue(reply["isError"], reply)
		self.assertIn("edits[1]", reply["content"][0]["text"])
		self.assertEqual(self.read("src/one.js")["src/one.js"], "export default 'one'\n")
		edits[1]["old_string"] = "two"
		edits.append({"path": "src/one.js", "old_string": "first", "new_string": "final"})
		reply = self.call("edit_files", edits=edits)
		self.assertFalse(reply["isError"], reply)
		self.assertEqual(
			self.read("src/one.js", "src/two.js"),
			{
				"src/one.js": "export default 'final'\n",
				"src/two.js": "export default 'second'\n",
			},
		)
		commit = self.call("commit", prompt="Change both files")
		self.assertFalse(commit["isError"], commit)
		self.assertEqual(commit["structuredContent"]["files_modified"], 2)

	def test_batch_edit_restores_files_after_a_write_failure(self):
		import os
		from unittest.mock import patch

		replace = os.replace
		calls = 0

		def fail_second(source, destination):
			nonlocal calls
			calls += 1
			if calls == 2:
				raise OSError("test write failure")
			return replace(source, destination)

		with patch("sketch.prototype_files.os.replace", side_effect=fail_second):
			reply = self.call(
				"edit_files",
				edits=[
					{"path": "src/one.js", "old_string": "one", "new_string": "first"},
					{"path": "src/two.js", "old_string": "two", "new_string": "second"},
				],
			)
		self.assertTrue(reply["isError"], reply)
		self.assertEqual(
			self.read("src/one.js", "src/two.js"),
			{
				"src/one.js": "export default 'one'\n",
				"src/two.js": "export default 'two'\n",
			},
		)
		self.assertFalse(self.call("commit", prompt="Nothing changed")["structuredContent"]["recorded"])

	def test_uploaded_image_is_importable_and_recorded_in_history(self):
		import base64
		import json

		svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="2" height="2"><rect width="2" height="2" fill="red"/></svg>'
		path = "src/assets/logo.js"
		reply = self.call(
			"upload_asset", path=path, mime_type="image/svg+xml", data_base64=base64.b64encode(svg).decode()
		)
		self.assertFalse(reply["isError"], reply)
		module = self.read(path)[path]
		url = json.loads(module.removeprefix("export default ").strip().removesuffix(";"))
		self.assertTrue(url.startswith("data:image/svg+xml;base64,"))
		self.assertEqual(base64.b64decode(url.split(",", 1)[1]), svg)
		reply = self.call("commit", prompt="Add the logo")
		self.assertEqual(reply["structuredContent"]["changes"], [{"path": path, "action": "added"}])

	def test_invalid_assets_cannot_replace_existing_source(self):
		import base64

		cases = [
			{"path": "src/one.js", "mime_type": "image/png", "data_base64": "eA=="},
			{
				"path": "src/assets/../../outside.js",
				"mime_type": "image/svg+xml",
				"data_base64": base64.b64encode(b"<svg/>").decode(),
			},
			{"path": "src/assets/a.js", "mime_type": "text/html", "data_base64": "eA=="},
			{"path": "src/assets/a.js", "mime_type": "image/png", "data_base64": "bad!"},
			{
				"path": "src/assets/a.js",
				"mime_type": "image/png",
				"data_base64": base64.b64encode(b"<svg/>").decode(),
			},
			{
				"path": "src/assets/a.js",
				"mime_type": "image/svg+xml",
				"data_base64": base64.b64encode(b"<!DOCTYPE svg><svg/>").decode(),
			},
			{
				"path": "src/assets/a.js",
				"mime_type": "image/png",
				"data_base64": base64.b64encode(b"x" * 512001).decode(),
			},
		]
		for arguments in cases:
			with self.subTest(path=arguments["path"], mime_type=arguments["mime_type"]):
				reply = self.call("upload_asset", **arguments)
				self.assertTrue(reply["isError"], reply["content"][0])
		self.assertEqual(self.read("src/one.js")["src/one.js"], "export default 'one'\n")
		files = self.call("list_files")["structuredContent"]["files"]
		self.assertEqual(len(files), 2)
