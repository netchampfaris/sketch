# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""Who the Viewer serves, and what a stranger learns from the answer.

Two rules, both from spec 6.3 and 6.5:

- **404, never 403.** A private Prototype and a Prototype that does not exist
  must answer the same. A 403 confirms the URL exists, which is the one fact
  the owner did not share.
- **A bad signature falls through.** It is not an error. A stale link to a
  public Prototype still works, and a stale link to a private one answers 404.

The HTTP cases arrive as strangers. Cache cases also request the page as its owner.
"""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase, set_user
from frappe.utils import set_request
from frappe.website.serve import get_response

from sketch import signature
from sketch.tests import utils

#: Facts only the owner holds. Neither may appear in a 404 body.
SECRET_TITLE = "D2T Confidential Roadmap"
SECRET_MARK = "d2t-secret-marker-string"
SECRET_FILES = {"src/App.vue": f"<template><h1>{SECRET_MARK}</h1></template>\n"}


class TestViewerAccess(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_runtime()
		cls.user = utils.make_user("access", "d2taccess")
		cls.addClassCleanup(utils.drop_user, cls.user)
		cls.username = utils.username_of(cls.user)

		files = {"src/App.vue": "<template><h1>hello</h1></template>\n"}
		cls.private = utils.make_prototype(
			cls.user, "d2t-private", files=SECRET_FILES, is_public=False, title=SECRET_TITLE
		)
		cls.addClassCleanup(utils.drop_prototype, cls.private.name)
		cls.public = utils.make_prototype(cls.user, "d2t-public", files=files, is_public=True)
		cls.addClassCleanup(utils.drop_prototype, cls.public.name)

	def setUp(self):
		utils.require_webserver()

	def get(self, path: str):
		return utils.request("GET", path)

	# ------------------------------------------------------- 404, not 403

	def test_a_private_prototype_answers_like_a_missing_one(self):
		"""The two answers must be identical, and both must be 404."""
		private = self.get(f"/u/{self.username}/d2t-private")
		missing = self.get(f"/u/{self.username}/d2t-no-such-slug")

		self.assertEqual(private.status_code, 404, private.text[:400])
		self.assertEqual(missing.status_code, 404, missing.text[:400])
		self.assertEqual(private.status_code, missing.status_code)

	def test_an_unknown_user_answers_404(self):
		response = self.get("/u/d2tnosuchuser/d2t-private")
		self.assertEqual(response.status_code, 404)

	def test_a_private_prototype_never_answers_403(self):
		"""Named on its own, because 403 is the mistake this guards."""
		for path in (
			f"/u/{self.username}/d2t-private",
			f"/u/{self.username}/d2t-private?exp=1&sig=deadbeef",
			f"/u/{self.username}/d2t-private?theme=dark",
		):
			with self.subTest(path=path):
				self.assertEqual(self.get(path).status_code, 404)

	def test_a_private_prototype_leaks_nothing_in_the_404(self):
		"""The 404 body must carry no fact the stranger did not already send.

		The requested path is echoed by Frappe's own 404 page, and the caller
		wrote it, so it is not a leak. The title and the source are.
		"""
		response = self.get(f"/u/{self.username}/d2t-private")
		self.assertNotIn(SECRET_TITLE, response.text)
		self.assertNotIn(SECRET_MARK, response.text)

	def test_a_public_prototype_serves_a_stranger(self):
		"""The control. Without it, a broken renderer would pass every 404 test."""
		response = self.get(f"/u/{self.username}/d2t-public")
		self.assertEqual(response.status_code, 200)
		self.assertEqual(utils.shell_slot(response.text)["name"], self.public.name)
		frame = self.get(f"/u/{self.username}/d2t-public?frame=1")
		self.assertEqual(frame.status_code, 200)
		self.assertEqual(utils.data_slot(frame.text)["name"], self.public.name)

	# --------------------------------------------------------- the signature

	def test_a_valid_signature_serves_a_private_prototype(self):
		stamp = signature.mint(self.private.name, ttl_seconds=600)
		response = self.get(
			f"/u/{self.username}/d2t-private?exp={stamp['exp']}&sig={stamp['sig']}"
		)
		self.assertEqual(response.status_code, 200, response.text[:400])
		payload = utils.data_slot(response.text)
		self.assertEqual(payload["name"], self.private.name)
		self.assertEqual(payload["chrome"], "off", "a signature opens check's document, never the shell")
		self.assertEqual(utils.credential_keys(payload), [], "nor anything that acts as someone")

	def test_an_expired_signature_falls_through_to_404(self):
		stamp = signature.mint(self.private.name, ttl_seconds=-60)
		response = self.get(
			f"/u/{self.username}/d2t-private?exp={stamp['exp']}&sig={stamp['sig']}"
		)
		self.assertEqual(response.status_code, 404)

	def test_a_wrong_signature_falls_through_to_404(self):
		stamp = signature.mint(self.private.name, ttl_seconds=600)
		wrong = ("0" if stamp["sig"][0] != "0" else "1") + stamp["sig"][1:]
		for exp, sig in (
			(stamp["exp"], wrong),
			(stamp["exp"], "deadbeef"),
			(stamp["exp"], ""),
			(stamp["exp"] + 1, stamp["sig"]),
			("not-a-number", stamp["sig"]),
			(stamp["exp"], stamp["sig"].upper()),
		):
			with self.subTest(exp=exp, sig=sig):
				response = self.get(f"/u/{self.username}/d2t-private?exp={exp}&sig={sig}")
				self.assertEqual(response.status_code, 404)

	def test_another_prototypes_signature_does_not_open_this_one(self):
		"""The signature covers the hash id, so it opens one Prototype only."""
		stamp = signature.mint(self.public.name, ttl_seconds=600)
		response = self.get(
			f"/u/{self.username}/d2t-private?exp={stamp['exp']}&sig={stamp['sig']}"
		)
		self.assertEqual(response.status_code, 404)

	def test_a_stale_signature_still_serves_a_public_prototype(self):
		"""A bad signature falls through. It never turns a 200 into a 404."""
		stamp = signature.mint(self.public.name, ttl_seconds=-3600)
		response = self.get(f"/u/{self.username}/d2t-public?exp={stamp['exp']}&sig={stamp['sig']}")
		self.assertEqual(response.status_code, 200, response.text[:400])
		self.assertEqual(utils.data_slot(response.text)["name"], self.public.name)

	# ----------------------------------------------------- verify() itself

	def test_verify_never_raises(self):
		for exp, sig in (
			(None, None),
			("", ""),
			("abc", "abc"),
			(1.5, 1.5),
			([], {}),
			(2**63, "x"),
		):
			with self.subTest(exp=exp, sig=sig):
				self.assertFalse(signature.verify(self.private.name, exp, sig))

	def test_verify_accepts_only_its_own_prototype(self):
		stamp = signature.mint(self.private.name, ttl_seconds=600)
		self.assertTrue(signature.verify(self.private.name, stamp["exp"], stamp["sig"]))
		self.assertFalse(signature.verify(self.public.name, stamp["exp"], stamp["sig"]))


class TestViewerWebsiteCache(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_runtime()
		cls.user = utils.make_user("viewercache", "d2tviewercache")
		cls.addClassCleanup(utils.drop_user, cls.user)
		cls.doc = utils.make_prototype(cls.user, "d2t-cache", files=SECRET_FILES)
		cls.addClassCleanup(utils.drop_prototype, cls.doc.name)
		cls.path = f"/u/{utils.username_of(cls.user)}/{cls.doc.slug}"

	def setUp(self):
		# Developer mode normally hides this bug by disabling website caching.
		self.enterContext(patch.dict(frappe.conf, developer_mode=0, disable_website_cache=0))
		self.enterContext(patch.dict(frappe.flags, force_website_cache=False))
		self.enterContext(patch.object(frappe.local, "request", None, create=True))
		self.enterContext(patch.object(frappe.local, "no_cache", False, create=True))
		self.enterContext(patch.object(frappe.local, "form_dict", frappe._dict()))
		self.enterContext(patch.object(frappe.local, "response_headers", frappe._dict()))
		self.enterContext(patch.dict(frappe.local.response, from_cache=False))

	def request(self, path: str, user: str = "Guest"):
		frappe.local.no_cache = False
		frappe.local.response.from_cache = False
		frappe.local.response_headers = frappe._dict()
		set_request(method="GET", path=path)
		url = frappe.local.request.url
		self.addCleanup(frappe.cache.hdel, "website_404", url)
		with set_user(user):
			return get_response(path)

	def test_guest_404_does_not_block_the_owner(self):
		guest = self.request(self.path)
		owner = self.request(self.path, self.user)

		self.assertEqual(guest.status_code, 404)
		self.assertEqual(owner.status_code, 200, owner.get_data(as_text=True)[:400])
		self.assertEqual(utils.shell_slot(owner.get_data(as_text=True))["role"], "owner")
		self.assertFalse(frappe.cache.hget("website_404", frappe.local.request.url))

	def test_missing_viewer_paths_are_not_cached(self):
		for path in (f"{self.path}-missing", "/u/d2tmissing/nothing", "/u/d2tmissing"):
			with self.subTest(path=path):
				response = self.request(path)
				self.assertEqual(response.status_code, 404)
				self.assertFalse(frappe.cache.hget("website_404", frappe.local.request.url))
