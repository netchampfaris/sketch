"""Check selected routes and capture sizes through MCP and a real browser."""

import base64
import os
import socket
import struct
import subprocess
import tempfile
import time
from unittest.mock import patch

import frappe
import requests
from frappe.tests import IntegrationTestCase

from sketch import checkd
from sketch.mcp import tools
from sketch.tests import utils


class TestCheckOptions(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_runtime()
		utils.require_webserver()
		cls.owner = utils.make_user("capture", "d2tcapture")
		cls.addClassCleanup(utils.drop_user, cls.owner)
		with socket.socket() as sock:
			sock.bind(("127.0.0.1", 0))
			port = sock.getsockname()[1]
		cls.url = f"http://127.0.0.1:{port}/check"
		log = tempfile.TemporaryFile()
		cls.addClassCleanup(log.close)
		server = subprocess.Popen(
			["node", os.path.join(frappe.get_app_path("sketch"), "..", "checkd", "checkd.mjs")],
			env={**os.environ, "SKETCH_CHECKD_PORT": str(port)},
			stdout=log,
			stderr=log,
		)

		def stop():
			server.terminate()
			try:
				server.wait(timeout=10)
			except subprocess.TimeoutExpired:
				server.kill()
				server.wait()

		cls.addClassCleanup(stop)
		for _ in range(100):
			try:
				requests.get(cls.url, timeout=1)
				break
			except requests.ConnectionError:
				if server.poll() is not None:
					log.seek(0)
					raise AssertionError(log.read().decode())
				time.sleep(0.1)
		else:
			raise AssertionError("test check service did not start")

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self.doc = utils.make_prototype(
			self.owner,
			"d2t-capture",
			files={
				"src/App.vue": "<template><RouterView /></template>",
				"src/router.ts": "import Page from './Page.vue'; export default [{path: '/', component: Page}, {path: '/items/:id', component: Page}]",
				"src/Page.vue": '<template><main style="min-height: 1800px">A tall page</main></template>',
			},
		)
		self.addCleanup(utils.drop_prototype, self.doc.name)
		frappe.set_user(self.owner)
		self.addCleanup(frappe.set_user, "Administrator")

	def check(self, **options):
		with patch.object(checkd, "URL", self.url):
			reply = tools.call_tool("check", {"prototype": self.doc.slug, **options})
		self.assertFalse(reply["isError"], reply)
		self.assertEqual(reply["structuredContent"]["status"], "ok", reply["content"][0])
		return reply

	def test_mobile_full_page_capture_visits_a_concrete_detail_route(self):
		reply = self.check(
			screenshot=True,
			routes=["/items/42?tab=details"],
			viewport={"width": 390, "height": 844},
			full_page=True,
		)
		report = reply["structuredContent"]
		self.assertEqual(report["visited"], ["/items/42?tab=details"])
		self.assertEqual(report["skipped"], [])
		self.assertEqual(report["viewport"], {"width": 390, "height": 844})
		images = [block for block in reply["content"] if block["type"] == "image"]
		self.assertEqual(len(images), 1)
		width, height = struct.unpack(">II", base64.b64decode(images[0]["data"])[16:24])
		self.assertEqual(width, 390)
		self.assertGreaterEqual(height, 1800)
		self.assertIn("/items/42?tab=details (390x844, full page)", reply["content"][1]["text"])
		# A mobile check must not turn gallery cards into mobile screenshots.
		from sketch import thumbnails

		for theme in ("light", "dark"):
			with open(thumbnails.png_path(self.doc.name, theme), "rb") as handle:
				self.assertEqual(struct.unpack(">II", handle.read(24)[16:24]), (1280, 800))

	def test_default_check_keeps_automatic_routes_and_desktop_size(self):
		report = self.check()["structuredContent"]
		self.assertEqual(report["visited"], ["/"])
		self.assertEqual(report["skipped"][0]["route"], "/items/:id")
		self.assertEqual(report["viewport"], {"width": 1280, "height": 800})
		self.assertFalse(report["fullPage"])

	def test_invalid_capture_options_are_refused_by_the_service(self):
		for options in (
			{"routes": ["https://example.com"]},
			{"routes": ["/items/:id"]},
			{"viewport": {"width": 10000, "height": 844}},
			{"fullPage": "false"},
		):
			with self.subTest(options=options):
				response = requests.post(self.url, json={"url": "http://127.0.0.1/", **options}, timeout=5)
				self.assertEqual(response.status_code, 400, response.text)

	def test_uploaded_image_decodes_in_the_check_browser_without_egress(self):
		import io

		from PIL import Image

		buffer = io.BytesIO()
		Image.new("RGB", (2, 2), "red").save(buffer, format="PNG")
		reply = tools.call_tool(
			"upload_asset",
			{
				"prototype": self.doc.slug,
				"path": "src/assets/logo.js",
				"mime_type": "image/png",
				"data_base64": base64.b64encode(buffer.getvalue()).decode(),
			},
		)
		self.assertFalse(reply["isError"], reply)
		reply = tools.call_tool(
			"write_files",
			{
				"prototype": self.doc.slug,
				"files": [
					{
						"path": "src/Asset.vue",
						"content": """<script setup>
import { onMounted } from 'vue'
import logo from './assets/logo.js'
onMounted(async () => {
  const image = new Image()
  image.src = logo
  await image.decode()
  if (image.naturalWidth !== 2) throw new Error('Wrong uploaded image size')
})
</script><template><img :src="logo" alt="Uploaded logo" /></template>""",
					},
					{
						"path": "src/router.ts",
						"content": "import Asset from './Asset.vue'; export default [{path: '/', component: Asset}]",
					},
				],
			},
		)
		self.assertFalse(reply["isError"], reply)
		frappe.db.commit()
		report = self.check(screenshot=True)["structuredContent"]
		self.assertEqual(report["warnings"], [])
