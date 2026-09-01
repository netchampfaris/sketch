# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The card picture: what is stored, who may fetch it, and when it goes stale.

Four jobs, four classes.

`TestThumbnailStore` is the disk. It writes bytes through `thumbnails.store`
rather than through a browser, so it runs with no checkd and no Runtime, and it
is the class that pins the rules a capture cannot express: a theme an earlier
run wrote is kept, an unknown theme is dropped, and the sidecar dates the
pictures against the tree stamp they were taken at.

`TestThumbnailAccess` is the door. Its rules are the Viewer's own (spec 6.3,
`sketch/tests/test_viewer_access.py`): a private Prototype and a Prototype that
does not exist answer the same 404, and neither is a 403. It repeats them here
because `/t/...` is a second renderer with a second copy of the ladder, and a
rule tested once is a rule tested for one of them.

`TestThumbnailRefreshTrigger` is the bill. A capture costs a Chromium run, so
it names who may ask for one: the owner, and nobody else.

`TestThumbnailCapture` is the browser. It is the only class here that needs
checkd and a Runtime on disk, and it skips with a reason when either is absent.
"""

import base64
import json
import os
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase, set_user

from sketch import api, prototype_files, thumbnails
from sketch.tests import utils

#: A 1x1 PNG. The store never decodes a picture, so its only job is to be
#: bytes that arrive whole and come back byte for byte.
PIXEL = base64.b64decode(
	"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
	"YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)
PIXEL_B64 = base64.b64encode(PIXEL).decode()

TREE = {"src/App.vue": "<template><h1>hello</h1></template>\n"}

#: A tree that actually mounts and has one static route. `TREE` above is enough
#: for the two classes that never open a browser, but a capture walks the
#: router: a Prototype with no `src/router.ts` reports no routes, so there is no
#: home route to take a picture of.
MOUNTING_TREE = {
	"src/App.vue": (
		"<script setup lang='ts'>\nimport { RouterView } from 'vue-router'\n</script>\n\n"
		"<template>\n  <div class='h-screen w-full bg-surface-base text-ink-gray-8'>\n"
		"    <RouterView />\n  </div>\n</template>\n"
	),
	"src/pages/Home.vue": (
		"<template>\n  <div class='p-5'>\n"
		"    <h1 class='text-2xl-semibold text-ink-gray-8'>Capture</h1>\n"
		"  </div>\n</template>\n"
	),
	"src/router.ts": (
		"import type { RouteRecordRaw } from 'vue-router'\n"
		"import Home from './pages/Home.vue'\n\n"
		"const routes: RouteRecordRaw[] = [{ path: '/', name: 'Home', component: Home }]\n\n"
		"export default routes\n"
	),
}


def shot(theme: str) -> dict:
	"""One entry of checkd's `thumbnails` list."""
	return {"theme": theme, "route": "/", "png_base64": PIXEL_B64}


