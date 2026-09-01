# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""`bench --site <site> sketch-funnel`: how far a Sketch user gets.

One command, because one question matters during the beta: of the people who
signed in, how many ever got an agent to write something.

**The funnel needs no event history.** Five of its six steps are states that
Sketch already stored: a role, a token row, a `last_used` stamp, a Prototype
row, a version row. So the funnel answers for every user who ever signed up,
including all of them from before `Sketch Event` existed. Only "a check that
passed" is read from the event table, and that row counts from the day
analytics landed. The report says so on the line itself.

**The diagnostics below the funnel are the opposite.** Auth failures, tool
calls and check outcomes are moments, not states, and none of them was recorded
before `sketch.events`. They fill up from now on.

The cohort is fetched into Python and the steps are counted against it in
memory. That is the readable shape and it holds while Sketch has hundreds of
users, not millions. A beta with tens of accounts is the case this is written
for.
"""

import click
import frappe
from frappe.commands import get_site, pass_context

from sketch import events

#: The role every Sketch account holds. It is what makes a User a Sketch user
#: rather than an Administrator or a system account.
ROLE = "Sketch User"

#: The `since` value that means "no lower bound". Older than any Frappe row.
DAWN = "1900-01-01 00:00:00"


@click.command("sketch-funnel")
@click.option("--days", default=7, help="The window for the recent cohort and the diagnostics.")
@pass_context
def sketch_funnel(context, days):
	"""Print the Sketch signup funnel and what is failing under it."""
	site = get_site(context)
	frappe.init(site=site)
	frappe.connect()
	try:
		click.echo(report(days))
	finally:
		frappe.destroy()


def report(days: int) -> str:
	"""The whole report as one string. Pure read, no write."""
	from frappe.utils import add_days, now_datetime

	since = add_days(now_datetime(), -days)
	lines = [
		"",
		f"Sketch funnel on {frappe.local.site}",
		"",
		f"{'':<24}{'all time':>10}{f'last {days}d':>10}",
	]
	all_time = funnel(DAWN)
	recent = funnel(since)
	for label, key in STEPS:
		lines.append(f"  {label:<22}{all_time[key]:>10}{recent[key]:>10}")

	lines += [
		"",
		"  Each row is counted on its own, so a lower one can be the larger number:",
		"  the SPA creates a Prototype without an agent. The last row reads the event",
		"  table and counts from the day analytics landed; every other row reads a",
		"  state, so it answers for every account that ever signed up.",
	]
	lines += section(f"Why /mcp said no, last {days}d", breakdown(events.AUTH_FAILED, since))
	lines += section(f"Check outcomes, last {days}d", breakdown(events.CHECK, since))
	lines += section(f"Tool calls, last {days}d", tool_calls(since))
	lines.append("")
	return "\n".join(lines)


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


def breakdown(event: str, since: str) -> list:
	"""(detail, count) for one event, biggest first."""
	rows = frappe.db.sql(
		"""
		SELECT detail, COUNT(*) AS n
		FROM `tabSketch Event`
		WHERE event = %(event)s AND creation >= %(since)s
		GROUP BY detail
		ORDER BY n DESC
		""",
		{"event": event, "since": since},
		as_dict=True,
	)
	return [(row.detail or "-", str(row.n)) for row in rows]


def tool_calls(since: str) -> list:
	"""(tool, "N calls, M failed") per tool, busiest first."""
	rows = frappe.db.sql(
		"""
		SELECT detail, COUNT(*) AS n, SUM(1 - ok) AS failed
		FROM `tabSketch Event`
		WHERE event = %(event)s AND creation >= %(since)s
		GROUP BY detail
		ORDER BY n DESC
		""",
		{"event": events.TOOL_CALL, "since": since},
		as_dict=True,
	)
	return [(row.detail or "-", f"{row.n}, {int(row.failed or 0)} failed") for row in rows]


def section(title: str, rows: list) -> list:
	"""One titled block. An empty block says so rather than printing a header
	over nothing."""
	if not rows:
		return ["", title, "  nothing recorded"]

	return ["", title] + [f"  {label:<22}{value:>10}" for label, value in rows]


commands = [sketch_funnel]
