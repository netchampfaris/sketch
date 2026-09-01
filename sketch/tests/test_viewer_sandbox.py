# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""Which origin a Prototype lands in.

A Prototype is JavaScript one user wrote, and the Viewer serves it as a
top-level document. Without a sandbox it runs on the app origin with the
reader's session, so it can call `sketch.api.get_agent_token` with the
reader's cookie and keep a permanent `/mcp` bearer for them.

The rule the renderer follows: every caller gets `sandbox` in the CSP, so the
document lands in an opaque origin. No cookies, no same-origin read, no SPA
csrf_token.

The owner is not exempt, and this module holds the renderer to that. Ownership
says who holds the tree, never who wrote the code in it: `fork_prototype`
copies another user's public tree, word for word, into a Prototype the caller
owns. An owner exemption therefore runs the attacker's JavaScript on the app
origin with the victim's session, which is the attack the sandbox exists to
stop. `TestAForkedTreeIsSandboxed` walks that exact route.

`allow-same-origin` must never appear. It hands the app origin back.
"""

import frappe
from frappe.tests import IntegrationTestCase, set_user

from sketch import api, signature
from sketch.tests import utils
from sketch.viewer import SketchViewerRenderer

FILES = {"src/App.vue": "<template><h1>hello</h1></template>\n"}

CSP = "Content-Security-Policy"


class TestViewerSandbox(IntegrationTestCase):
	"""The header on the wire. Only a real request carries the session."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_runtime()
		cls.user = utils.make_user("sandbox", "d2tsandbox")
		cls.addClassCleanup(utils.drop_user, cls.user)
		cls.username = utils.username_of(cls.user)
		cls.doc = utils.make_prototype(cls.user, "d2t-sandbox", files=FILES, is_public=True)
		cls.addClassCleanup(utils.drop_prototype, cls.doc.name)
		cls.path = f"/u/{cls.username}/d2t-sandbox"

	def setUp(self):
		utils.require_webserver()

	def test_a_guest_gets_the_sandbox(self):
		"""A stranger on a public Prototype reads it from an opaque origin."""
		response = utils.request("GET", self.path)

		self.assertEqual(response.status_code, 200, response.text[:400])
		self.assertIn("sandbox", response.headers[CSP])
		self.assertNotIn("allow-same-origin", response.headers[CSP])

	def test_the_owner_gets_the_sandbox_too(self):
		"""The owner reads a tree a fork may have filled with a stranger's code."""
		response = utils.request("GET", self.path, headers=utils.api_auth_header(self.user))

		self.assertEqual(response.status_code, 200, response.text[:400])
		self.assertTrue(utils.data_slot(response.text)["is_owner"], "the request must be the owner's")
		self.assertIn("sandbox", response.headers[CSP])
		self.assertNotIn("allow-same-origin", response.headers[CSP])

	def test_the_frame_rule_survives_the_sandbox(self):
		"""frame-ancestors is spec 6.4 and both callers keep it."""
		guest = utils.request("GET", self.path)
		owner = utils.request("GET", self.path, headers=utils.api_auth_header(self.user))

		for response in (guest, owner):
			self.assertIn("frame-ancestors 'self'", response.headers[CSP])


class TestSandboxHeaders(IntegrationTestCase):
	"""The renderer's own answer, driven the way `is_live` is driven.

	`can_render()` sets `is_owner` from the session, so each case runs inside
	the session it is about.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_runtime()
		cls.user = utils.make_user("sbhead", "d2tsbhead")
		cls.addClassCleanup(utils.drop_user, cls.user)
		cls.username = utils.username_of(cls.user)
		cls.doc = utils.make_prototype(cls.user, "d2t-sbhead", files=FILES, is_public=True)
		cls.addClassCleanup(utils.drop_prototype, cls.doc.name)

	def response_headers(self) -> dict:
		renderer = SketchViewerRenderer(path=f"u/{self.username}/{self.doc.slug}")
		self.assertTrue(renderer.can_render())
		return renderer.response_headers()

	def test_a_guest_is_sandboxed(self):
		with set_user("Guest"):
			policy = self.response_headers()[CSP]

		self.assertIn("sandbox allow-scripts", policy)
		self.assertNotIn("allow-same-origin", policy)

	def test_a_check_request_is_sandboxed(self):
		"""check arrives as a Guest with the signature, so it is not the owner."""
		with set_user("Guest"):
			stamp = signature.mint(self.doc.name, ttl_seconds=600)
			frappe.form_dict.update({"exp": stamp["exp"], "sig": stamp["sig"]})
			policy = self.response_headers()[CSP]

		self.assertIn("sandbox", policy)

	def test_the_owner_is_sandboxed(self):
		"""No owner exemption. One rule for every caller is one rule to check."""
		with set_user(self.user):
			renderer = SketchViewerRenderer(path=f"u/{self.username}/{self.doc.slug}")
			self.assertTrue(renderer.can_render())
			self.assertTrue(renderer.is_owner, "the case must run as the owner")
			policy = renderer.response_headers()[CSP]

		self.assertIn("sandbox allow-scripts", policy)
		self.assertNotIn("allow-same-origin", policy)

	def test_a_renderer_that_skipped_can_render_is_sandboxed(self):
		"""The default is the safe one, whatever a future caller does."""
		policy = SketchViewerRenderer(path="u/nobody/nothing").response_headers()[CSP]
		self.assertIn("sandbox", policy)


class TestAForkedTreeIsSandboxed(IntegrationTestCase):
	"""The route that makes an owner exemption a hole.

	The attacker publishes a Prototype. The victim forks it from the feed, so
	the victim now owns a tree of the attacker's code, and opens it. The
	document must still land in an opaque origin.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_runtime()
		cls.attacker = utils.make_user("forkatk", "d2tforkatk")
		cls.addClassCleanup(utils.drop_user, cls.attacker)
		cls.victim = utils.make_user("forkvic", "d2tforkvic")
		cls.addClassCleanup(utils.drop_user, cls.victim)
		cls.attacker_name = utils.username_of(cls.attacker)
		cls.source = utils.make_prototype(
			cls.attacker, "d2t-fork-sandbox", files=FILES, is_public=True
		)
		cls.addClassCleanup(utils.drop_prototype, cls.source.name)

	def test_the_victims_own_fork_is_sandboxed(self):
		with set_user(self.victim):
			row = api.fork_prototype(self.attacker_name, self.source.slug)

		self.addCleanup(utils.drop_prototype, row["name"])

		with set_user(self.victim):
			renderer = SketchViewerRenderer(path=f"u/{utils.username_of(self.victim)}/{row['slug']}")
			self.assertTrue(renderer.can_render())
			self.assertTrue(renderer.is_owner, "the fork lands on the victim")
			policy = renderer.response_headers()[CSP]

		self.assertIn("sandbox allow-scripts", policy)
		self.assertNotIn("allow-same-origin", policy)
