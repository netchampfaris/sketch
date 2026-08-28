# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""A legal Sketch username for a user who signs up with GitHub.

`frappe.utils.oauth.get_user_record` builds the User for a social sign-in
(`frappe/utils/oauth.py:278-310`) and never writes `username`. Core then
derives one with `frappe.scrub(self.first_name)`
(`frappe/core/doctype/user/user.py:766-768`), which lowercases the value and
turns a hyphen or a space into an underscore. `sketch.user_hooks` refuses that
value, so the browser shows a 417 page with a traceback.

This module writes the field first, so nothing is left for core to derive. It
is a `before_insert` doc_event. `Document.insert` runs `before_insert` at
`frappe/model/document.py:733`, ahead of `run_before_save_methods` (line 739)
and `_validate` (line 740). So the name is in place before core's
`validate_username` and before the Sketch hook read it.

The rules stay in `sketch.user_hooks`. This module imports them. It does not
repeat them.
"""

import re

import frappe

from sketch.user_hooks import (
	USERNAME_MAX_LENGTH,
	USERNAME_MIN_LENGTH,
	USERNAME_PATTERN,
	is_taken,
	normalise,
)

#: The name for a login that holds no usable character at all.
FALLBACK_USERNAME = "sketch-user"

#: Put in front of a name that starts with a digit.
LETTER_PREFIX = "u-"

#: Added to the end of a name that is shorter than the minimum length.
PAD_CHARACTER = "0"

#: How many `-2`, `-3` counters to try before a random suffix is used.
MAX_COLLISION_TRIES = 1000

#: Number of characters in that random suffix.
HASH_LENGTH = 8

#: Every character a Sketch username cannot hold.
ILLEGAL_CHARACTERS = re.compile(r"[^a-z0-9-]")

#: Two or more hyphens together.
REPEATED_HYPHENS = re.compile(r"-{2,}")


def fit(value: str) -> str:
	"""Cut a name to the maximum length and remove a hyphen left at the end."""
	return value[:USERNAME_MAX_LENGTH].rstrip("-")


def with_suffix(base: str, suffix: str) -> str:
	"""Join a base and a suffix, and keep the total inside the maximum length.

	The base is cut short so the suffix always survives. A hyphen exposed at
	the cut is removed, or the join makes a doubled hyphen.
	"""
	head = base[: USERNAME_MAX_LENGTH - len(suffix)].rstrip("-")
	if not head:
		head = FALLBACK_USERNAME[: USERNAME_MAX_LENGTH - len(suffix)].rstrip("-")
	return head + suffix


def derive_username(seed: str | None) -> str:
	"""Turn any login or display name into a legal Sketch username.

	The answer matches `user_hooks.USERNAME_PATTERN` and holds between
	`USERNAME_MIN_LENGTH` and `USERNAME_MAX_LENGTH` characters. It is not
	compared with the users that already exist, see `unique_username`.

	The function never raises. Any seed at all gives a usable name.
	"""
	value = ILLEGAL_CHARACTERS.sub("-", normalise(seed))
	value = REPEATED_HYPHENS.sub("-", value).strip("-")

	# The first character must be a letter, so "7ktn" becomes "u-7ktn".
	if value and not value[0].isalpha():
		value = LETTER_PREFIX + value

	if not value:
		value = FALLBACK_USERNAME

	value = fit(value)

	while len(value) < USERNAME_MIN_LENGTH:
		value += PAD_CHARACTER

	# A last guard. The steps above cover every seed, and this keeps a future
	# change to the rules from letting a bad name through.
	return value if USERNAME_PATTERN.match(value) else FALLBACK_USERNAME


def unique_username(seed: str | None, exclude: str | None = None) -> str:
	"""A legal username that no other User holds.

	A taken name gets a counter: `octocat`, then `octocat-2`, `octocat-3`. The
	search stops after `MAX_COLLISION_TRIES` and uses a random suffix, so a
	crowded name cannot make the signup slow.
	"""
	base = derive_username(seed)
	if not is_taken(base, exclude=exclude):
		return base

	for counter in range(2, MAX_COLLISION_TRIES + 2):
		candidate = with_suffix(base, f"-{counter}")
		if not is_taken(candidate, exclude=exclude):
			return candidate

	return with_suffix(base, "-" + frappe.generate_hash(length=HASH_LENGTH))


def social_login_row(doc):
	"""The first `social_logins` row that names a provider, or None."""
	for row in doc.get("social_logins") or []:
		if row.get("provider"):
			return row
	return None


def set_username_for_social_signup(doc, method=None) -> None:
	"""The `User.before_insert` hook. Social sign-ups only.

	It acts only when the document has no username and holds a social login
	row. A Desk-created user arrives with a username, or with no social login
	row, so it passes through untouched.

	GitHub puts the account login in the row's `username` field
	(`frappe/utils/oauth.py:332`). That login is the best seed. The display
	name is the fallback, because a provider can send no login at all.
	"""
	if normalise(doc.get("username")):
		return

	row = social_login_row(doc)
	if row is None:
		return

	doc.username = unique_username(row.get("username") or doc.get("first_name"))
