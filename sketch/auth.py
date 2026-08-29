# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The `auth_hooks` entry that resolves a Sketch Token.

Registered as `auth_hooks = ["sketch.auth.validate_sketch_token"]`. Frappe
core calls it from `validate_auth_via_hooks` (`frappe/auth.py:772-774`), after
its own OAuth and API-key attempts.

**The hook refuses every path except `/mcp`.** That single check is the whole
security argument for `Sketch Token` over Frappe's `api_key`, which
authenticates every Frappe endpoint. Signup is open to anyone, so a token that
reached more than `/mcp` would hand every new account the whole site.

**A failure raises here, and nowhere later.** Core calls `validate_auth()` at
`frappe/app.py:80`, before `get_response()` at `frappe/app.py:115`, so a
`page_renderer` never sees a bad token. `validate_auth_via_hooks` discards the
hook return value (`frappe/auth.py:772-774`), so there is no return contract
and raising is the only stop. Left alone, core raises `frappe.AuthenticationError`
(`frappe/auth.py:657-658`) and renders an 8 KB HTML page an agent cannot read.

One failure is answered even earlier. Core tries its own API keys at
`frappe/auth.py:649-651`, before the hooks at `frappe/auth.py:653`, and throws
an HTML page there for a `Basic` or `token` scheme. So
`sketch.mcp.http.before_request` refuses a non-Bearer scheme first.

`raise Unauthorized(response=...)` avoids that page. `frappe/app.py:121` does
`e.get_response(request.environ)` for an `HTTPException`, and werkzeug returns
the response the constructor was given, unchanged
(`werkzeug/exceptions.py:162-163`). So the exact JSON bytes reach the client,
`handle_exception` never runs, and no traceback leaks at any `developer_mode`.
"""

import frappe
from frappe.utils import now_datetime, time_diff_in_seconds
from werkzeug.exceptions import Unauthorized

# The one path a Sketch Token opens. Do not add a second entry here.
MCP_PATH = "/mcp"

BEARER_PREFIX = "bearer "

#: Stamp `last_used` only when the stored value is older than this. The hook
#: runs on every agent request, and a row write per request is not worth a line
#: of relative time in Settings.
LAST_USED_INTERVAL_SECONDS = 60


def validate_sketch_token() -> None:
	"""Set the session user from `Authorization: Bearer sk_...`, on `/mcp` only."""
	if not _is_mcp_path():
		# Trap 8. Every other path, Desk and API included, is out of reach.
		return

	if frappe.session.user not in ("", "Guest"):
		# A session cookie already logged this request in. Leave it alone.
		return

	header = (frappe.get_request_header("Authorization") or "").strip()
	if not header:
		# No credentials at all. The renderer answers `no_credentials`, because
		# a client with no header may be reading the endpoint, not failing at
		# it, and core needs no help to leave the session as Guest.
		return

	if not header.lower().startswith(BEARER_PREFIX):
		# Over HTTP `sketch.mcp.http.before_request` answers this first, because
		# core tries its own API keys before the app hooks
		# (`frappe/auth.py:649-653`) and throws its own HTML page for `Basic`
		# and `token`. The check stays here so the hook holds the whole
		# contract for a caller that runs it directly.
		_refuse("wrong_auth_scheme")

	from sketch.sketch.doctype.sketch_token.sketch_token import resolve

	user = resolve(header[len(BEARER_PREFIX) :].strip())
	if not user:
		_refuse("invalid_token")

	frappe.set_user(user)
	_stamp_last_used(user)


def _refuse(error: str):
	"""Stop the request with the `/mcp` error contract body."""
	from sketch.mcp.http import error_response

	raise Unauthorized(response=error_response(error))


def _is_mcp_path() -> bool:
	"""True only for the `/mcp` endpoint of this site, in any letter case."""
	request = getattr(frappe.local, "request", None)
	if request is None:
		return False

	return request.path.rstrip("/").lower() == MCP_PATH


def _stamp_last_used(user: str) -> None:
	"""Record that an agent used this token.

	Cheap on purpose: one direct row write, no doc load, and none at all when
	the stored stamp is younger than `LAST_USED_INTERVAL_SECONDS`.
	`update_modified=False` keeps the row's `modified` stamp still, so a read
	never looks like a token change.

	The commit is safe here: the hook runs before any Sketch work
	(`frappe/app.py:80`), so nothing else is open in the transaction. It also
	keeps the stamp when the request itself later fails and rolls back.

	A stamp is a nicety, so no failure of it reaches the agent.
	"""
	try:
		row = frappe.db.get_value("Sketch Token", {"user": user}, ["name", "last_used"], as_dict=True)
		if not row:
			return

		if row.last_used and time_diff_in_seconds(now_datetime(), row.last_used) < LAST_USED_INTERVAL_SECONDS:
			return

		frappe.db.set_value("Sketch Token", row.name, "last_used", now_datetime(), update_modified=False)
		frappe.db.commit()
	except Exception:
		frappe.logger("sketch.auth").warning("could not stamp last_used", exc_info=True)
