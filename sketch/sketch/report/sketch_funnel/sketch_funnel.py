# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""Desk report: how far a Sketch user gets.

The same six steps the `sketch-funnel` bench command prints, in a table you can
sort, filter and export. Every number comes from `sketch.analytics`, so the two
surfaces can never disagree.

Two columns, two cohorts. **All time** is every account that ever signed up.
**Last N days** is the accounts that signed up inside the window, followed all
the way down: it answers "are the people arriving now getting through", which a
running total cannot.

`Of signups` is the share of that row's own all-time cohort, so it reads as the
funnel's shape rather than as a raw count.
"""

import frappe
from frappe import _

from sketch import analytics


def execute(filters=None):
	frappe.only_for("System Manager")
	days = window(filters)

	all_time = analytics.funnel(analytics.DAWN)
	recent = analytics.funnel(analytics.since_days(days))
	signups = all_time["users"] or 0

	data = [
		{
			"step": _(label),
			"all_time": all_time[key],
			"share": (all_time[key] / signups * 100) if signups else 0,
			"recent": recent[key],
		}
		for label, key in analytics.STEPS
	]
	return columns(days), data


def columns(days: int) -> list:
	return [
		{"fieldname": "step", "label": _("Step"), "fieldtype": "Data", "width": 220},
		{"fieldname": "all_time", "label": _("All time"), "fieldtype": "Int", "width": 100},
		{"fieldname": "share", "label": _("Of signups"), "fieldtype": "Percent", "width": 110},
		{
			"fieldname": "recent",
			"label": _("Signed up in last {0}d").format(days),
			"fieldtype": "Int",
			"width": 170,
		},
	]


def window(filters) -> int:
	"""The `days` filter, defaulting only when Desk sent none.

	`or 7` would be wrong here. Desk sends no filters at all on a report's first
	paint, which is the case the default is for, but it also lets you type 0,
	and 0 is a real window: it means "since this moment". A falsy test cannot
	tell those two apart.
	"""
	days = (filters or {}).get("days")
	return 7 if days is None else int(days)
