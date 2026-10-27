# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""One comment on a live Prototype: the first of a thread, or a reply to it.

Every write goes through `sketch.comments`, one row at a time, so a deleted
comment can never be written back by a stale page. A Sketch User has no desk
access to this table.
"""

from frappe.model.document import Document


class SketchComment(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		anchor: DF.LongText | None
		author: DF.Data
		edited: DF.Check
		mentions: DF.SmallText | None
		prototype: DF.Data
		resolved: DF.Check
		text: DF.LongText | None
		thread: DF.Data | None
	# end: auto-generated types

	pass
