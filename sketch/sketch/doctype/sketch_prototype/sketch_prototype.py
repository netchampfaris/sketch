# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class SketchPrototype(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		is_public: DF.Check
		pin: DF.Data
		slug: DF.Data
		title: DF.Data
	# end: auto-generated types

	def on_trash(self):
		"""Delete the on-disk tree. Without this, orphan directories build up."""
		from sketch.prototype_files import delete_tree

		delete_tree(self.name)


def on_doctype_update():
	"""One slug per owner. Two users can both hold the slug `dashboard`."""
	frappe.db.add_unique("Sketch Prototype", ["owner", "slug"], constraint_name="unique_owner_slug")
