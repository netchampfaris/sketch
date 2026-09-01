# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""One row per thing that happened. Written by `sketch.events`, read by nobody
inside the app.

The doctype is deliberately thin: no validation, no hooks, no lifecycle. It is
a log, and a log that can refuse a write is a log that changes the behaviour of
the code it watches. `sketch.events.record` is the only writer, and it swallows
every failure of its own, so nothing here may throw.

A Sketch User cannot read this table. It is operator data: it holds one row per
tool call across every account, so any read of it is a read across users.
"""

from frappe.model.document import Document


class SketchEvent(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		detail: DF.Data | None
		event: DF.Data
		ms: DF.Int
		ok: DF.Check
		prototype: DF.Data | None
		user: DF.Link | None
	# end: auto-generated types

	pass
