# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The "Updated" line must mean that the agent changed this Prototype.

`set_public` calls `doc.save()`, and the gallery used to read and sort on
`Sketch Prototype.modified`. Flipping the public switch therefore reset the
card to "Updated 1 second ago" and threw it to the head of the grid, so every
other card moved out from under the pointer (review 5.7).

`_content_modified` (`sketch/api.py:116-145`) now stamps the newest mtime in
the on-disk tree, and `list_prototypes` sorts on that same value
(`sketch/api.py:255-262`). A document write is invisible to both. Only an agent
writing a file is a change the user asked for.

Every mtime here is forced with `os.utime`, so the order is fixed and no case
depends on how fast the run is. No web server is needed; a Runtime is, because
a Prototype pins one.
"""

import os
import time

import frappe
from frappe.tests import IntegrationTestCase, set_user
from frappe.utils import get_datetime, now_datetime

from sketch import api, prototype_files
from sketch.tests import utils

#: The fixture tree. Two files, so a case can prove the stamp reads the newest
#: one and not the first one walked.
FILES = {
	"src/App.vue": "<template><RouterView /></template>\n",
	"src/pages/Home.vue": "<template><h1>hi</h1></template>\n",
}

HOUR = 3600

#: How far a read stamp may sit from the mtime that was written. Wide enough
#: that a slow run never fails, far tighter than the 5h30m an unconverted epoch
#: stamp is out by on the default site timezone.
TOLERANCE_SECONDS = 120

#: What an agent writing a file looks like.
A_WRITE = [{"path": "src/pages/Home.vue", "content": "<template><h1>new</h1></template>\n"}]


class TestContentStamp(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_runtime()
		cls.user = utils.make_user("stamp", "d2tstamp")
		cls.addClassCleanup(utils.drop_user, cls.user)
		cls.older = utils.make_prototype(cls.user, "d2t-stamp-older", files=FILES)
		cls.addClassCleanup(utils.drop_prototype, cls.older.name)
		cls.newer = utils.make_prototype(cls.user, "d2t-stamp-newer", files=FILES)
		cls.addClassCleanup(utils.drop_prototype, cls.newer.name)

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		super().tearDownClass()

	def setUp(self):
		# Every case starts from one fixed order: older at 3 hours, newer at 1
		# hour. A case that writes a file changes that for itself only.
		self.backdate(self.older.name, 3 * HOUR)
		self.backdate(self.newer.name, 1 * HOUR)

	# ------------------------------------------------------------- helpers

	def backdate(self, name: str, seconds_ago: float, path: str | None = None) -> None:
		"""Move the mtime of one file, or of the whole tree, into the past."""
		stamp = time.time() - seconds_ago
		paths = [path] if path else [row["path"] for row in prototype_files.list_files(name)]
		for rel in paths:
			os.utime(prototype_files.safe_join(name, rel), (stamp, stamp))

	def rows(self) -> dict:
		"""The gallery this user sees, keyed by slug."""
		with set_user(self.user):
			return {row["slug"]: row for row in api.list_prototypes()}

	def order(self) -> list:
		"""The fixture slugs in the order the gallery lays them out."""
		return [slug for slug in self.rows() if slug.startswith("d2t-stamp-")]

	def stamp_of(self, slug: str) -> str:
		return self.rows()[slug]["modified"]

	def age_of(self, slug: str) -> float:
		"""How many seconds ago the card says this Prototype was updated."""
		return (now_datetime() - get_datetime(self.stamp_of(slug))).total_seconds()

	def doc_modified(self, name: str):
		return frappe.db.get_value("Sketch Prototype", name, "modified")

	# ------------------------------------------------------- what it reads

	def test_the_stamp_is_the_newest_file_in_the_tree(self):
		"""One file moves, the other stays at three hours. The newer wins."""
		self.backdate(self.older.name, 60, path="src/pages/Home.vue")

		self.assertAlmostEqual(self.age_of("d2t-stamp-older"), 60, delta=TOLERANCE_SECONDS)

	def test_the_stamp_reads_the_site_clock_and_not_utc(self):
		"""`pretty_date` subtracts against `now_datetime()`, which is the site
		timezone. An epoch mtime printed raw reads hours out, and on a site
		east of UTC it prints a time in the future."""
		self.assertAlmostEqual(self.age_of("d2t-stamp-newer"), HOUR, delta=TOLERANCE_SECONDS)

	def test_the_stamp_is_not_the_documents_own_field(self):
		"""The regression in one line. The fixture was inserted seconds ago and
		its files are three hours old, so the two fields cannot agree."""
		document_age = (now_datetime() - get_datetime(self.doc_modified(self.older.name))).total_seconds()

		self.assertAlmostEqual(self.age_of("d2t-stamp-older"), 3 * HOUR, delta=TOLERANCE_SECONDS)
		self.assertLess(document_age, TOLERANCE_SECONDS)

	def test_the_card_prints_a_relative_time_from_the_stamp(self):
		"""`updated` is the string the card shows. A blank one is a card with
		no "Updated" line at all."""
		self.assertTrue(self.rows()["d2t-stamp-older"]["updated"])

	def test_the_gallery_is_ordered_by_the_stamp(self):
		self.assertEqual(self.order(), ["d2t-stamp-newer", "d2t-stamp-older"])

	# ------------------------------------------- what must not move a card

	def test_turning_public_on_leaves_the_updated_time_alone(self):
		"""The regression itself. This card read "Updated 1 second ago"."""
		before = self.stamp_of("d2t-stamp-older")
		document_before = self.doc_modified(self.older.name)

		self.publish("d2t-stamp-older", True)

		# The control. A `set_public` that saved nothing would pass without it.
		self.assertNotEqual(self.doc_modified(self.older.name), document_before)
		self.assertEqual(self.stamp_of("d2t-stamp-older"), before)

	def test_turning_public_off_leaves_the_updated_time_alone(self):
		"""Both directions are a `doc.save()`, so both carried the bug."""
		self.publish("d2t-stamp-older", True)
		before = self.stamp_of("d2t-stamp-older")

		self.publish("d2t-stamp-older", False)

		self.assertEqual(self.stamp_of("d2t-stamp-older"), before)

	def test_turning_public_on_leaves_the_gallery_order_alone(self):
		"""The oldest card is the one toggled, because it has the furthest to
		travel. It used to land at the head of the grid."""
		before = self.order()

		self.publish("d2t-stamp-older", True)

		self.assertEqual(self.order(), before)

	def test_renaming_leaves_the_updated_time_alone(self):
		"""`rename_prototype` is the same `doc.save()`. Naming a Prototype is
		not the agent writing to it."""
		before = self.stamp_of("d2t-stamp-older")

		with set_user(self.user):
			api.rename_prototype("d2t-stamp-older", "D2t Stamp Older Renamed")
			self.addCleanup(self.rename_back, "d2t-stamp-older", self.older.title)

		self.assertEqual(self.stamp_of("d2t-stamp-older"), before)

	# ----------------------------------------------- what must move a card

	def test_writing_a_file_moves_the_updated_time(self):
		"""The control for every case above. A stamp that never moves is a
		gallery that never reports an agent's work."""
		before = self.stamp_of("d2t-stamp-older")

		prototype_files.write_files(self.older.name, A_WRITE)

		self.assertNotEqual(self.stamp_of("d2t-stamp-older"), before)
		self.assertLess(self.age_of("d2t-stamp-older"), TOLERANCE_SECONDS)

	def test_writing_a_file_moves_the_prototype_to_the_top(self):
		self.assertEqual(self.order(), ["d2t-stamp-newer", "d2t-stamp-older"])

		prototype_files.write_files(self.older.name, A_WRITE)

		self.assertEqual(self.order(), ["d2t-stamp-older", "d2t-stamp-newer"])

	# ----------------------------------------------------- the empty tree

	def test_an_empty_tree_reports_when_it_was_created(self):
		"""A Prototype with no files has no mtime to read. The fallback is
		`creation`, never `modified`: `modified` is the field that moves on a
		visibility toggle, which is the jump this stamp exists to stop."""
		doc = utils.make_prototype(self.user, "d2t-stamp-empty")
		self.addCleanup(utils.drop_prototype, doc.name)

		self.assertEqual(self.rows()["d2t-stamp-empty"]["modified"], str(doc.creation))

		self.publish("d2t-stamp-empty", True)

		self.assertEqual(self.rows()["d2t-stamp-empty"]["modified"], str(doc.creation))

	# ------------------------------------------------------------ cleanup

	def publish(self, slug: str, is_public: bool) -> None:
		"""Toggle Public as the owner, and put it back when the case ends."""
		with set_user(self.user):
			api.set_public(slug, is_public)

		if is_public:
			self.addCleanup(self.publish, slug, False)

	def rename_back(self, slug: str, title: str) -> None:
		with set_user(self.user):
			api.rename_prototype(slug, title)
