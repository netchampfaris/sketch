# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""/feed, the public listing and the front door.

Two jobs, and both are checked here.

The listing must never leak. `sketch.api.public_prototypes` filters on
`is_public` with `frappe.get_all`, so the filter is the whole permission check
and nothing else stands between a private Prototype and a stranger.

The front door is problem 8.1. `sketch/www/sketch.py` sends a signed-out
visitor at `/` here, so the page has to say what Sketch is and offer the way
in. A page that lost either would be worse than the redirect to /login it
replaced.

The HTTP cases drive the live server, because a Guest session and the website
renderer only exist inside a real request. The two cases that need a fixed
page size call `get_context` instead: the site holds whatever public
Prototypes it holds, and a case that depends on the count of them is a case
that fails on somebody else's data.
"""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase, set_user

from sketch.api import public_prototypes
from sketch.tests import utils
from sketch.www import feed

#: Proof the SPA bundle was served. Both come from sketch/www/sketch.html.
BUNDLE_MARKS = ('id="app"', "/assets/sketch/frontend/")

#: The one line that says what Sketch is. `sketch/www/login.html:30` prints the
#: same sentence, so the two Guest pages never describe the product twice.
WHAT_SKETCH_IS = "Sketch renders frappe-ui prototypes that your own agent writes over MCP."

#: A title that is markup. Frappe's Jinja environment does not autoescape
#: (`frappe/utils/jinja.py:66`), so every user-written value in the template
#: carries `| e` and this case is what holds it there.
#:
#: `<b>`, not `<script>`. Frappe runs a Data field through `sanitize_html` on
#: save, which drops a script block outright but keeps `<b>` and keeps
#: `<img src=x>`, so a stored title can still hold live markup and `<script>`
#: would pass this case for the wrong reason.
UNSAFE_TITLE = "d2t feed <b>bold</b>"


class TestFeed(IntegrationTestCase):
	"""The served page. One user, one public and one private Prototype."""

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

	def setUp(self):
		utils.require_webserver()

	def get_feed(self) -> str:
		"""The page as a Guest reads it."""
		response = utils.request("GET", "/feed")
		self.assertEqual(response.status_code, 200)
		return response.text

	# ------------------------------------------------------- a Guest reads it

	def test_a_guest_can_read_the_feed(self):
		"""No session, no role, one page. The root now sends every signed-out
		visitor here, so a login wall would be problem 8.1 again."""
		body = self.get_feed()

		self.assertIn('class="sk-shell"', body)
		self.assertIn("Public prototypes", body)

	def test_the_page_says_what_sketch_is_and_offers_the_way_in(self):
		"""Finding 8.1. One sentence before the ask, and the ask itself."""
		body = self.get_feed()

		self.assertIn(WHAT_SKETCH_IS, body)
		self.assertIn('href="/login"', body)

	def test_the_page_carries_no_solid_button(self):
		"""The standing rule (commit 54f7fdc)."""
		self.assertNotIn('data-variant="solid"', self.get_feed())

	def test_a_guest_never_downloads_the_bundle_here_either(self):
		"""The front door moved, so the B4 guard has to move with it."""
		body = self.get_feed()

		for mark in BUNDLE_MARKS:
			self.assertNotIn(mark, body)

	# ------------------------------------------------------------ the listing

	def test_a_public_prototype_is_on_the_feed(self):
		"""Title and Viewer link, for a Prototype the reader does not own."""
		body = self.get_feed()

		self.assertIn(self.public.title, body)
		self.assertIn(f'href="/u/d2tfeed/{self.public.slug}"', body)

	def test_a_private_prototype_is_never_on_the_feed(self):
		"""The one thing this page must not do. The `is_public` filter is the
		whole permission check, so this is the case that proves it."""
		body = self.get_feed()

		self.assertNotIn(self.private.title, body)
		self.assertNotIn(f"/u/d2tfeed/{self.private.slug}", body)

	def test_the_author_is_named(self):
		"""A cross-user feed that does not say who wrote a Prototype is a list
		of orphans. The username is also the first half of its address."""
		self.assertIn("d2tfeed", self.get_feed())

	def test_a_link_opens_in_a_new_tab_with_noopener(self):
		"""`noopener` is not optional. The Viewer runs prototype code somebody
		else's agent wrote, and without it that page holds a live
		`window.opener` handle to this one
		(`frontend/src/components/PrototypeCard.vue:77`)."""
		body = self.get_feed()

		row = body[body.find(f'href="/u/d2tfeed/{self.public.slug}"') :][:200]

		self.assertIn('rel="noopener"', row)
		self.assertIn('target="_blank"', row)

	def test_a_title_that_is_markup_is_escaped(self):
		"""A title is user-written and this page is public, so an unescaped one
		puts a stranger's markup on the front door.

		Vue escapes the same title in the SPA card, so both surfaces print the
		tag as text and neither renders it.
		"""
		doc = utils.make_prototype(
			self.user,
			"d2t-feed-unsafe",
			is_public=True,
			title=UNSAFE_TITLE,
		)
		self.addCleanup(utils.drop_prototype, doc.name)

		body = self.get_feed()

		self.assertNotIn(UNSAFE_TITLE, body)
		self.assertIn("d2t feed &lt;b&gt;bold&lt;/b&gt;", body)


class TestFeedContext(IntegrationTestCase):
	"""The page size and the truncation line, with no web server.

	`get_context` is called directly, so the case fixes PAGE_SIZE instead of
	the number of public Prototypes on the site.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_runtime()
		cls.user = utils.make_user("feedcap", "d2tfeedcap")
		cls.addClassCleanup(utils.drop_user, cls.user)

		for slug in ("d2t-cap-one", "d2t-cap-two"):
			doc = utils.make_prototype(cls.user, slug, is_public=True)
			cls.addClassCleanup(utils.drop_prototype, doc.name)

	def test_the_page_stops_at_the_page_size(self):
		"""A cap the page never mentions is a silent truncation."""
		with patch.object(feed, "PAGE_SIZE", 1):
			context = feed.get_context(frappe._dict())

		self.assertEqual(len(context.prototypes), 1)
		self.assertGreater(context.total, 1)
		self.assertTrue(context.capped)

	def test_a_page_that_holds_everything_says_nothing(self):
		"""`capped` is false when nothing was left out, so the line that
		announces a cap cannot appear on a page that has none."""
		with patch.object(feed, "PAGE_SIZE", 10_000):
			context = feed.get_context(frappe._dict())

		self.assertEqual(len(context.prototypes), context.total)
		self.assertFalse(context.capped)

	def test_the_listing_reads_the_same_with_no_session(self):
		"""The listing must not depend on the caller holding a role. Guest
		holds none at all, and `Sketch User` carries `if_owner`, so a
		permission-checked read would answer differently for each caller."""
		as_owner = [item["viewer_path"] for item in public_prototypes()]

		with set_user("Guest"):
			as_guest = [item["viewer_path"] for item in public_prototypes()]

		self.assertEqual(as_owner, as_guest)
		self.assertIn("/u/d2tfeedcap/d2t-cap-one", as_guest)

	def test_the_listing_holds_no_private_prototype(self):
		"""The same guard as the page, one layer down."""
		doc = utils.make_prototype(self.user, "d2t-cap-private", is_public=False)
		self.addCleanup(utils.drop_prototype, doc.name)

		paths = [item["viewer_path"] for item in public_prototypes()]

		self.assertNotIn("/u/d2tfeedcap/d2t-cap-private", paths)
