# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""Desk report: what the agents did, and what failed.

One flat table over every recorded event, grouped by the event and its
discriminator. Four groups today: a tool call names its tool, a check names its
outcome, an auth failure names which of the four ways it failed, a Viewer open
names owner against public.

`Not ok` reads the same way in every group, because every group records it the
same way: a tool that raised, a check that did not compile, a refused request.
For a `compile-failed` row, `Count` and `Not ok` are equal by construction, and
that is the honest reading.

Unlike the funnel, nothing here answers for a day before `sketch.events`
landed. These are moments, and no table kept them until then.
"""

import frappe
from frappe import _

from sketch import analytics


def execute(filters=None):
	frappe.only_for("System Manager")
	days = window(filters)

	data = [
		{
			**row,
			"group": _(row["group"]),
			"fail_rate": (row["not_ok"] / row["count"] * 100) if row["count"] else 0,
		}
		for row in analytics.activity(analytics.since_days(days))
	]
	return columns(), data


def columns() -> list:
	return [
		{"fieldname": "group", "label": _("Group"), "fieldtype": "Data", "width": 140},
		{"fieldname": "item", "label": _("Item"), "fieldtype": "Data", "width": 220},
		{"fieldname": "count", "label": _("Count"), "fieldtype": "Int", "width": 90},
		{"fieldname": "not_ok", "label": _("Not ok"), "fieldtype": "Int", "width": 90},
		{"fieldname": "fail_rate", "label": _("Not ok %"), "fieldtype": "Percent", "width": 110},
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
