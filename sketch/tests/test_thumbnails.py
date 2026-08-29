# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The card picture: what is stored, who may fetch it, and when it goes stale.

Three jobs, three classes.

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

`TestThumbnailCapture` is the browser. It is the only class here that needs
checkd and a Runtime on disk, and it skips with a reason when either is absent.
"""

import base64
import os

import frappe
from frappe.tests import IntegrationTestCase

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

		self.assertEqual(thumbnails.meta(self.doc.name), {"rev": rev, "themes": ["light"]})

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

	def test_a_row_url_carries_the_tree_stamp(self):
		"""The stamp is the cache key. Without it the renderer refuses to send
		a year-long cache header, because the same URL would answer with
		different bytes after the next capture."""
		rev = self.rev()
		thumbnails.store(self.doc.name, [shot("light")], rev)

		with self.set_user(self.user):
			url = self.row()["thumbnail"]["light"]

		self.assertEqual(url, f"/t/d2tthumbstore/d2t-store/light.png?rev={rev}")

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

	def test_a_year_of_cache_needs_a_stamp_in_the_url(self):
		rev = prototype_files.revision(self.public.name)
		stamped = self.get(f"{self.path('d2t-shot-public')}?rev={rev}")
		bare = self.get(self.path("d2t-shot-public"))

		self.assertEqual(stamped.headers["cache-control"], "public, max-age=31536000, immutable")
		self.assertEqual(bare.headers["cache-control"], "no-cache")

	def test_a_private_picture_is_never_cached_by_a_shared_cache(self):
		"""A proxy that stored it would hand it to the next caller without the
		ladder above running."""
		rev = prototype_files.revision(self.private.name)
		answer = self.get(
			f"{self.path('d2t-shot-private')}?rev={rev}", headers=utils.api_auth_header(self.user)
		)

		self.assertEqual(answer.headers["cache-control"], "private, max-age=31536000, immutable")


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
