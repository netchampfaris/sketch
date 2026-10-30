# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""What one person has looked at on one Prototype: a variant, or a comment thread.

Written by `sketch.badges.mark` only, through the signed call the Viewer makes. A
Sketch User has no desk access to this table.
"""

import frappe
from frappe.model.document import Document


class SketchSeen(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		item: DF.Data
		kind: DF.Literal["Variant", "Thread"]
		prototype: DF.Data
		seen_at: DF.Datetime
		user: DF.Data
	# end: auto-generated types

	pass


def on_doctype_update():
	"""One row per person, Prototype and thing seen."""
	frappe.db.add_unique(
		"Sketch Seen", ["prototype", "user", "kind", "item"], constraint_name="unique_sketch_seen"
	)
