# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The Runtime files a sandboxed Viewer can read.

`sketch/viewer.py` sends every caller into an opaque origin, the owner as well.
In an opaque origin every http URL is cross-origin, and two of the Runtime's own
requests are made in CORS mode: the module script boot.js with everything the
import map pulls in, and the @font-face request inside frappe-ui.css. /assets
carries no Access-Control-Allow-Origin and is not served by this app, so the
sandboxed document reads the Runtime from /sketch-runtime/<pin>/<file>
instead, which is.

Without this the Viewer prints

    Access to script at '.../boot.js' from origin 'null' has been blocked by
    CORS policy

for every public visitor and every `check`. `sketch/tests/test_recipes_boot.py`
is the end-to-end proof, because `check` reads the Viewer as a signed Guest and
so runs sandboxed.
"""

import frappe
from frappe.tests import IntegrationTestCase

from sketch import runtime_assets
from sketch.tests import utils
from sketch.viewer import ASSET_PREFIX

FILES = {"src/App.vue": "<template><h1>hello</h1></template>\n"}


class TestRuntimeAssetUrls(IntegrationTestCase):
	"""Which prefix each caller's document names."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_runtime()
		cls.user = utils.make_user("rtasset", "d2trtasset")
		cls.addClassCleanup(utils.drop_user, cls.user)
		cls.username = utils.username_of(cls.user)
		cls.doc = utils.make_prototype(cls.user, "d2t-rtasset", files=FILES, is_public=True)
		cls.addClassCleanup(utils.drop_prototype, cls.doc.name)
		cls.path = f"/u/{cls.username}/d2t-rtasset"

	def setUp(self):
		utils.require_webserver()

	def assets_prefix(self) -> str:
		return f"{ASSET_PREFIX}{self.doc.pin}/"

	def test_a_sandboxed_document_reads_the_runtime_over_cors(self):
		"""No /assets URL survives, so nothing the page loads is CORS-blocked."""
		html = utils.request("GET", self.path).text

		self.assertIn(runtime_assets.url_prefix(self.doc.pin), html)
		self.assertNotIn(self.assets_prefix(), html)

	def test_the_owner_reads_the_runtime_over_cors_too(self):
		"""The owner is sandboxed as well, so the owner is in an opaque origin.

		This test used to assert the opposite. It pinned the owner exemption in
		`viewer.py.response_headers`, which `sketch.api.fork_prototype` turns
		into a bypass: a victim who forks an attacker's public tree owns the
		copy, so the attacker's JavaScript ran unsandboxed on the app origin.
		The exemption is gone, and with it the /assets URLs the owner used to
		get: from an opaque origin /assets carries no
		Access-Control-Allow-Origin, so boot.js would be CORS-blocked.
		"""
		response = utils.request("GET", self.path, headers=utils.api_auth_header(self.user))

		self.assertTrue(utils.data_slot(response.text)["is_owner"], "the request must be the owner's")
		self.assertIn(runtime_assets.url_prefix(self.doc.pin), response.text)
		self.assertNotIn(self.assets_prefix(), response.text)


class TestRuntimeAssetRoute(IntegrationTestCase):
	"""What /sketch-runtime/<pin>/<file> answers."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_runtime()
		cls.pin = utils.newest_runtime()

	def setUp(self):
		utils.require_webserver()

	def get(self, path: str):
		return utils.request("GET", path)

	def test_a_guest_reads_boot_js_with_the_cors_header(self):
		"""The one header this route exists for."""
		response = self.get(f"/{runtime_assets.PREFIX}/{self.pin}/boot.js")

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "*")
		self.assertIn("text/javascript", response.headers.get("Content-Type", ""))

	def test_the_bytes_are_the_bytes_under_assets(self):
		"""One file, two doors. A door that serves something else is a bug."""
		mine = self.get(f"/{runtime_assets.PREFIX}/{self.pin}/boot.js").content
		theirs = self.get(f"/assets/sketch/runtimes/{self.pin}/boot.js").content

		self.assertEqual(mine, theirs)

	def test_the_font_is_reachable_too(self):
		"""@font-face is a CORS request, so Inter needs the header as well."""
		response = self.get(f"/{runtime_assets.PREFIX}/{self.pin}/Inter.var.woff2")

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "*")

	def test_a_pin_folder_is_all_it_can_reach(self):
		"""Nothing outside the runtimes folder, by name or by dot segment."""
		for path in (
			f"/{runtime_assets.PREFIX}/{self.pin}/../../hooks.py",
			f"/{runtime_assets.PREFIX}/../hooks.py",
			f"/{runtime_assets.PREFIX}/no-such-pin/boot.js",
			f"/{runtime_assets.PREFIX}/{self.pin}/no-such-file.js",
		):
			with self.subTest(path=path):
				self.assertEqual(self.get(path).status_code, 404)

	def test_the_viewer_template_is_not_served_raw(self):
		"""viewer.html holds an unfilled data slot. It is the renderer's, not a file."""
		self.assertEqual(self.get(f"/{runtime_assets.PREFIX}/{self.pin}/viewer.html").status_code, 404)


class TestAssetPath(IntegrationTestCase):
	"""The path guard on its own, without a request."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_runtime()
		cls.pin = utils.newest_runtime()

	def test_a_real_file_resolves_inside_the_runtimes_folder(self):
		path = runtime_assets.asset_path(self.pin, "boot.js")

		self.assertIsNotNone(path)
		self.assertTrue(path.startswith(frappe.get_app_path("sketch", "public", "runtimes")))

	def test_every_way_out_of_the_folder_is_none(self):
		for pin, filename in (
			("", "boot.js"),
			(self.pin, ""),
			("..", "hooks.py"),
			(self.pin, ".."),
			(self.pin, "../../hooks.py"),
			(self.pin, "..\\..\\hooks.py"),
			(self.pin, ".hidden.js"),
			(self.pin, "viewer.html"),
			(self.pin, "manifest.json.bak"),
			("no-such-pin", "boot.js"),
		):
			with self.subTest(pin=pin, filename=filename):
				self.assertIsNone(runtime_assets.asset_path(pin, filename))

	def test_a_nul_byte_in_a_name_is_none_and_not_an_error(self):
		"""`os.path.realpath` raises ValueError on an embedded NUL.

		The name check has to catch it. This route runs before authentication,
		so a name the resolver refuses would turn any request into a 500.
		"""
		for pin, filename in ((self.pin, "boot\x00.js"), ("\x00", "boot.js"), (self.pin, "\x00.js")):
			with self.subTest(pin=pin, filename=filename):
				self.assertIsNone(runtime_assets.asset_path(pin, filename))
