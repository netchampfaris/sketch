# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""One inline browser run per account, and the slot always comes back.

`checkd.run` is a blocking POST on the web worker. Two doors reach it with a
session: the `check` tool and `api.refresh_preview`. Without a claim, one
account with many agents pins every worker on the site for the whole checkd
deadline.

The claim is a Redis key with SET NX EX, because `cache().set_value` carries no
`if_not_exists` on this Frappe version. Two properties matter as much as the
claim itself:

- `run` gives the slot back on the way out, on success and on failure. A
  crashed check that kept the key would lock the account out for the cooldown.
- Only the request that took the claim gives it back. A background thumbnail
  job calls `run` without claiming, and must not free an inline check's slot.

No case here starts a browser. The three cases that could reach `checkd.run`
point `checkd.URL` at a closed port, so the POST fails on connect and the
release path still runs. No other case reaches `run`: the claim is taken
already, or the tree has no revision, or the slug belongs to somebody else.

The last class is not about the lock. It covers the other half of a failed
check: the line the agent reads.
"""

import unittest
from unittest.mock import patch

import requests

import frappe
from frappe.tests import IntegrationTestCase

from sketch import api, checkd
from sketch.mcp import tools
from sketch.tests import utils

SLUG = "d2t-lock"

#: A Prototype with no files. `thumbnails.capture` answers a tree with no
#: revision without opening a browser, so `run` never runs and never releases.
EMPTY_SLUG = "d2t-lock-empty"

#: The Prototype `TestCheckFailureText` checks. Its own, because that class
#: replaces `checkd.run` and so never gives its claim back through it.
FAULT_SLUG = "d2t-lock-fault"

#: A port nothing listens on. `run` fails on connect, which is a failure the
#: release path must survive.
DEAD_URL = "http://127.0.0.1:9/check"


class TestCheckLock(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_runtime()
		if not frappe.cache().connected():
			raise unittest.SkipTest("redis is not reachable, so the claim cannot be tested")

		cls.owner = utils.make_user("lock", "d2tlock")
		cls.other = utils.make_user("lockb", "d2tlockb")
		cls.doc = utils.make_prototype(cls.owner, SLUG, files={"src/App.vue": "<template><div/></template>\n"})
		cls.empty = utils.make_prototype(cls.owner, EMPTY_SLUG)

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		utils.drop_prototype(cls.doc.name)
		utils.drop_prototype(cls.empty.name)
		for email in (cls.owner, cls.other):
			utils.drop_user(email)
		frappe.db.commit()
		super().tearDownClass()

	def setUp(self):
		super().setUp()
		self.free_the_slots()
		self.addCleanup(self.free_the_slots)
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user(self.owner)

	def free_the_slots(self):
		"""Drop every claim this class can take.

		The key lives for COOLDOWN_SECONDS, which is longer than the suite
		takes to reach the next case.
		"""
		frappe.local.sketch_check_slot = None
		for email in (self.owner, self.other):
			frappe.cache().delete(checkd.slot_key(email))

	# ----------------------------------------------------------- the claim

	def test_a_second_claim_for_one_user_is_refused(self):
		checkd.claim_slot()

		with self.assertRaises(frappe.ValidationError) as caught:
			checkd.claim_slot()

		self.assertIn("already running", str(caught.exception))

	def test_the_claim_is_per_user(self):
		"""One busy account must not stop everybody else's check."""
		checkd.claim_slot()

		frappe.set_user(self.other)
		checkd.claim_slot()

	def test_a_released_slot_is_free_again(self):
		checkd.claim_slot()
		checkd.release_slot()

		checkd.claim_slot()

	# --------------------------------------------------- the release in run

	def test_a_failed_run_gives_the_slot_back(self):
		"""The crash case. A held key would lock the account out for 20 s."""
		checkd.claim_slot()

		with patch.object(checkd, "URL", DEAD_URL):
			with self.assertRaises(frappe.ValidationError):
				checkd.run(self.doc)

		checkd.claim_slot()

	def test_a_run_that_never_claimed_frees_nothing(self):
		"""The background thumbnail job. It calls `run` with no claim of its
		own, so it must leave an inline check's slot alone."""
		checkd.claim_slot()
		# The job is another request, and another request holds no flag.
		frappe.local.sketch_check_slot = None

		with patch.object(checkd, "URL", DEAD_URL):
			with self.assertRaises(frappe.ValidationError):
				checkd.run(self.doc)

		with self.assertRaises(frappe.ValidationError):
			checkd.claim_slot()

	# ------------------------------------------------------- the check tool

	def test_the_check_tool_claims_before_it_opens_a_browser(self):
		"""`do_check` claims ahead of `checkd.run`, so a second check answers
		from the claim and never starts a browser."""
		checkd.claim_slot()

		reply = tools.call_tool("check", {"prototype": SLUG})

		self.assertTrue(reply["isError"])
		self.assertIn("already running", reply["content"][0]["text"])

	# ------------------------------------------------------- refresh preview

	def test_refresh_preview_claims_before_it_opens_a_browser(self):
		"""The second door. It runs the browser inline on the web worker, so
		one account with many tabs would hold every worker on the site.

		`URL` is a closed port, so a regression here fails on connect rather
		than opening a real browser."""
		checkd.claim_slot()

		with patch.object(checkd, "URL", DEAD_URL):
			with self.assertRaises(frappe.ValidationError) as caught:
				api.refresh_preview(SLUG)

		self.assertIn("already running", str(caught.exception))

	def test_refresh_preview_gives_the_slot_back_when_it_opens_no_browser(self):
		"""`capture` answers a tree with no revision without calling `run`, so
		the release in `run` never happens. An empty Prototype must not lock
		the account out for the cooldown."""
		with self.assertRaises(frappe.ValidationError) as caught:
			api.refresh_preview(EMPTY_SLUG)

		self.assertIn("did not render", str(caught.exception))
		checkd.claim_slot()

	def test_refresh_preview_on_somebody_elses_slug_costs_no_cooldown(self):
		"""The claim is taken after `resolve_owned`, so a slug the caller does
		not own is refused for free."""
		frappe.set_user(self.other)

		with self.assertRaises(frappe.DoesNotExistError):
			api.refresh_preview(SLUG)

		checkd.claim_slot()

	# ---------------------------------------------------------- the timeout

	def test_the_client_gives_up_just_after_checkd_does(self):
		"""checkd caps a check at 30 s. Every second past that is a web worker
		another request cannot have."""
		self.assertGreater(checkd.TIMEOUT, 30)
		self.assertLessEqual(checkd.TIMEOUT, 35)


