# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The read side of product analytics. Every number Sketch reports comes from
here.

`sketch.events` writes. This module counts. They are split because three
callers now ask the same questions and none of them should hold its own copy of
a query: the `sketch-funnel` bench command, and the two Desk reports under
`sketch/sketch/report/`.

**The funnel needs no event history.** Five of its six steps are states Sketch
already stored: a role, a token row, a `last_used` stamp, a Prototype row, a
version row. So the funnel answers for every user who ever signed up, including
all of them from before `Sketch Event` existed. Only "a check that passed"
reads the event table, and that row counts from the day analytics landed.

**Activity is the opposite.** Auth failures, tool calls, check outcomes and
Viewer opens are moments, not states, so they fill up from the day
`sketch.events` landed and never answer for a day before it.

The cohort is fetched into Python and the steps are counted against it in
memory. That is the readable shape and it holds while Sketch has hundreds of
users, not millions. A beta with tens of accounts is the case this is written
for.
"""

import frappe

from sketch import events

#: The role every Sketch account holds. It is what makes a User a Sketch user
#: rather than an Administrator or a system account.
ROLE = "Sketch User"

#: The `since` value that means "no lower bound". Older than any Frappe row.
DAWN = "1900-01-01 00:00:00"

#: The funnel, top to bottom. Each row is counted on its own, against the same
#: cohort, so a lower number can be larger than the one above it. Two real cases
#: do that, and neither is a bug: the SPA creates a Prototype without any agent,
#: so "wrote a prototype" can beat "agent connected"; and "a check that passed"
#: reads the event table, which started later than every other row here.
STEPS = (
	("signed in", "users"),
	("token minted", "token"),
	("agent connected", "connected"),
	("wrote a prototype", "prototype"),
	("committed a version", "committed"),
	("a check that passed", "checked"),
)

#: How each recorded event is named in the activity report, and the order the
#: groups are printed in. An event missing from here still shows, under its own
#: raw name, so a new event is visible before this line is updated.
GROUPS = (
	(events.TOOL_CALL, "Tool call"),
	(events.CHECK, "Check"),
	(events.AUTH_FAILED, "Auth failure"),
	(events.VIEWER_OPEN, "Viewer open"),
	(events.AGENT_CONNECTED, "Agent connected"),
)


def since_days(days: int) -> str:
	"""The timestamp `days` ago, as the queries below want it."""
	from frappe.utils import add_days, now_datetime

	return add_days(now_datetime(), -int(days or 0))


def funnel(since: str) -> dict:
	"""Count one cohort through every step. `since` filters on signup date."""
	users = cohort(since)
	if not users:
		return dict.fromkeys([key for _, key in STEPS], 0)

	tokens = {
		row.user: row.last_used
		for row in frappe.get_all(
			"Sketch Token", filters={"user": ("in", users)}, fields=["user", "last_used"]
		)
	}
	prototypes = frappe.get_all(
		"Sketch Prototype", filters={"owner": ("in", users)}, fields=["name", "owner"]
	)
	owner_of = {row.name: row.owner for row in prototypes}
	versioned = frappe.get_all(
		"Sketch Prototype Version",
		filters={"prototype": ("in", list(owner_of))} if owner_of else {"prototype": ("in", [""])},
		pluck="prototype",
		distinct=True,
	)
	passed = frappe.get_all(
		"Sketch Event",
		filters={"event": events.CHECK, "ok": 1, "user": ("in", users)},
		pluck="user",
		distinct=True,
	)
	return {
		"users": len(users),
		"token": len(tokens),
		"connected": len([1 for stamp in tokens.values() if stamp]),
		"prototype": len({row.owner for row in prototypes}),
		"committed": len({owner_of[name] for name in versioned}),
		"checked": len(set(passed)),
	}


def cohort(since: str) -> list:
	"""Every enabled account that holds the Sketch role, created since `since`.

	The role and not the presence of a token: a user who never opened Settings
	has no token row, and they are the top of the funnel, not outside it.

	`Has Role` is a child table of User, so this is one join and not two reads.
	"""
	return frappe.db.sql_list(
		"""
		SELECT u.name
		FROM `tabUser` u
		JOIN `tabHas Role` r ON r.parent = u.name AND r.parenttype = 'User'
		WHERE r.role = %(role)s AND u.enabled = 1 AND u.creation >= %(since)s
		""",
		{"role": ROLE, "since": since},
	)


def activity(since: str) -> list:
	"""Every recorded event since `since`, grouped by name and discriminator.

	One query for the whole activity report. `not_ok` is meaningful for every
	group, not only for tool calls: a `compile-failed` check and an
	`invalid_token` request are both recorded with `ok = 0`, so the column reads
	the same way everywhere.

	Groups come out in `GROUPS` order, and each group's rows come out busiest
	first. An event `GROUPS` does not name sorts last, under its own raw name,
	so a newly recorded event is visible without touching this module.
	"""
	rows = frappe.db.sql(
		"""
		SELECT event, detail, COUNT(*) AS n, SUM(1 - ok) AS not_ok
		FROM `tabSketch Event`
		WHERE creation >= %(since)s
		GROUP BY event, detail
		""",
		{"since": since},
		as_dict=True,
	)
	label_of = dict(GROUPS)
	order = {name: index for index, (name, _) in enumerate(GROUPS)}
	rows.sort(key=lambda row: (order.get(row.event, len(order)), -row.n))
	return [
		{
			"group": label_of.get(row.event, row.event),
			"item": row.detail or "-",
			"count": int(row.n),
			"not_ok": int(row.not_ok or 0),
		}
		for row in rows
	]


def breakdown(event: str, since: str) -> list:
	"""(detail, count) for one event, biggest first. The text report uses it."""
	return [(row["item"], str(row["count"])) for row in activity(since) if row["group"] == _label(event)]


def tool_calls(since: str) -> list:
	"""(tool, "N, M failed") per tool, busiest first. The text report uses it."""
	return [
		(row["item"], f"{row['count']}, {row['not_ok']} failed")
		for row in activity(since)
		if row["group"] == _label(events.TOOL_CALL)
	]


def _label(event: str) -> str:
	return dict(GROUPS).get(event, event)