class TestThumbnailStore(IntegrationTestCase):
	"""The bytes on disk and the sidecar that dates them."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.user = utils.make_user("thumbstore", "d2tthumbstore")
		cls.addClassCleanup(utils.drop_user, cls.user)

	def setUp(self):
		self.doc = utils.make_prototype(self.user, "d2t-store", files=TREE)
		self.addCleanup(utils.drop_prototype, self.doc.name)

	def rev(self) -> str:
		return prototype_files.revision(self.doc.name)

	def test_a_capture_writes_one_png_per_theme(self):
		written = thumbnails.store(self.doc.name, [shot("light"), shot("dark")], self.rev())

		self.assertEqual(sorted(written), ["dark", "light"])
		for theme in ("light", "dark"):
			self.assertEqual(thumbnails.read(self.doc.name, theme), PIXEL)

	def test_the_sidecar_dates_the_pictures_against_the_tree(self):
		rev = self.rev()
		thumbnails.store(self.doc.name, [shot("light")], rev)
		stored = thumbnails.meta(self.doc.name)

		self.assertEqual(stored["rev"], rev)
		self.assertEqual(stored["themes"], ["light"])
		# `stamp` is the cache key and is new on every call, so it is checked
		# for existence here and for change in
		# `test_two_captures_of_one_tree_land_at_two_urls`.
		self.assertTrue(stored["stamp"])

	def test_a_theme_an_earlier_run_wrote_survives_a_run_without_it(self):
		"""A dark capture that fails must not delete the dark picture on disk.

		checkd leaves a theme out of its answer rather than sending an empty
		one, so "absent" has to mean "keep what is there".
		"""
		thumbnails.store(self.doc.name, [shot("light"), shot("dark")], self.rev())
		thumbnails.store(self.doc.name, [shot("light")], self.rev())

		self.assertEqual(thumbnails.meta(self.doc.name)["themes"], ["dark", "light"])
		self.assertEqual(thumbnails.read(self.doc.name, "dark"), PIXEL)

	def test_a_theme_that_is_not_ours_is_dropped(self):
		written = thumbnails.store(self.doc.name, [shot("system"), shot("light")], self.rev())

		self.assertEqual(written, ["light"])
		self.assertFalse(os.path.exists(os.path.join(thumbnails.thumb_dir(self.doc.name), "system.png")))

	def test_a_run_that_wrote_nothing_leaves_no_sidecar(self):
		"""A tree that never mounted returns no thumbnails, and that is not a
		capture. Writing a sidecar for it would date pictures that do not
		exist, and the next read would call them fresh."""
		self.assertEqual(thumbnails.store(self.doc.name, [], self.rev()), [])
		self.assertEqual(thumbnails.meta(self.doc.name), {})

	def test_the_state_is_missing_then_fresh_then_stale(self):
		self.assertEqual(thumbnails.state(self.doc.name), "missing")

		thumbnails.store(self.doc.name, [shot("light")], self.rev())
		self.assertEqual(thumbnails.state(self.doc.name), "fresh")

		prototype_files.write_files(self.doc.name, [{"path": "src/Two.vue", "content": "<template />\n"}])
		self.assertEqual(thumbnails.state(self.doc.name), "stale")

	def test_the_pictures_live_outside_the_source_tree(self):
		"""A PNG under `private/files/sketch/<name>/` would be listed as a file
		of the Prototype, counted in the line under the card title, and would
		move the revision the sidecar is compared against."""
		before = prototype_files.revision(self.doc.name)
		thumbnails.store(self.doc.name, [shot("light"), shot("dark")], before)

		self.assertEqual(prototype_files.revision(self.doc.name), before)
		self.assertEqual([row["path"] for row in prototype_files.list_files(self.doc.name)], ["src/App.vue"])

	def test_deleting_the_prototype_deletes_its_pictures(self):
		thumbnails.store(self.doc.name, [shot("light")], self.rev())
		folder = thumbnails.thumb_dir(self.doc.name)
		self.assertTrue(os.path.isdir(folder))

		utils.drop_prototype(self.doc.name)
		self.assertFalse(os.path.isdir(folder))

	def test_a_gallery_row_names_only_the_themes_on_disk(self):
		with self.set_user(self.user):
			self.assertIsNone(self.row()["thumbnail"])

			thumbnails.store(self.doc.name, [shot("light")], self.rev())
			self.assertEqual(list(self.row()["thumbnail"]), ["light"])

			thumbnails.store(self.doc.name, [shot("dark")], self.rev())
			self.assertEqual(sorted(self.row()["thumbnail"]), ["dark", "light"])

	def test_a_row_url_carries_the_capture_stamp(self):
		"""The stamp is the cache key. Without it the renderer refuses to send
		a year-long cache header, because the same URL would answer with
		different bytes after the next capture."""
		thumbnails.store(self.doc.name, [shot("light")], self.rev())

		with self.set_user(self.user):
			url = self.row()["thumbnail"]["light"]

		stamp = thumbnails.stamp(self.doc.name)
		self.assertEqual(url, f"/t/d2tthumbstore/d2t-store/light.png?rev={stamp}")

	def test_two_captures_of_one_tree_land_at_two_urls(self):
		"""The Refresh preview case. A capture leaves the tree untouched, so
		keying the URL on the tree revision would send the second picture to a
		URL the browser already holds under a year-long cache, and the user
		would go on seeing the old one."""
		rev = self.rev()
		thumbnails.store(self.doc.name, [shot("light")], rev)
		with self.set_user(self.user):
			first = self.row()["thumbnail"]["light"]

		thumbnails.store(self.doc.name, [shot("light")], rev)
		with self.set_user(self.user):
			second = self.row()["thumbnail"]["light"]

		self.assertEqual(self.rev(), rev, "the capture must not move the tree")
		self.assertNotEqual(first, second)

	def test_a_sidecar_with_no_stamp_still_has_a_cache_key(self):
		"""A capture written before `stamp` existed. It keeps a URL a browser
		can cache rather than losing one."""
		thumbnails.store(self.doc.name, [shot("light")], self.rev())
		path = os.path.join(thumbnails.thumb_dir(self.doc.name), thumbnails.META)
		with open(path, "w", encoding="utf-8") as handle:
			handle.write(json.dumps({"rev": self.rev(), "themes": ["light"]}))

		self.assertEqual(thumbnails.stamp(self.doc.name), self.rev())

	def row(self) -> dict:
		return [item for item in api.list_prototypes() if item["name"] == self.doc.name][0]


class TestThumbnailAccess(IntegrationTestCase):
	"""Who /t/<username>/<slug>/<theme>.png serves. Spec 6.3, second copy."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.user = utils.make_user("thumbweb", "d2tthumbweb")
		cls.addClassCleanup(utils.drop_user, cls.user)
		cls.username = utils.username_of(cls.user)

		cls.public = utils.make_prototype(cls.user, "d2t-shot-public", files=TREE, is_public=True)
		cls.addClassCleanup(utils.drop_prototype, cls.public.name)
		cls.private = utils.make_prototype(cls.user, "d2t-shot-private", files=TREE, is_public=False)
		cls.addClassCleanup(utils.drop_prototype, cls.private.name)

		for doc in (cls.public, cls.private):
			thumbnails.store(doc.name, [shot("light"), shot("dark")], prototype_files.revision(doc.name))

	def setUp(self):
		utils.require_webserver()

	def get(self, path: str, **kwargs):
		return utils.request("GET", path, **kwargs)

	def path(self, slug: str, theme: str = "light") -> str:
		return f"/t/{self.username}/{slug}/{theme}.png"

	def test_a_stranger_gets_the_picture_of_a_public_prototype(self):
		answer = self.get(self.path("d2t-shot-public"))

		self.assertEqual(answer.status_code, 200, answer.text[:400])
		self.assertEqual(answer.headers["content-type"], "image/png")
		self.assertEqual(answer.content, PIXEL)

	def test_both_themes_are_served(self):
		for theme in ("light", "dark"):
			answer = self.get(self.path("d2t-shot-public", theme))
			self.assertEqual(answer.status_code, 200, f"{theme}: {answer.text[:200]}")

	def test_a_private_picture_answers_like_a_missing_one(self):
		private = self.get(self.path("d2t-shot-private"))
		missing = self.get(self.path("d2t-no-such-slug"))

		self.assertEqual(private.status_code, 404, private.text[:400])
		self.assertEqual(missing.status_code, 404, missing.text[:400])

	def test_the_owner_gets_their_own_private_picture(self):
		answer = self.get(self.path("d2t-shot-private"), headers=utils.api_auth_header(self.user))

		self.assertEqual(answer.status_code, 200, answer.text[:400])
		self.assertEqual(answer.content, PIXEL)

	def test_a_theme_that_is_not_ours_is_not_a_path(self):
		"""`system` is a preference, never a picture (spec 12). It must 404
		before the lookup runs, so no theme name can address a file."""
		self.assertEqual(self.get(self.path("d2t-shot-public", "system")).status_code, 404)

	def test_a_prototype_with_no_capture_answers_404(self):
		"""The ordinary state of a new Prototype. The card reads the 404 and
		draws its placeholder."""
		doc = utils.make_prototype(self.user, "d2t-shot-none", files=TREE, is_public=True)
		self.addCleanup(utils.drop_prototype, doc.name)

		self.assertEqual(self.get(self.path("d2t-shot-none")).status_code, 404)

	def test_any_cache_at_all_needs_a_stamp_in_the_url(self):
		"""Without a stamp the same URL answers with different bytes after the
		next capture, so nothing may hold it."""
		bare = self.get(self.path("d2t-shot-public"))

		self.assertEqual(bare.headers["cache-control"], "no-cache")

	def test_a_public_picture_is_held_for_ten_minutes_and_no_longer(self):
		"""The unpublish window. `api.set_public` writes the field and nothing
		else: no new stamp, no purge. A year of `immutable` in a shared cache
		would go on serving the picture of a Prototype the origin now 404s."""
		rev = prototype_files.revision(self.public.name)
		answer = self.get(f"{self.path('d2t-shot-public')}?rev={rev}")

		self.assertEqual(answer.headers["cache-control"], "public, max-age=600")
		self.assertNotIn("immutable", answer.headers["cache-control"])

	def test_a_private_picture_is_never_cached_by_a_shared_cache(self):
		"""A proxy that stored it would hand it to the next caller without the
		ladder above running. One browser may hold it for a year: the URL
		carries the capture stamp, and its owner can clear it."""
		rev = prototype_files.revision(self.private.name)
		answer = self.get(
			f"{self.path('d2t-shot-private')}?rev={rev}", headers=utils.api_auth_header(self.user)
		)

		self.assertEqual(answer.headers["cache-control"], "private, max-age=31536000, immutable")


