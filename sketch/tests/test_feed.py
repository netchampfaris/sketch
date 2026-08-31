# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""/feed, the public listing and the front door.

Two jobs, and both are checked here.

The listing must never leak. `sketch.api.public_prototypes` filters on
`is_public` with `frappe.get_all`, so the filter is the whole permission check
and nothing else stands between a private Prototype and a stranger. It carries
`allow_guest`, so the case that matters most is the one that calls it with no
session.

The front door is problem 8.1. `sketch/www/sketch.py` sends a signed-out
visitor at `/` here, so the page has to say what Sketch is and offer the way
in. That page is a route of the SPA now (`frontend/src/pages/FeedScreen.vue`),
not a server-rendered template, so the HTTP cases here check that a Guest is
served the bundle and the listing, and the screen itself owns the markup.

The HTTP cases drive the live server, because a Guest session and the website
renderer only exist inside a real request.
"""

import frappe
from frappe.tests import IntegrationTestCase, set_user

from sketch.api import public_prototypes
from sketch.tests import utils

#: Proof the SPA bundle was served. Both come from sketch/www/sketch.html.
BUNDLE_MARKS = ('id="app"', "/assets/sketch/frontend/")

#: The listing endpoint the feed screen reads.
LISTING = "/api/v2/method/sketch.api.public_prototypes"


class TestFeedPage(IntegrationTestCase):
	"""What the server answers on /feed, with no session."""

	def setUp(self):
		utils.require_webserver()

	def test_a_guest_is_served_the_page(self):
		"""No session, no role, one page. The root sends every signed-out
		visitor here, so a login wall would be problem 8.1 again."""
		response = utils.request("GET", "/feed")

		self.assertEqual(response.status_code, 200)

	def test_a_guest_is_served_the_bundle_here(self):
		"""The trade this route makes. /feed is a frappe-ui screen now, so the
		Guest guard in `sketch/www/sketch.py` lets the bundle through on this
		one path and on /about, and on no other."""
		body = utils.request("GET", "/feed").text

		for mark in BUNDLE_MARKS:
			self.assertIn(mark, body)

	def test_a_guest_is_still_refused_the_bundle_elsewhere(self):
		"""The rest of problem B4 stands. A deep link into the app bounces to
		/login before a byte of the bundle is served."""
		response = utils.request("GET", "/settings")

		self.assertEqual(response.status_code, 301)
		for mark in BUNDLE_MARKS:
			self.assertNotIn(mark, response.text)


class TestFeedListing(IntegrationTestCase):
	"""`sketch.api.public_prototypes`, which is the whole feed.

	One user, one public and one private Prototype.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_runtime()
		cls.user = utils.make_user("feed", "d2tfeed")
		cls.addClassCleanup(utils.drop_user, cls.user)

		cls.public = utils.make_prototype(
			cls.user,
			"d2t-feed-public",
			files={"src/App.vue": "<template><h1>public</h1></template>\n"},
			is_public=True,
			title="D2t Feed Public",
		)
		cls.addClassCleanup(utils.drop_prototype, cls.public.name)

		cls.private = utils.make_prototype(
			cls.user,
			"d2t-feed-private",
			files={"src/App.vue": "<template><h1>private</h1></template>\n"},
			is_public=False,
			title="D2t Feed Private",
		)
		cls.addClassCleanup(utils.drop_prototype, cls.private.name)

	def rows(self) -> list[dict]:
		"""The listing as a Guest reads it."""
		with set_user("Guest"):
			return public_prototypes()

	def row_for(self, slug: str) -> dict | None:
		return next((row for row in self.rows() if row["slug"] == slug), None)

	# ------------------------------------------------------------ the listing

	def test_a_public_prototype_is_on_the_feed(self):
		row = self.row_for(self.public.slug)

		self.assertIsNotNone(row)
		self.assertEqual(row["title"], self.public.title)
		self.assertEqual(row["viewer_path"], f"/u/d2tfeed/{self.public.slug}")

	def test_a_private_prototype_is_never_on_the_feed(self):
		"""The one thing this listing must not do. The `is_public` filter is
		the whole permission check, so this is the case that proves it."""
		self.assertIsNone(self.row_for(self.private.slug))

	def test_the_row_carries_the_author(self):
		"""A cross-user feed that does not say who wrote a Prototype is a list
		of orphans. The card draws an Avatar from these two fields and the
		handle beside it (`frontend/src/components/FeedCard.vue`)."""
		row = self.row_for(self.public.slug)

		self.assertEqual(row["username"], "d2tfeed")
		self.assertTrue(row["full_name"])
		self.assertIn("user_image", row)

	def test_the_row_carries_the_file_count(self):
		"""Export is disabled on an empty tree, so the card needs the count."""
		self.assertEqual(self.row_for(self.public.slug)["file_count"], 1)

	def test_the_row_carries_a_link_a_visitor_can_share(self):
		self.assertTrue(
			self.row_for(self.public.slug)["public_url"].endswith(f"/u/d2tfeed/{self.public.slug}")
		)

	def test_the_listing_reads_the_same_with_no_session(self):
		"""The listing must not depend on the caller holding a role. Guest
		holds none at all, and `Sketch User` carries `if_owner`, so a
		permission-checked read would answer differently for each caller."""
		as_owner = [item["viewer_path"] for item in public_prototypes()]

		self.assertEqual(as_owner, [item["viewer_path"] for item in self.rows()])

	def test_a_guest_can_call_it_over_http(self):
		"""`allow_guest` is what makes the front door work. Without it the feed
		screen answers an empty grid to the visitor it exists for."""
		utils.require_webserver()

		response = utils.request("GET", LISTING)

		self.assertEqual(response.status_code, 200, response.text[:400])
		slugs = [row["slug"] for row in response.json()["data"]]
		self.assertIn(self.public.slug, slugs)
		self.assertNotIn(self.private.slug, slugs)

	def test_a_row_whose_owner_has_no_username_is_left_out(self):
		"""`/u/<username>/<slug>` is the only address a Prototype has, so a row
		without one has no link the feed could print."""
		nameless = utils.make_user("feednouser", "d2tfeednouser")
		self.addCleanup(utils.drop_user, nameless)
		doc = utils.make_prototype(nameless, "d2t-feed-nameless", is_public=True)
		self.addCleanup(utils.drop_prototype, doc.name)
		frappe.db.set_value("User", nameless, "username", "")
		frappe.db.commit()

		self.assertIsNone(self.row_for(doc.slug))
