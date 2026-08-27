# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""HTTP endpoint: POST /mcp, a stateless MCP server served by the site.

A page renderer, not a whitelisted method and not a route rule. It gives full
control over the raw response (JSON-RPC bodies, a 401 with no login redirect)
and a clean URL. POST reaches website renderers on both Frappe lines.

Authentication happens upstream in `frappe.validate_auth`, which calls
`sketch.auth.validate_sketch_token`. An unauthenticated request gets a plain
401 that carries the `WWW-Authenticate` header core attaches, which starts an
MCP client's OAuth discovery.

This module is imported for every website request, so `rpc` loads lazily
inside `render()`.
"""

import json

import frappe
from werkzeug.wrappers import Response

MCP_PATH = "/mcp"


class McpPageRenderer:
	def __init__(self, path: str, http_status_code: int | None = None):
		self.path = path

	def can_render(self) -> bool:
		return bool(frappe.request) and frappe.request.path.rstrip("/") == MCP_PATH

	def render(self) -> Response:
		from sketch.mcp import rpc

		if frappe.request.method != "POST":
			# -32600, not Builder's -32000: the -32000..-32019 sub-range is
			# legacy in 2026-07-28 and new servers must stay out of it.
			payload = rpc.error(None, -32600, "Method Not Allowed: POST a single JSON-RPC message")
			return json_response(405, payload, headers={"Allow": "POST"})
		if frappe.session.user == "Guest":
			return json_response(401, {"error": "authentication required"})
		if not frappe.has_permission("Sketch Prototype", "read"):
			return json_response(403, {"error": "this account has no access to Sketch Prototypes"})

		status, payload = rpc.handle(frappe.request.get_data(), frappe.request.headers)
		return json_response(status, payload)


def json_response(status: int, payload: dict | None, headers: dict | None = None) -> Response:
	body = "" if payload is None else json.dumps(payload)
	return Response(body, status=status, mimetype="application/json", headers=headers)
