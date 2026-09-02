# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The two Desk reports, and the one rule they share with the bench command.

`sketch.analytics` is the only place that counts. The reports and
`sketch-funnel` render it, so a number can never differ between the terminal
and Desk. These cases hold that: each report is compared against the module it
reads, not against a number written out by hand.

Both reports are operator surfaces. `Sketch Event` holds every account's tool
calls, so a Sketch User must not reach either one.
"""

import frappe
from frappe.tests import IntegrationTestCase

from sketch import analytics, events
from sketch.sketch.report.sketch_agent_activity import sketch_agent_activity
from sketch.sketch.report.sketch_funnel import sketch_funnel
from sketch.tests import utils

#: The two reports this app ships, and the module each one renders.
REPORTS = ("Sketch Funnel", "Sketch Agent Activity")


class TestReports(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.user = utils.make_user("rep", "d2trep")
		cls.addClassCleanup(utils.drop_user, cls.user)

	def setUp(self):
		frappe.set_user("Administrator")
		self.addCleanup(frappe.set_user, "Administrator")
		# `frappe.local` outlives every case in a run, and nothing in a test
		# process ends a request, so events buffered by earlier modules are
		# still sitting here. Left alone they fill the cap and this module's own
		# probes are dropped, which is exactly how this line was earned.
		events._buffer()[:] = []

	# ------------------------------------------------------------ registered

	def test_both_reports_are_standard_and_enabled(self):
		"""A standard report lives in the app, so `bench migrate` is the only
		thing that can install it. A missing row means the folder is wrong."""
		for name in REPORTS:
			with self.subTest(report=name):
				doc = frappe.get_doc("Report", name)
				self.assertEqual(doc.is_standard, "Yes")
				self.assertEqual(doc.report_type, "Script Report")
				self.assertEqual(doc.module, "Sketch")
				self.assertEqual(doc.ref_doctype, "Sketch Event")
				self.assertFalse(doc.disabled)
				self.assertEqual([row.role for row in doc.roles], ["System Manager"])

	# ---------------------------------------------------------------- funnel

	def test_the_funnel_report_is_the_funnel_module(self):
		"""One source of truth. If these ever disagree, Desk is lying."""
		columns, data = sketch_funnel.execute({"days": 7})
		expected = analytics.funnel(analytics.DAWN)

		self.assertEqual([row["step"] for row in data], [label for label, _ in analytics.STEPS])
		for (label, key), row in zip(analytics.STEPS, data, strict=True):
			with self.subTest(step=label):
				self.assertEqual(row["all_time"], expected[key])

		self.assertEqual(columns[0]["fieldname"], "step")

	def test_the_window_column_names_the_window(self):
		"""The filter is the only thing that says what the last column counts,
		so the label has to carry it."""
		columns, _ = sketch_funnel.execute({"days": 30})
		self.assertIn("30", columns[-1]["label"])

	def test_the_share_column_is_a_share_of_signups(self):
		columns, data = sketch_funnel.execute({"days": 7})
		self.assertEqual(columns[2]["fieldtype"], "Percent")
		if data[0]["all_time"]:
			self.assertEqual(data[0]["share"], 100.0)

	def test_a_missing_filter_falls_back_and_does_not_raise(self):
		"""Desk sends no filters on the first paint of a report."""
		self.assertTrue(sketch_funnel.execute()[1])
		self.assertEqual(sketch_agent_activity.execute()[1], sketch_agent_activity.execute({})[1])

	# -------------------------------------------------------------- activity

	def test_a_recorded_event_reaches_the_activity_report(self):
		events.record(events.TOOL_CALL, user=self.user, ok=False, detail="d2t-report-probe")
		events.flush()
		self.addCleanup(frappe.db.delete, "Sketch Event", {"detail": "d2t-report-probe"})

		_, data = sketch_agent_activity.execute({"days": 7})
		row = next(item for item in data if item["item"] == "d2t-report-probe")
		self.assertEqual(row["group"], "Tool call")
		self.assertEqual(row["count"], 1)
		self.assertEqual(row["not_ok"], 1)
		self.assertEqual(row["fail_rate"], 100.0)

	def test_an_event_outside_the_window_is_not_counted(self):
		events.record(events.TOOL_CALL, user=self.user, detail="d2t-report-probe")
		events.flush()
		self.addCleanup(frappe.db.delete, "Sketch Event", {"detail": "d2t-report-probe"})

		# A zero-day window starts now, so a row written a moment ago is out.
		_, data = sketch_agent_activity.execute({"days": 0})
		self.assertNotIn("d2t-report-probe", [item["item"] for item in data])

	def test_an_unnamed_event_still_shows_under_its_own_name(self):
		"""A new event must be visible before `GROUPS` is updated for it,
		or the report hides the thing it was opened to find."""
		events.record("d2t_unmapped", user=self.user, detail="d2t-report-probe")
		events.flush()
		self.addCleanup(frappe.db.delete, "Sketch Event", {"detail": "d2t-report-probe"})

		_, data = sketch_agent_activity.execute({"days": 7})
		row = next(item for item in data if item["item"] == "d2t-report-probe")
		self.assertEqual(row["group"], "d2t_unmapped")

	# ----------------------------------------------------------- permissions

	def test_a_sketch_user_reaches_neither_report(self):
		frappe.set_user(self.user)
		for module in (sketch_funnel, sketch_agent_activity):
			with self.subTest(report=module.__name__):
				with self.assertRaises(frappe.PermissionError):
					module.execute({"days": 7})
