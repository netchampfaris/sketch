# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""JSON-RPC layer: parse one MCP message, dispatch, shape the reply.

Stateless by design: no handshake state, no session ids, no SSE. Every request
is served on its own, and every reply is one JSON document.

**Dual-era.** One endpoint serves the legacy revision `2025-06-18` and the
modern revision `2026-07-28`. `2025-11-25` is not served: its nine changes are
OAuth discovery, icons, elicitation, sampling and tasks, and none of them touch
Sketch's twelve tools.

The era switch is one test: the presence of
`params._meta["io.modelcontextprotocol/protocolVersion"]`. Sketch keeps no
session, so nothing else forks.

| | Legacy `2025-06-18` | Modern `2026-07-28` |
|---|---|---|
| Opens with | `initialize` | per-request `_meta` |
| `initialize`, `ping` | yes | no, both removed |
| `server/discover` | no | yes, and required |
| Required headers | none | `MCP-Protocol-Version`, `Mcp-Method`, `Mcp-Name` |
| `resultType` on results | no | yes, always |
| `ttlMs`, `cacheScope` | no | yes, on `tools/list` and `server/discover` |

An unknown protocol version is an error in both eras. Builder downgrades it in
silence; Sketch must not.
"""

import json

import frappe

import sketch
from sketch.mcp import tools as surface

MODERN_VERSION = "2026-07-28"
LEGACY_VERSION = "2025-06-18"
SUPPORTED_VERSIONS = (MODERN_VERSION, LEGACY_VERSION)

META_PROTOCOL_VERSION = "io.modelcontextprotocol/protocolVersion"
META_CLIENT_CAPABILITIES = "io.modelcontextprotocol/clientCapabilities"
META_SERVER_INFO = "io.modelcontextprotocol/serverInfo"

HEADER_PROTOCOL_VERSION = "MCP-Protocol-Version"
HEADER_METHOD = "Mcp-Method"
HEADER_NAME = "Mcp-Name"

# Modern error codes. Both answer HTTP 400.
HEADER_MISMATCH = -32020
UNSUPPORTED_PROTOCOL_VERSION = -32022

# The tool set is the same twelve for every account, so it caches publicly.
# One hour, the value in the revision's own example.
CACHE_TTL_MS = 3600000
CACHE_SCOPE = "public"

# Methods that take a name in `Mcp-Name`.
NAME_TAKING = ("tools/call",)

INSTRUCTIONS = """Sketch MCP server: write high-fidelity frappe-ui prototypes that render in the browser.

Workflow: call get_skill first. Then list_prototypes or create_prototype, write the files, call check with screenshot: true, and finish with commit. Do that once at the end of each user request, with `prompt` set to the user's message word for word. Every tool except list_prototypes and create_prototype takes a `prototype` argument: the slug returned by create_prototype.

A Prototype is an app-like source tree that lives on this server, not on your disk. Pages go in src/pages/, shared components in src/components/, with src/App.vue and src/router.ts at the top. Every path you pass is a full relative path such as src/pages/Home.vue. Use write_files for new or rewritten files and edit_file for small changes to an existing one.

There is no server and no backend. Data lives in plain refs inside the prototype files. Never import useList, useDoc, useCall, useDoctype, useNewDoc, createResource, createListResource, createDocumentResource, frappeRequest or call. They will throw.

TypeScript is stripped, not type-checked. Tailwind classes, frappe-ui components and frappe-ui tokens all work; get_skill documents them.

