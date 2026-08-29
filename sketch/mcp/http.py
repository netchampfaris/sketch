# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""HTTP endpoint: POST /mcp, a stateless MCP server served by the site.

A page renderer, not a whitelisted method and not a route rule. It gives full
control over the raw response (JSON-RPC bodies, a 401 with no login redirect)
and a clean URL. POST reaches website renderers on both Frappe lines.

Authentication happens upstream in `frappe.validate_auth`, which calls
`sketch.auth.validate_sketch_token` (`frappe/app.py:80`). A wrong token never
reaches this module: `sketch.auth` raises there, before `get_response()` at
`frappe/app.py:115`. A request that arrives here as Guest carried no
`Authorization` header at all.

This module owns the `/mcp` error contract, `ERRORS` below, because three places
serve it: the renderer answers `no_credentials` and `no_access`, `before_request`
refuses a non-Bearer scheme, and `sketch.auth` raises on a token that resolves
to no user.

This module is imported for every website request, so `rpc` and `sketch.api`
load lazily inside the functions that need them.
"""

import json

import frappe
from werkzeug.exceptions import HTTPException
from werkzeug.wrappers import Response

from sketch.auth import BEARER_PREFIX

#: The one path this app serves. Every comparison lower-cases the request path,
#: so `/MCP` reaches the endpoint instead of the website 404 (trap E8).
MCP_PATH = "/mcp"

#: Where every error body sends the user. The public base is read at request
#: time, so the beta site and the test site each name themselves.
SETTINGS_PATH = "/settings"

#: The `/mcp` error contract: (status, message, `WWW-Authenticate` value).
#: An agent reads JSON, so every failure names the mistake and the fix in the
#: body. This module answers `no_credentials` and `no_access`; `sketch.auth`
#: raises `wrong_auth_scheme` and `invalid_token` before any renderer runs.
#:
#: No challenge carries a `resource_metadata` parameter. Core's own 401 header
#: advertises the site as an OAuth authorization server
#: (`frappe/app.py:295-299`), and an MCP client that reads it starts an OAuth
#: flow `/mcp` does not serve. Sketch takes a pasted token only.
ERRORS = {
	"no_credentials": (
		401,
		"Sketch needs a token. Send the header Authorization: Bearer sk_... on every request to"
		" /mcp. Copy your token from Settings.",
		'Bearer realm="sketch"',
	),
	"wrong_auth_scheme": (
		401,
		"Sketch reads the Authorization header with the Bearer scheme only. Send Authorization:"
		" Bearer sk_... Do not use a custom header name, and do not send the token on its own.",
		'Bearer realm="sketch", error="invalid_request"',
	),
	"invalid_token": (
		401,
		"This Sketch token is not valid. It was regenerated, mistyped, or it belongs to another"
		" account. Copy the current token from Settings and paste it into your MCP client again.",
		'Bearer realm="sketch", error="invalid_token"',
	),
	"no_access": (
		403,
		"Add the Sketch User role to this account, then copy its token again from Settings.",
		# A 403 needs its own challenge for the same reason a 401 does: core
		# rewrites the header on both (`frappe/app.py:243`), and its value
		# points an MCP client at an OAuth flow /mcp does not serve.
		# `insufficient_scope` is the RFC 6750 code for a good token with too
		# few rights.
		'Bearer realm="sketch", error="insufficient_scope"',
	),
}

#: The one body a wrong method gets. -32600, not Builder's -32000: the
#: -32000..-32019 sub-range is legacy in 2026-07-28 and new servers stay out.
METHOD_NOT_ALLOWED = "Method Not Allowed: POST a single JSON-RPC message"


def is_mcp_path(path: str | None) -> bool:
	"""True for `/mcp`, `/mcp/`, and any letter case of either."""
	return bool(path) and path.rstrip("/").lower() == MCP_PATH


class McpPageRenderer:
	def __init__(self, path: str, http_status_code: int | None = None):
		self.path = path

	def can_render(self) -> bool:
		return bool(frappe.request) and is_mcp_path(frappe.request.path)

	def render(self) -> Response:
		from sketch.mcp import rpc

		if frappe.request.method != "POST":
			return json_response(
				405, rpc.error(None, -32600, METHOD_NOT_ALLOWED), headers={"Allow": "POST"}
			)
		if frappe.session.user == "Guest":
			# No Authorization header. A wrong one never gets this far.
			return error_response("no_credentials")
		if not frappe.has_permission("Sketch Prototype", "read"):
			return error_response("no_access")

		status, payload = rpc.handle(frappe.request.get_data(), frappe.request.headers)
		return json_response(status, payload)


def before_request() -> None:
	"""Answer the `/mcp` cases that are decided before any renderer or hook.

	Three of them, and each needs this early a seat:

	- DELETE. Core raises `NotFound` (`frappe/app.py:117-118`).
	- OPTIONS. Core returns a bare 200 with no `Allow` header
	  (`frappe/app.py:82-83`). Both decisions come before `get_response()`
	  (`frappe/app.py:115`), so a `page_renderer` never runs for either.
	- An `Authorization` scheme that is not Bearer. `validate_auth` tries its
	  own API keys first (`frappe/auth.py:649-651`) and only then the app hooks
	  (`frappe/auth.py:653`). `Basic <not base64>` throws
	  `InvalidAuthorizationToken` at `frappe/auth.py:734-738` and `token a:b`
	  throws `AuthenticationError`, both as an HTML page, before
	  `sketch.auth.validate_sketch_token` is ever called.

	This hook runs inside `init_request` (`frappe/app.py:183-184`), which is
	ahead of `validate_auth()` at `frappe/app.py:80`, so it beats all three.

	The hook is registered site-wide and runs on every request, so every other
	path leaves on the first test.
	"""
	request = getattr(frappe.local, "request", None)
	if request is None or not is_mcp_path(request.path):
		return

	if request.method == "DELETE":
		from sketch.mcp import rpc

		stop(json_response(405, rpc.error(None, -32600, METHOD_NOT_ALLOWED), headers={"Allow": "POST"}))

	if request.method == "OPTIONS":
		# 204: an answer about methods carries no body.
		stop(Response(status=204, headers={"Allow": "POST, OPTIONS"}))

	if frappe.session.user not in ("", "Guest"):
		# A session cookie already logged this request in. Leave it alone.
		# `HTTPRequest()` resolved it one line earlier (`frappe/app.py:180-181`).
		return

	header = (frappe.get_request_header("Authorization") or "").strip()
	if header and not header.lower().startswith(BEARER_PREFIX):
		stop(error_response("wrong_auth_scheme"))


def stop(response: Response) -> None:
	"""End the request with these exact bytes.

	`before_request` has no return contract, so raising is the only stop.
	`frappe/app.py:121` returns `e.get_response(request.environ)` for an
	`HTTPException`, and werkzeug returns the response the constructor was
	given, unchanged (`werkzeug/exceptions.py:162-163`). So core's
	`handle_exception` never runs and no traceback leaks.
	"""
	raise HTTPException(response=response)


def error_response(error: str) -> Response:
	"""The contract body for one `ERRORS` key."""
	from sketch import api

	status, message, challenge = ERRORS[error]
	payload = {
		"error": error,
		"message": message,
		# The same origin a shared link carries, so one host names the site.
		"settings_url": api._public_base() + SETTINGS_PATH,
	}
	headers = {}
	if challenge:
		headers["WWW-Authenticate"] = challenge
		pin_header("WWW-Authenticate", challenge)

	return json_response(status, payload, headers=headers)


def pin_header(name: str, value: str) -> None:
	"""Set a header core cannot overwrite later in the same request.

	Core replaces `WWW-Authenticate` on every 401 and 403 while OAuth Settings
	`show_protected_resource_metadata` is on (`frappe/app.py:243-244`), on the
	renderer path and on the raise path alike. `frappe.local.response_headers`
	is applied after that (`frappe/app.py:247`), so a value pinned here wins.
	Only `/mcp` calls this, so no other endpoint changes.
	"""
	headers = getattr(frappe.local, "response_headers", None)
	if headers is not None:
		headers[name] = value


def json_response(status: int, payload: dict | None, headers: dict | None = None) -> Response:
	body = "" if payload is None else json.dumps(payload)
	return Response(body, status=status, mimetype="application/json", headers=headers)
