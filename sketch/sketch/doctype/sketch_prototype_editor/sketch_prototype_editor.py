# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""One invited editor of one Prototype.

A row means: this person's agent may add variants to that Prototype, and this
person may view and comment on it while it is private. Every write goes through
`sketch.sharing`, which only the owner's Share dialog reaches. A Sketch User has
no desk access to this table.
"""

import frappe
from frappe.model.document import Document


class SketchPrototypeEditor(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		prototype: DF.Data
		user: DF.Link
	# end: auto-generated types

	pass


def on_doctype_update():
	"""One row per person and Prototype."""
	frappe.db.add_unique(
		"Sketch Prototype Editor", ["prototype", "user"], constraint_name="unique_prototype_editor"
	)
