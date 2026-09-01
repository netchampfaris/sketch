# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""Delete every Sketch Token that names a user other than its owner.

Until this patch a Sketch User held `create` on the doctype, and Frappe never
applies `if_owner` to `create`. `Document.insert` forces only `owner`, so the
`user` Link field stayed caller-controlled: a REST insert of
`{"user": "victim@example.com", "token": "sk_chosen"}` minted a working /mcp
credential for the victim. `sketch.auth` trusts the `user` field as the
identity, so such a row is an account takeover.

`SketchToken.validate` now refuses to write one. This removes any row an
attacker already planted. A row minted by Sketch always has `user == owner`,
so nothing legitimate is deleted.

`delete_doc` and not a raw delete: the secret lives in `__Auth`, and only the
document delete clears it.
"""

import frappe


def execute():
	if not frappe.db.table_exists("Sketch Token"):
		return

	for row in frappe.get_all("Sketch Token", fields=["name", "user", "owner"]):
		if row.user == row.owner:
			continue

		frappe.logger("sketch").warning(f"dropping Sketch Token {row.name}: it names {row.user}, owner is {row.owner}")
		frappe.delete_doc("Sketch Token", row.name, force=True, ignore_permissions=True)
