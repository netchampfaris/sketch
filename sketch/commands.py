# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""`bench --site <site> sketch-funnel`: how far a Sketch user gets, as text.

One command, because one question matters during the beta: of the people who
signed in, how many ever got an agent to write something.

Every number comes from `sketch.analytics`, which the two Desk reports read
too. This module owns the terminal rendering and nothing else. Reach for it
over Desk when you want the answer in a shell, a log or a paste.
"""

import click
import frappe
from frappe.commands import get_site, pass_context

from sketch import analytics, events


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
	since = analytics.since_days(days)
	lines = [
		"",
		f"Sketch funnel on {frappe.local.site}",
		"",
		f"{'':<24}{'all time':>10}{f'last {days}d':>10}",
	]
	all_time = analytics.funnel(analytics.DAWN)
	recent = analytics.funnel(since)
	for label, key in analytics.STEPS:
		lines.append(f"  {label:<22}{all_time[key]:>10}{recent[key]:>10}")

	lines += [
		"",
		"  Each row is counted on its own, so a lower one can be the larger number:",
		"  the SPA creates a Prototype without an agent. The last row reads the event",
		"  table and counts from the day analytics landed; every other row reads a",
		"  state, so it answers for every account that ever signed up.",
	]
	lines += section(f"Why /mcp said no, last {days}d", analytics.breakdown(events.AUTH_FAILED, since))
	lines += section(f"Check outcomes, last {days}d", analytics.breakdown(events.CHECK, since))
	lines += section(f"Tool calls, last {days}d", analytics.tool_calls(since))
	lines.append("")
	return "\n".join(lines)


def section(title: str, rows: list) -> list:
	"""One titled block. An empty block says so rather than printing a header
	over nothing."""
	if not rows:
		return ["", title, "  nothing recorded"]

	return ["", title] + [f"  {label:<22}{value:>10}" for label, value in rows]


commands = [sketch_funnel]
