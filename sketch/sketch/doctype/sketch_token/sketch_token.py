# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

import hmac
import secrets

import frappe
from frappe.model.document import Document
from frappe.utils.password import get_decrypted_password

TOKEN_PREFIX = "sk_"


class SketchToken(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		last_used: DF.Datetime | None
		token: DF.Password
		user: DF.Link
	# end: auto-generated types

	pass


def new_token() -> str:
	"""A fresh token. `sk_` plus 32 random bytes, URL-safe."""
	return TOKEN_PREFIX + secrets.token_urlsafe(32)


def get_or_create(user: str | None = None) -> str:
	"""Return the user's token. Create the row on first call.

	The row is owned by the user, so the `if_owner` rules let the user read it.
	"""
	user = user or frappe.session.user
	name = frappe.db.get_value("Sketch Token", {"user": user}, "name")
	if name:
		return get_token(user)

	token = new_token()
	doc = frappe.new_doc("Sketch Token")
	doc.user = user
	doc.token = token
	doc.owner = user
	doc.insert(ignore_permissions=True)
	# The commit is not optional. `get_agent_token` is a GET, and core rolls a
	# GET back at `frappe/app.py:404-407`: it commits only for an unsafe HTTP
	# method or when `flags.commit` is set. Without this the screen shows a
	# token, the row never lands, the next read mints a different one, and no
	# token the user pastes can ever authenticate. This is a deliberate write
	# on a read path, so it commits itself.
	frappe.db.commit()
	# Frappe masks a Password field on the document after save. Return the
	# plain value we generated, never doc.token.
	return token


def get_token(user: str | None = None) -> str:
	"""The stored token in the clear. Raises when the user has no row."""
	user = user or frappe.session.user
	return get_decrypted_password("Sketch Token", user, "token")


def regenerate(user: str | None = None) -> str:
	"""Write a new token over the old one. A write, never a delete."""
	user = user or frappe.session.user
	if not frappe.db.exists("Sketch Token", {"user": user}):
		return get_or_create(user)

	token = new_token()
	doc = frappe.get_doc("Sketch Token", user)
	doc.token = token
	doc.save(ignore_permissions=True)
	return token


def resolve(token: str) -> str | None:
	"""The User that owns this token, or None.

	The token is encrypted at rest with a random IV, so the database cannot be
	queried by value. Every row is decrypted and compared in constant time.
	"""
	if not token or not token.startswith(TOKEN_PREFIX):
		return None

	for row in frappe.get_all("Sketch Token", pluck="user"):
		stored = get_decrypted_password("Sketch Token", row, "token", raise_exception=False)
		if stored and hmac.compare_digest(stored, token):
			return row

	return None