check returns compile errors, console errors, and one image per route when screenshot is true. Fix every error before you report done. delete_file and set_public are annotated destructive, so your client asks before running them."""


class RpcError(Exception):
	"""A JSON-RPC error, with the HTTP status it must be served under."""

	def __init__(self, code: int, message: str, data: dict | None = None, http_status: int = 200):
		self.code = code
		self.message = message
		self.data = data
		self.http_status = http_status


def handle(raw: bytes, headers=None) -> tuple[int, dict | None]:
	"""Serve one MCP message. Returns (http_status, json payload or None).

	`headers` is the request header mapping. The modern era compares three of
	them against the body, so the comparison lives here and not in the
	transport.

	Unlike Builder, this returns HTTP 400 for a protocol error the revision
	says must carry one.
	"""
	headers = headers if headers is not None else {}
	try:
		message = json.loads(raw or b"null")
	except Exception:
		# This branch never runs over HTTP. Core parses the body in
		# `make_form_dict` (`frappe/app.py:302-308`), called from `init_request`
		# at `frappe/app.py:178`, and throws `frappe.DataError` there. That is
		# before every app hook and every renderer, so a broken body never
		# reaches `handle`. The branch stays for the in-process callers, which
		# pass raw bytes straight in.
		return 200, error(None, -32700, "Parse error: body must be a JSON object")
	if isinstance(message, list):
		return 200, error(None, -32600, "Batching is not supported: send one message per request")
	if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
		return 200, error(None, -32600, "Invalid JSON-RPC message")
	if "id" not in message:
		# Notification (initialized, cancelled, ...) or a stray client response:
		# nothing is tracked between requests, accept and drop.
		return 202, None

	request_id = message["id"]
	method = message.get("method")
	params = message.get("params") or {}
	if not isinstance(params, dict):
		return 200, error(request_id, -32602, "params must be an object")

	try:
		modern = is_modern(params)
		if modern:
			validate_modern(method, params, headers)
		else:
			validate_legacy(headers)

		methods = MODERN_METHODS if modern else LEGACY_METHODS
		handler = methods.get(method)
		if handler is None:
			return 200, error(request_id, -32601, unknown_method_message(method, modern))

		return 200, result(request_id, handler(params, modern), modern)
	except RpcError as e:
		return e.http_status, error(request_id, e.code, e.message, e.data)
	except Exception:
		frappe.logger("sketch.mcp").error("mcp rpc crashed", exc_info=True)
		return 200, error(request_id, -32603, "Internal error")


def is_modern(params: dict) -> bool:
	"""The era switch. A modern client states its version on every request."""
	meta = params.get("_meta")
	return isinstance(meta, dict) and bool(meta.get(META_PROTOCOL_VERSION))


def validate_modern(method, params: dict, headers) -> None:
	"""Check the two required `_meta` keys and the three required headers."""
	meta = params.get("_meta") or {}
	requested = meta.get(META_PROTOCOL_VERSION)

	if requested != MODERN_VERSION:
		raise unsupported_version(requested)

	if META_CLIENT_CAPABILITIES not in meta:
		raise RpcError(
			-32602,
			f"Invalid params: _meta.{META_CLIENT_CAPABILITIES} is required on every request",
			http_status=400,
		)

	header_version = header(headers, HEADER_PROTOCOL_VERSION)
	if not header_version:
		raise header_mismatch(f"{HEADER_PROTOCOL_VERSION} header is required")
	if header_version != requested:
		raise header_mismatch(
			f"{HEADER_PROTOCOL_VERSION} is {header_version} but _meta says {requested}"
		)

	header_method = header(headers, HEADER_METHOD)
	if not header_method:
		raise header_mismatch(f"{HEADER_METHOD} header is required")
	if header_method != method:
		raise header_mismatch(f"{HEADER_METHOD} is {header_method} but the message calls {method}")

	if method in NAME_TAKING:
		# Sketch never Base64-encodes this header, because every value it can
		# carry is a tool name or a slug, and both are ASCII [a-z0-9_-]. A
		# non-ASCII name would need the sentinel decode the revision defines.
		header_name = header(headers, HEADER_NAME)
		if not header_name:
			raise header_mismatch(f"{HEADER_NAME} header is required for {method}")
		if header_name != params.get("name"):
			raise header_mismatch(
				f"{HEADER_NAME} is {header_name} but params.name is {params.get('name')}"
			)


def validate_legacy(headers) -> None:
	"""Reject a legacy request that names a version Sketch does not serve.

	`2025-06-18` lets the server assume `2025-03-26` when the header is absent,
	so a missing header is fine here. A header naming an unknown version is a
	400, which is the one MUST the legacy revision puts on the server.
	"""
	header_version = header(headers, HEADER_PROTOCOL_VERSION)
	if header_version and header_version not in SUPPORTED_VERSIONS:
		raise unsupported_version(header_version)


def header(headers, key: str) -> str | None:
	"""One request header, or None. Header lookup is case-insensitive."""
	try:
		value = headers.get(key)
	except AttributeError:
		return None

	return value.strip() if isinstance(value, str) and value.strip() else None


def header_mismatch(message: str) -> RpcError:
	return RpcError(HEADER_MISMATCH, f"HeaderMismatch: {message}", http_status=400)


def unsupported_version(requested) -> RpcError:
	return RpcError(
		UNSUPPORTED_PROTOCOL_VERSION,
		"Unsupported protocol version",
		data={"supported": list(SUPPORTED_VERSIONS), "requested": requested},
		http_status=400,
	)


def unknown_method_message(method, modern: bool) -> str:
	"""Say why, when the method exists in the other era."""
	if modern and method in LEGACY_METHODS:
		return f"Method not found: {method} was removed in {MODERN_VERSION}"
	if not modern and method in MODERN_METHODS:
		return f"Method not found: {method} needs the {MODERN_VERSION} per-request _meta"

	return f"Method not found: {method}"


def result(request_id, payload: dict, modern: bool = False) -> dict:
	"""Wrap one handler result. Modern results carry resultType and serverInfo."""
	if modern:
		meta = dict(payload.get("_meta") or {})
		meta[META_SERVER_INFO] = server_info()
		payload = {**payload, "resultType": "complete", "_meta": meta}

	return {"jsonrpc": "2.0", "id": request_id, "result": payload}


def error(request_id, code: int, message: str, data: dict | None = None) -> dict:
	body = {"code": code, "message": message}
	if data is not None:
		body["data"] = data

	return {"jsonrpc": "2.0", "id": request_id, "error": body}


def server_info() -> dict:
	return {"name": "sketch", "version": sketch.__version__}


def handle_initialize(params: dict, modern: bool) -> dict:
	"""Legacy only. Echo the requested version, or refuse it."""
	requested = params.get("protocolVersion")
	if requested and requested not in SUPPORTED_VERSIONS:
		raise unsupported_version(requested)

	return {
		"protocolVersion": requested or LEGACY_VERSION,
		"capabilities": {"tools": {}},
		"serverInfo": server_info(),
		"instructions": INSTRUCTIONS,
	}


def handle_discover(params: dict, modern: bool) -> dict:
	"""Modern only, and required there. A full DiscoverResult.

	`resultType` and `_meta.serverInfo` are added by `result()`.
	"""
	return {
		"supportedVersions": list(SUPPORTED_VERSIONS),
		"capabilities": {"tools": {}},
		"instructions": INSTRUCTIONS,
		"ttlMs": CACHE_TTL_MS,
		"cacheScope": CACHE_SCOPE,
	}


def handle_tools_list(params: dict, modern: bool) -> dict:
	payload = {
		"tools": [
			{
				"name": tool.name,
				"description": tool.description,
				"inputSchema": tool.parameters,
				"annotations": surface.annotations(tool.name),
				**({"outputSchema": tool.output_schema} if tool.output_schema else {}),
			}
			for tool in surface.TOOLS.values()
		]
	}
	if modern:
		payload["ttlMs"] = CACHE_TTL_MS
		payload["cacheScope"] = CACHE_SCOPE

	return payload


def handle_tools_call(params: dict, modern: bool) -> dict:
	name = params.get("name")
	if name not in surface.TOOLS:
		raise RpcError(-32602, f"Unknown tool: {name}")
	arguments = params.get("arguments") or {}
	if not isinstance(arguments, dict):
		raise RpcError(-32602, "arguments must be an object")

	return surface.call_tool(name, arguments)


LEGACY_METHODS = {
	"initialize": handle_initialize,
	"ping": lambda params, modern: {},
	"tools/list": handle_tools_list,
	"tools/call": handle_tools_call,
}

MODERN_METHODS = {
	"server/discover": handle_discover,
	"tools/list": handle_tools_list,
	"tools/call": handle_tools_call,
}
