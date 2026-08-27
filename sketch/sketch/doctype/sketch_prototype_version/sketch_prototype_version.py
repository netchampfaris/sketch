# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class SketchPrototypeVersion(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		changes: DF.LongText | None
		files_added: DF.Int
		files_deleted: DF.Int
		files_modified: DF.Int
		prompt: DF.LongText
		prototype: DF.Link
		sequence: DF.Int
		summary: DF.Data | None
	# end: auto-generated types

	pass
