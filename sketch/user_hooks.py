"""Sketch username rules on the core User doctype.

`validate_username` is a `doc_events` hook on `User.validate`. `Document.hook`
composes the doc method first and the app hooks after it, so this code sees the
value that core's own `validate_username` already wrote or blanked.

Scope: Sketch users only. The hook fires on every User save on the site, so an
unscoped throw stops Desk user management. `user_type` alone is not enough:
`User.set_system_user()` writes "Website User" on any new user that holds no
role with desk access, so a Desk-created System User passes through that test
before its roles are added. A user is in scope when it holds the `Sketch User`
role.
"""

import re

import frappe
from frappe import _

USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 30

# Starts with a letter. Lowercase letters, digits and single hyphens after it.
# No doubled hyphen, no trailing hyphen.
USERNAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")

SKETCH_ROLE = "Sketch User"

SYSTEM_USERS = ("Administrator", "Guest")


def normalise(value: str | None) -> str:
	"""Trim and lowercase a username. Returns an empty string for None."""
	return (value or "").strip().lower()


def check_format(value: str) -> None:
	"""Raise `frappe.ValidationError` with a readable message on a bad username.

	The value must already be normalised. Order of the checks decides which
	message the person reads, so keep the most useful ones first.
	"""
	title = _("Invalid Username")

	if not value:
		frappe.throw(_("A username is required."), title=title)

	if len(value) < USERNAME_MIN_LENGTH:
		frappe.throw(
			_("The username {0} is too short. Use at least {1} characters.").format(
				value, USERNAME_MIN_LENGTH
			),
			title=title,
		)

	if len(value) > USERNAME_MAX_LENGTH:
		frappe.throw(
			_("The username {0} is too long. Use at most {1} characters.").format(
				value, USERNAME_MAX_LENGTH
			),
			title=title,
		)

	if not re.match(r"^[a-z]", value):
		frappe.throw(
			_("The username {0} must start with a letter.").format(value),
			title=title,
		)

	if not re.match(r"^[a-z0-9-]+$", value):
		frappe.throw(
			_("The username {0} can use only lowercase letters, numbers and hyphens.").format(value),
			title=title,
		)

	if "--" in value:
		frappe.throw(
			_("The username {0} has two hyphens together. Use one.").format(value),
			title=title,
		)

	if value.endswith("-"):
		frappe.throw(
			_("The username {0} ends with a hyphen. Remove it.").format(value),
			title=title,
		)

	if not USERNAME_PATTERN.match(value):
		frappe.throw(
			_("The username {0} is not allowed.").format(value),
			title=title,
		)


def is_taken(value: str, exclude: str | None = None) -> bool:
	"""True when another User already holds this username."""
	filters: dict = {"username": value}
	if exclude:
		filters["name"] = ("!=", exclude)
	return bool(frappe.db.exists("User", filters))


def in_scope(doc) -> bool:
	"""True when the Sketch username rules apply to this User document."""
	if doc.get("user_type") != "Website User":
		return False
	if doc.name in SYSTEM_USERS:
		return False
	return any(row.role == SKETCH_ROLE for row in (doc.get("roles") or []))


def validate_username(doc, method=None) -> None:
	"""The `User.validate` hook. Sketch users only, see `in_scope`.

	Four jobs:
	1. Keep the username frozen after sign-up.
	2. Turn core's silent blanking of a colliding name into a readable throw.
	3. Enforce the Sketch format.
	4. Normalise the stored value to lowercase.
	"""
	if not in_scope(doc):
		return

	before = None if doc.is_new() else doc.get_doc_before_save()

	# 1. Frozen after sign-up. A collision on a later save also lands here,
	# because core blanks the field and the value then differs.
	if before is not None and before.get("username"):
		if normalise(doc.username) != normalise(before.username):
			frappe.throw(
				_("The username {0} cannot be changed.").format(before.username),
				title=_("Username Is Fixed"),
			)
		doc.username = normalise(doc.username)
		return

	# 2. Core blanked the value. For a Website User it says nothing at all.
	if not doc.username:
		if doc.is_new():
			frappe.throw(
				_("A username is required, and it may already be taken."),
				title=_("Invalid Username"),
			)
		return

	# 3 and 4.
	value = normalise(doc.username)
	check_format(value)

	if is_taken(value, exclude=doc.name):
		frappe.throw(
			_("The username {0} is already taken. Choose another.").format(value),
			title=_("Username Taken"),
		)

	doc.username = value
