# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""Fill `token_hash` on every Sketch Token minted before the field existed.

`resolve` now finds one row by `token_hash` instead of decrypting every row.
A row with an empty hash matches nothing, so the agent holding that token
would get a 401 until the user pressed Regenerate. This decrypts each row once
and stores the digest.

A row whose secret cannot be decrypted is left alone. That token already
resolved to nobody, because the compare it used to fail is the same compare
`resolve` still makes.
"""

import frappe
from frappe.utils.password import get_decrypted_password

from sketch.sketch.doctype.sketch_token.sketch_token import token_hash


def execute():
	for name in frappe.get_all("Sketch Token", filters={"token_hash": ("is", "not set")}, pluck="name"):
		token = get_decrypted_password("Sketch Token", name, "token", raise_exception=False)
		if not token:
			frappe.logger("sketch").warning(f"Sketch Token {name} has no readable secret; no hash written")
			continue

		frappe.db.set_value("Sketch Token", name, "token_hash", token_hash(token), update_modified=False)
