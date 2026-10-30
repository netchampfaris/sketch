# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""When a variant file was added to a Prototype.

The tree is plain files and keeps no creation time of its own, so "new" has nothing to
compare against without this. Written by `sketch.badges.stamp` when an agent adds a file
under `src/variants/@<username>/`. A variant with no stamp is never new: a file that
predates this table shows no badge.
"""

import frappe
from frappe.model.document import Document


class SketchVariantStamp(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		path: DF.Data
		prototype: DF.Data
	# end: auto-generated types

	pass


def on_doctype_update():
	"""One row per file."""
	frappe.db.add_unique(
		"Sketch Variant Stamp", ["prototype", "path"], constraint_name="unique_variant_stamp"
	)
