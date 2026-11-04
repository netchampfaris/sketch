# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""Move every Prototype off a retired Runtime, onto frappe-ui 1.1.0.

Only 1.1.0 is left in runtime/versions/, so build-all.sh builds one Runtime and
removes the others' output. A Prototype pinned to 1.0.0, 1.0.0-rc.2 or
1.0.0-beta.55 would find no Runtime, so it moves to 1.1.0 and keeps its old Pin
in `moved_from_pin`: the owner sees a notice once (viewer.shell_payload).

The target is fixed here, not read from the build output: a patch may run
before the build. A rerun finds nothing left to move.
"""

import frappe

TARGET = "1.1.0"


def execute():
	move()


def move(names: list[str] | None = None) -> None:
	"""Move every Prototype off a retired Pin, or only `names` (the tests' own, on a shared database)."""
	filters = {"pin": ["!=", TARGET]}
	if names is not None:
		filters["name"] = ["in", names]
	for row in frappe.get_all("Sketch Prototype", filters=filters, fields=["name", "pin"]):
		frappe.db.set_value(
			"Sketch Prototype",
			row.name,
			{"pin": TARGET, "moved_from_pin": row.pin},
			update_modified=False,
		)
