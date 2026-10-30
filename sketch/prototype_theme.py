# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The theme a person's prototypes open in: light, dark or system.

It is apart from Sketch's own UI theme, which lives in the browser
(`localStorage["theme"]`), so a dark Sketch can show light prototypes. The
Viewer is sandboxed into an opaque origin with no storage, so it cannot read
Sketch's key anyway: the renderer hands it this preference in the payload.

Kept as a user default (`frappe.defaults`), so it needs no field and no
migration. A person who never chose has "system".
"""

import frappe

KEY = "sketch_prototype_theme"
CHOICES = ("light", "dark", "system")
DEFAULT = "system"


def read(user: str) -> str:
	"""This person's preference. "system" for a Guest or a person who never chose."""
	if not user or user == "Guest":
		return DEFAULT

	value = frappe.defaults.get_user_default(KEY, user)
	return value if value in CHOICES else DEFAULT


def write(user: str, value: str) -> str:
	"""Save the preference. Refuses a Guest and anything but the three choices."""
	if not user or user == "Guest":
		raise frappe.PermissionError

	value = (value or "").strip().lower()
	if value not in CHOICES:
		frappe.throw(frappe._("Theme must be light, dark or system"), frappe.ValidationError)

	frappe.defaults.set_user_default(KEY, value, user)
	return value


def subject(username: str) -> str:
	"""What a theme credential covers: one person, on every Prototype."""
	return f"theme|{username}"