class TestThumbnailRefreshTrigger(IntegrationTestCase):
	"""Who may spend a Chromium run. Review 3.9.

	`_card_image` used to ask for a capture whenever the picture was not
	fresh, and `public_prototypes` carries `allow_guest`. A POST to it commits,
	so the `enqueue_after_commit` jobs fire, and a stranger reading the feed
	bought one browser run per stale card. A tree that never mounts writes no
	sidecar, so it stays stale and is re-queued on every read for ever.

	No case here starts a browser: `thumbnails.request_refresh` is the thing
	under test, so it is replaced by a probe.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.user = utils.make_user("thumbbill", "d2tthumbbill")
		cls.addClassCleanup(utils.drop_user, cls.user)
		cls.reader = utils.make_user("thumbread", "d2tthumbread")
		cls.addClassCleanup(utils.drop_user, cls.reader)

		# Public, and never captured, which is the shape the exploit uses: a
		# tree that does not compile stays "missing" for ever.
		cls.doc = utils.make_prototype(cls.user, "d2t-bill", files=TREE, is_public=True)
		cls.addClassCleanup(utils.drop_prototype, cls.doc.name)

	def feed(self, user: str) -> list[dict]:
		"""The feed as `user` reads it, and every capture it asked for."""
		with patch.object(thumbnails, "request_refresh") as probe:
			with set_user(user):
				rows = api.public_prototypes()

		self.asked_for = [call.args[0] for call in probe.call_args_list]
		return rows

	def row_for(self, rows: list[dict]) -> dict | None:
		return next((row for row in rows if row["slug"] == self.doc.slug), None)

	def test_a_guest_read_of_the_feed_queues_no_capture(self):
		"""The finding. No session, no browser."""
		self.feed("Guest")

		self.assertEqual(self.asked_for, [])

	def test_a_signed_in_stranger_queues_no_capture_either(self):
		"""A session is not ownership. The card is public to look at, not to
		spend the site's browsers on."""
		self.feed(self.reader)

		self.assertEqual(self.asked_for, [])

	def test_the_owner_reading_the_feed_still_queues_one(self):
		"""The owner is who the refresh is for, so their own read of the feed
		keeps working the way the gallery does."""
		self.feed(self.user)

		self.assertIn(self.doc.name, self.asked_for)

	def test_the_owner_gallery_read_still_queues_one(self):
		"""`list_prototypes` is the owner's own screen, so nothing changes
		there. `_row` reads `owner` off the row for that."""
		with patch.object(thumbnails, "request_refresh") as probe:
			with set_user(self.user):
				api.list_prototypes()

		self.assertIn(self.doc.name, [call.args[0] for call in probe.call_args_list])

	def test_a_guest_still_sees_the_card(self):
		"""The feed must not break. A stranger reads the row and the picture
		on disk; only the capture is the owner's."""
		thumbnails.store(self.doc.name, [shot("light")], "not-the-current-revision")
		self.addCleanup(thumbnails.forget, self.doc.name)

		row = self.row_for(self.feed("Guest"))

		self.assertEqual(thumbnails.state(self.doc.name), "stale")
		self.assertEqual(self.asked_for, [])
		self.assertEqual(list(row["thumbnail"]), ["light"])