class TestCheckFailureText(IntegrationTestCase):
	"""What a failed check tells the agent.

	`tools.call_tool` hides the absolute path an OSError carries, because it
	names the bench root and the private files layout. It must hide it by the
	`filename` on the exception and not by the class: OSError is a much wider
	family than the filesystem. `requests.exceptions.RequestException` is one,
	and `checkd.run` lets it out, because it catches ConnectionError and
	Timeout and nothing else. A dispatcher that calls every OSError a failed
	write answers a dropped connection with "the file could not be written",
	and the agent then reads the tree for a fault that is on the wire.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_runtime()
		cls.owner = utils.make_user("lockmsg", "d2tlockmsg")
		cls.doc = utils.make_prototype(cls.owner, FAULT_SLUG)

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		utils.drop_prototype(cls.doc.name)
		utils.drop_user(cls.owner)
		frappe.db.commit()
		super().tearDownClass()

	def setUp(self):
		super().setUp()
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user(self.owner)
		# `do_check` claims a real slot, and the release lives in `run`, which
		# this class replaces. So the claim is dropped by hand.
		self.addCleanup(frappe.cache().delete, checkd.slot_key(self.owner))
		self.addCleanup(setattr, frappe.local, "sketch_check_slot", None)

	def test_a_network_fault_in_check_is_not_reported_as_a_write(self):
		"""The fault the check path really raises. The reply has to name it."""
		fault = requests.exceptions.ChunkedEncodingError("Connection broken: IncompleteRead")

		with patch.object(checkd, "run", side_effect=fault):
			reply = tools.call_tool("check", {"prototype": FAULT_SLUG})

		text = reply["content"][0]["text"]
		self.assertTrue(reply["isError"])
		self.assertNotIn("could not be written", text)
		self.assertIn("Connection broken", text)

	def test_a_filesystem_error_still_hides_the_path(self):
		"""The other half. A real file error carries `filename`, so it gets the
		fixed line and the path stays in the log."""
		fault = OSError(21, "Is a directory", "/home/x/sites/site/private/files/sketch/abc/src")

		text = tools.failure_text("write_files", fault)

		self.assertEqual(text, "write_files failed: the file could not be written.")
		self.assertNotIn("/private/files", text)


if __name__ == "__main__":
	unittest.main()
