# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The `auth_hooks` entry that resolves a Sketch Token.

Registered as `auth_hooks = ["sketch.auth.validate_sketch_token"]`. Frappe
core calls it from `validate_auth_via_hooks` (`auth.py:772-774`), after its
own OAuth and API-key attempts.

**The hook refuses every path except `/mcp`.** That single check is the whole
security argument for `Sketch Token` over Frappe's `api_key`, which
authenticates every Frappe endpoint. Signup is open to anyone, so a token that
reached more than `/mcp` would hand every new account the whole site.

A token that fails here leaves the session as Guest. Core then raises
`AuthenticationError` for any request that carried an `Authorization` header
(`auth.py:657-658`), so a wrong token gets a 401 without this module raising.
"""

import frappe

# The one path a Sketch Token opens. Do not add a second entry here.
MCP_PATH = "/mcp"

BEARER_PREFIX = "bearer "
TOKEN_PREFIX = "sk_"


def validate_sketch_token() -> None:
	"""Set the session user from `Authorization: Bearer sk_...`, on `/mcp` only."""
	if not _is_mcp_path():
		# Trap 8. Every other path, Desk and API included, is out of reach.
		return

	token = _bearer_token()
	if not token:
		return

	from sketch.sketch.doctype.sketch_token.sketch_token import resolve

	user = resolve(token)
	if not user:
		return

	if frappe.session.user not in ("", "Guest"):
		# A session cookie already logged this request in. Leave it alone.
		return

	frappe.set_user(user)


def _is_mcp_path() -> bool:
	"""True only for the `/mcp` endpoint of this site."""
	request = getattr(frappe.local, "request", None)
	if request is None:
		return False

	return request.path.rstrip("/") == MCP_PATH


def _bearer_token() -> str | None:
	"""The `sk_` token out of the Authorization header, or None."""
	header = frappe.get_request_header("Authorization") or ""
	if not header.lower().startswith(BEARER_PREFIX):
		return None

	token = header[len(BEARER_PREFIX) :].strip()
	return token if token.startswith(TOKEN_PREFIX) else None