class TestThumbnailCapture(IntegrationTestCase):
	"""One real capture, in a real browser. Needs checkd and a Runtime."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.user = utils.make_user("thumbshot", "d2tthumbshot")
		cls.addClassCleanup(utils.drop_user, cls.user)

	def setUp(self):
		utils.require_runtime()
		utils.require_checkd()
		utils.require_webserver()
		self.doc = utils.make_prototype(self.user, "d2t-capture", files=MOUNTING_TREE)
		self.addCleanup(utils.drop_prototype, self.doc.name)

	def test_a_capture_writes_a_real_png_in_both_themes(self):
		with self.set_user(self.user):
			written = thumbnails.capture(self.doc.name)

		self.assertEqual(sorted(written), ["dark", "light"])
		self.assertEqual(thumbnails.state(self.doc.name), "fresh")
		for theme in ("light", "dark"):
			data = thumbnails.read(self.doc.name, theme)
			self.assertTrue(data.startswith(b"\x89PNG\r\n"), f"{theme} is not a PNG")

	def test_the_two_themes_are_not_the_same_picture(self):
		"""The whole point of a second capture. A dark card that showed the
		light screenshot would read as broken, not as stale."""
		with self.set_user(self.user):
			thumbnails.capture(self.doc.name)

		self.assertNotEqual(
			thumbnails.read(self.doc.name, "light"), thumbnails.read(self.doc.name, "dark")
		)

	def test_refresh_preview_re_takes_the_picture_and_answers_with_the_row(self):
		"""The manual door. The reply carries a URL the browser has not seen,
		even though the tree did not move."""
		with self.set_user(self.user):
			thumbnails.capture(self.doc.name)
			before = api.list_prototypes()
			before_url = [r for r in before if r["name"] == self.doc.name][0]["thumbnail"]["light"]

			row = api.refresh_preview("d2t-capture")

		self.assertEqual(sorted(row["thumbnail"]), ["dark", "light"])
		self.assertNotEqual(row["thumbnail"]["light"], before_url)

	def test_refresh_preview_says_so_when_the_prototype_does_not_render(self):
		"""A queued job that dies leaves the same stale picture with nothing
		said. This one was asked for, so it fails out loud."""
		with self.set_user(self.user):
			prototype_files.write_files(
				self.doc.name, [{"path": "src/App.vue", "content": "<template><h1>unclosed\n"}]
			)
			with self.assertRaises(frappe.ValidationError) as caught:
				api.refresh_preview("d2t-capture")

		self.assertIn("did not render", str(caught.exception))

	def test_refresh_preview_is_not_a_door_into_somebody_elses_prototype(self):
		"""`resolve_owned` is the guard, the same one every other action on
		this menu uses. The test is here because this method reaches a browser
		and a private file, which the others do not."""
		stranger = utils.make_user("thumbstranger", "d2tthumbstranger")
		self.addCleanup(utils.drop_user, stranger)

		with self.set_user(stranger):
			with self.assertRaises(frappe.DoesNotExistError):
				api.refresh_preview("d2t-capture")

	def test_a_tree_that_never_mounts_keeps_the_picture_it_has(self):
		"""checkd answers a broken tree with no thumbnails, and no thumbnails
		writes nothing, so a compile error does not blank the card."""
		with self.set_user(self.user):
			thumbnails.capture(self.doc.name)
			before = thumbnails.read(self.doc.name, "light")

			prototype_files.write_files(
				self.doc.name, [{"path": "src/App.vue", "content": "<template><h1>unclosed\n"}]
			)
			self.assertEqual(thumbnails.capture(self.doc.name), [])

		self.assertEqual(thumbnails.read(self.doc.name, "light"), before)
		self.assertEqual(thumbnails.state(self.doc.name), "stale")
