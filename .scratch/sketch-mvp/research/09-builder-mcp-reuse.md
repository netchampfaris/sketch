# What to reuse from Builder's /mcp implementation

Ticket: `/home/faris/benches/.scratch/sketch-mvp/issues/09-builder-mcp-reuse.md`
Source: `/home/faris/benches/builder-bench/apps/builder`, branch `forge/mcp-server`,
commit `98e8c6a` ("feat(ai): serve a stateless MCP server at /mcp").
Frappe A: `/home/faris/benches/builder-bench/apps/frappe` (`version-16`, v16.30.0).
Frappe B: `/home/faris/benches/frappe-bench/apps/frappe` (`develop`, HEAD `6f6fd317d5`).

## Gist

- Copy `http.py` and `rpc.py`. They carry the transport, auth gate, JSON-RPC, and error shape.
  Swap the `Builder Page` permission check and the `INSTRUCTIONS` text.
- Register the renderer class in `hooks.py` `page_renderer`. One line.
- Write a new `tools.py` and `dispatch.py`. Builder's versions are wrappers over its AI agent
  registry, page lock, snapshots, and realtime mirror. None of that applies to Sketch.
- Drop `ctx.py` and `pages.py`. They are all Builder Page logic.
- Auth is free. Frappe core handles `Authorization: token key:secret` and `Bearer <oauth>`,
  and stamps `WWW-Authenticate` on every 401. This is identical on v16 and develop.
- Every Frappe API Builder uses exists on both v16 and develop. Verified by agents and by
  live curl on both benches (see "Verification").

## 1. How /mcp reaches Python

The route is a `page_renderer` hook, not a whitelisted method and not a `website_route_rules` entry.

- `builder/hooks.py:205-208`:
  ```python
  page_renderer = [
      "builder.ai.mcp.http.McpPageRenderer",
      "builder.builder.doctype.builder_page.builder_page.BuilderPageRenderer",
  ]
  ```
- `builder/ai/mcp/http.py:22-31`: `McpPageRenderer.__init__(self, path, http_status_code=None)`.
  `can_render()` returns true when `frappe.request.path.rstrip("/") == "/mcp"`.
- Frappe resolves custom renderers first, before `StaticPage`, `DocumentPage`, etc.
  (`frappe/website/path_resolver.py:56-70`, same lines in A and B). Constructor is called
  positionally as `renderer(endpoint, self.http_status_code)` at line 68.
- `render()` returns a werkzeug `Response`. Frappe passes it through unchanged
  (`frappe/website/serve.py:18-20`, identical in A and B). No HTML wrapping.
- POST reaches the website path: `frappe/app.py` dispatches `GET`, `HEAD`, `POST` to
  `get_response()` (A `app.py:138-139`, B `app.py:143-144`). `PUT`/`DELETE` raise `NotFound`
  before the renderer. So Builder's 405 branch (`http.py:36-38`) only fires for GET/HEAD.
- Reason given in the module docstring (`http.py:1-12`): a page renderer gives full control
  over the raw response, a clean URL, and a plain 401 with no login redirect.

Gotchas from Frappe core (both versions):

- `frappe.cache.hget("website_404", request.url)` short-circuits to a 404 page before custom
  renderers run (`path_resolver.py:38`). Only active when `can_cache()` is true, so not in
  `developer_mode`. A production site that got a `/mcp` request before the hook existed
  needs the cache cleared.
- CSRF: a POST from a browser session with a `sid` cookie and no `X-Frappe-CSRF-Token`
  gets a 400 (`frappe/auth.py:83-98`). Header-token requests have no session csrf token, so
  they pass.

## 2. Request parsing and stateless JSON-RPC

`builder/ai/mcp/rpc.py` is the whole transport layer. It is 128 lines and has no Builder
dependency except the `INSTRUCTIONS` string, `builder.__version__`, and the two imports
of `dispatch` and `tools`.

- `handle(raw: bytes) -> (http_status, payload | None)` at `rpc.py:44-67`:
  - `json.loads(raw or b"null")`; parse failure -> 200 with error `-32700`.
  - A JSON list -> 200 with `-32600` "Batching is not supported".
  - Not a dict, or `jsonrpc != "2.0"` -> 200 with `-32600`.
  - No `id` key -> `202` with empty body. This absorbs `notifications/initialized`,
    `notifications/cancelled`, and stray client responses.
  - Unknown method -> 200 with `-32601`.
  - Handler success -> 200 with `{"jsonrpc":"2.0","id":..,"result":..}`.
  - `RpcError` -> 200 with its code and message. Any other exception -> logged, 200 with
    `-32603` "Internal error".
- `METHODS` table at `rpc.py:122-128`: `initialize`, `server/discover`, `ping`,
  `tools/list`, `tools/call`.
- `handle_initialize` (`rpc.py:82-89`) echoes the requested `protocolVersion` if it is in
  `PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26")` (`rpc.py:17`), else the newest. It
  returns `capabilities: {"tools": {}}`, `serverInfo`, and `instructions`. No session id
  header is ever set. `server/discover` (`rpc.py:92-98`) is the SEP-2575 stateless
  discovery method and returns `supportedVersions`.
- The body is read with `frappe.request.get_data()` (`http.py:41`). Werkzeug caches the
  body, so this is safe after Frappe's own `make_form_dict` call.
- Response builder `json_response(status, payload, headers)` at `http.py:45-47`:
  `Response(json.dumps(payload), status=..., mimetype="application/json")`.
- No SSE. Every reply is one JSON document. Clients that expect `text/event-stream` still
  work because the streamable-HTTP spec allows a plain JSON response
  (`rpc.py:3-7` docstring, `docs/mcp.md:44`).

## 3. Token auth and the OAuth 401

Builder does no auth itself. It only checks the outcome.

- `http.py:37-40`:
  ```python
  if frappe.session.user == "Guest":
      return json_response(401, {"error": "authentication required"})
  if not frappe.has_permission("Builder Page", "read"):
      return json_response(403, {"error": "this account has no access to Builder Pages"})
  ```
- Frappe core runs `validate_auth()` before route dispatch for every request, website paths
  included (A `frappe/app.py:104`, B `app.py:109`). Body is identical in A and B
  (A `frappe/auth.py:629-644`, B `auth.py:641-656`):
  - `Authorization: token <key>:<secret>` -> `validate_auth_via_api_keys` ->
    `validate_api_key_secret`. Bad key or secret raises `frappe.AuthenticationError` (401).
    `Basic base64(key:secret)` is also accepted.
  - `Authorization: Bearer <token>` -> `validate_oauth`. An unknown token does not raise
    there. The final check `len(header) == 2 and user in ("", "Guest")` raises
    `AuthenticationError` -> 401. This is the path that starts the MCP client's OAuth flow.
  - No `Authorization` header -> user stays `Guest`, nothing raises. The renderer must 401
    itself, which is what `http.py:37` does.
- `WWW-Authenticate` is stamped by core in `process_response`, on any response with status
  401 or 403, when `OAuth Settings.show_protected_resource_metadata` is on
  (A `frappe/app.py:266-267, 319-323`; B `app.py:271-272, 324-328`):
  ```python
  "WWW-Authenticate": f'Bearer resource_metadata="{get_resource_url()}/.well-known/oauth-protected-resource"'
  ```
  It is not path-scoped and not `/api`-scoped, so it lands on the hand-built 401 from the
  page renderer.
- `/.well-known/oauth-protected-resource` and `/.well-known/oauth-authorization-server`
  are hard-coded in `frappe/app.py` (A `:129-136`, B `:134-141`) and served by
  `frappe.integrations.oauth2.handle_wellknown` (A `oauth2.py:283-298`, B `:285-300`).
  RFC 9728 body: `_get_protected_resource_metadata` (A `:440-482`, B `:443-485`).
- Dynamic client registration: `POST /api/method/frappe.integrations.oauth2.register_client`
  (A `oauth2.py:349-350`, B `:351-353`). Develop adds `@rate_limit(limit=5, seconds=600)`.
- `OAuth Settings` defaults: `show_auth_server_metadata=1`,
  `show_protected_resource_metadata=1`, `enable_dynamic_client_registration=1`
  (`frappe/integrations/doctype/oauth_settings/oauth_settings.json`, identical A and B).
  So the flow is live out of the box.
- Develop differences that do not change behaviour for a client: develop hashes bearer
  tokens before lookup (B `auth.py:686-693`) and rejects disabled users (B `auth.py:700-701`).
- `docs/mcp.md:9-26` documents both connection modes:
  `claude mcp add --transport http builder https://site/mcp --header "Authorization: token k:s"`,
  or no header to trigger OAuth discovery. Note in `docs/mcp.md:24`: dynamic registration
  rejects `http://localhost` redirect URIs unless `developer_mode` is on.

## 4. Tool registry and dispatch

Registry (`builder/ai/mcp/tools.py`):

- Reuses the `Tool` dataclass from `builder/ai/agent/registry.py:32-46`:
  `name, side, description, parameters (JSON schema dict), handler(ctx, args) -> str | None`,
  plus `artifact` and `generator` fields Builder's in-app agent uses.
- `TOOLS = build_tools()` at `tools.py:141`, a module-level `dict[str, Tool]`. Built from
  Builder's in-app agent registry (`build_default_registry()`, `tools.py:122`) plus the
  MCP-native page tools in `pages.py`. Agent schemas are deep-copied and a required `page`
  param is injected (`with_page_param`, `tools.py:112-118`).
- Category sets drive behaviour by name (`tools.py:17-109`): `CLIENT_OPS`, `SCRIPT_TWINS`,
  `CONFIRM_KINDS`, `PAGE_SCOPED`, `PAGE_TAKING`, `READ_ONLY`, `DESTRUCTIVE`.
- Annotations (`tools.py:137-138`):
  ```python
  def annotations(name: str) -> dict:
      return {"readOnlyHint": name in READ_ONLY, "destructiveHint": name in DESTRUCTIVE}
  ```
  `tools/list` (`rpc.py:101-112`) emits `name`, `description`, `inputSchema`, `annotations`
  per tool. `docs/mcp.md:40` says clients prompt before destructive tools because of this.

Dispatch:

- `rpc.handle_tools_call` (`rpc.py:115-122`): unknown name or non-dict `arguments` raise
  `RpcError(-32602)`. Otherwise `dispatch.call_tool(name, arguments)` and the reply is
  `{"content": [...], "isError": bool}`.
- `dispatch.call_tool` (`dispatch.py:15-19`) runs `execute`, converts the string or list to
  MCP content blocks (`to_content`, `dispatch.py:76-79`), and sets `isError` when the first
  text block starts with `FAILED`.
- `dispatch.execute` (`dispatch.py:22-45`): write-permission gate for non-read-only tools,
  page resolution (pops `page` from args, checks `frappe.db.exists`), builds `McpCtx`, takes
  the per-page Redis lock for mutations, arms a revert snapshot, then `route`.
- `dispatch.route` (`dispatch.py:48-65`): `frappe.db.savepoint("mcp_tool")` before the
  handler; on exception `frappe.db.rollback(save_point="mcp_tool")` and return a `FAILED:`
  string. The savepoint pattern is the reusable part. Everything else in `route` is
  Builder-specific (client ops, script twins, queued realtime ops).
- Confirm-gated tools (`dispatch.py:68-73`) run the handler against a `CaptureCtx` to
  validate, then apply through `apply_pending_action`. Rationale in `tools.py:24-26`: the MCP
  client's own permission prompt is the confirmation step.

## 5. Error shapes

Three layers, all with HTTP 200 except transport-level cases:

| Case | HTTP | Body |
|---|---|---|
| Not POST | 405 + `Allow: POST` | JSON-RPC error `-32000` (`http.py:36-38`) |
| Guest | 401 | `{"error": "authentication required"}` plus core `WWW-Authenticate` (`http.py:37-38`) |
| No doctype read permission | 403 | `{"error": ...}` (`http.py:39-40`) |
| Notification (no `id`) | 202 | empty (`rpc.py:53-56`) |
| Parse error / invalid message / batch | 200 | JSON-RPC error `-32700` / `-32600` (`rpc.py:46-52`) |
| Unknown method | 200 | `-32601` (`rpc.py:57-59`) |
| Bad tool name or args | 200 | `-32602` via `RpcError` (`rpc.py:117-120`) |
| Handler crash | 200 | `-32603` "Internal error", logged to `frappe.logger("builder.ai.mcp")` (`rpc.py:64-66`) |
| Tool-level failure | 200 | `result.content[0].text` starts with `FAILED: ...`, `isError: true` (`dispatch.py:18`) |

Tool failures are data, not protocol errors. This matches the MCP spec: `isError` for tool
execution problems, JSON-RPC `error` for protocol problems.

## 6. Files to copy with minimal change

| File | Verdict | Changes |
|---|---|---|
| `builder/ai/mcp/__init__.py` | copy | empty |
| `builder/ai/mcp/http.py` | copy | rename import path (`http.py:34`); replace `"Builder Page", "read"` at `http.py:39` with Sketch's doctype; edit 403 message |
| `builder/ai/mcp/rpc.py` | copy | replace `INSTRUCTIONS` (`rpc.py:19-35`); `server_info()` name and `builder.__version__` (`rpc.py:78-79`); import paths (`rpc.py:13-15`); logger name (`rpc.py:65`) |
| `builder/hooks.py:205-208` | copy one line | `page_renderer = ["sketch.mcp.http.McpPageRenderer"]` |
| `builder/ai/mcp/tools.py` | rewrite | keep the shape: module-level `TOOLS` dict, `READ_ONLY` / `DESTRUCTIVE` sets, `annotations()` at `tools.py:137-138`. Drop everything from `builder.ai.agent` |
| `builder/ai/mcp/dispatch.py` | rewrite | keep `call_tool` / `to_content` / `isError` rule (`dispatch.py:15-19, 76-79`) and the savepoint + rollback guard (`dispatch.py:51-61`). Drop lock, ctx, confirm, script twins |
| `builder/ai/mcp/ctx.py` | do not copy | all Builder page state |
| `builder/ai/mcp/pages.py` | do not copy | all Builder Page tools. Only the `page_tool()` helper shape (`pages.py:180-193`) is worth imitating for a `Tool` factory |
| `docs/mcp.md` | copy as template | connection instructions (`docs/mcp.md:9-26`) apply unchanged apart from the URL and required role |

Sketch also needs its own `Tool` dataclass. Builder's lives in
`builder/ai/agent/registry.py:32-46`. Four fields are enough:
`name, description, parameters, handler`.

## 7. Builder-specific parts to remove

- `frappe.has_permission("Builder Page", ...)` gates: `http.py:39`, `dispatch.py:24`.
- `builder.ai.locks` page lock and TTL: `dispatch.py:7, 33-36, 41-44`, `tools.py:15`
  (`MCP_LOCK_TTL = 120`). The lock exists so MCP fails fast while the in-app AI assistant
  holds a page (`docs/mcp.md:42`). Sketch has no in-app agent, so drop it.
- `McpCtx` / `CaptureCtx` (`ctx.py`, whole file): `WorkingTree`, `page_writer`,
  revert snapshots (`capture_page_state`, `save_revert_snapshot`), realtime mirror
  `ai_chat_*` events, queued client ops.
- Agent registry reuse: `build_default_registry`, `REGISTRY_ORDER`, `PAGE_SCOPED`,
  `with_page_param` (`tools.py:9, 41-66, 74-86, 112-135`).
- `CLIENT_OPS`, `SCRIPT_TWINS`, `CONFIRM_KINDS` and their dispatch branches
  (`tools.py:17-31`, `dispatch.py:49-73`), including `apply_pending_action`.
- `pages.py` tools and `PAGE_PARAM`, `PAGE_TAKING`.
- `INSTRUCTIONS` text in `rpc.py:19-35` (block model, snapshots, preview advice).
- `docs/mcp.md` lines 28-42: tool list and the two Builder-only notes (page lock, reserved
  `mcp` route for Builder Pages).
- The second `page_renderer` entry (`BuilderPageRenderer`) and the ordering comment in
  `http.py:5-7`. Sketch has no competing renderer.

## Frappe version compatibility

Works on both `version-16` and `develop`. Agents compared the two checkouts:

- `page_renderer` hook, `PathResolver`, `serve.get_response`: identical.
- `validate_auth`, `validate_auth_via_api_keys`: identical. `validate_oauth` differs only in
  token hashing and a disabled-user check on develop.
- `WWW-Authenticate` stamping, `handle_wellknown`, RFC 9728 metadata, `OAuth Settings`
  doctype: identical. Develop adds a rate limit on `register_client`.
- `frappe.db.savepoint` (A `database.py:1219`, B `:1237`), `frappe.db.rollback(save_point=)`
  (A `:1196`, B `:1214`), `frappe.publish_realtime(after_commit=)` (A `frappe/realtime.py`,
  B `frappe/realtime/__init__.py`, same signature), `frappe.logger`, `frappe.has_permission`,
  `frappe.request.get_data()`: all present on both.
- `handle_exception` for a raised `AuthenticationError` on a non-`/api` path: identical.
  JSON when `Accept: application/json`, else an HTML 401 error page. Never a redirect.
- Builder's own `pyproject.toml:31` declares `frappe = ">=15.0.0,<18.0.0"`.

## Verification

Live probes run on this box on 2026-08-26:

- Builder bench (v16), `POST /mcp` with no auth:
  `HTTP/1.1 401`, body `{"error": "authentication required"}`, header
  `WWW-Authenticate: Bearer resource_metadata="http://builder.localhost/.well-known/oauth-protected-resource"`.
- Builder bench, `GET /mcp`: `405`.
- Gameplan bench (develop), `GET /.well-known/oauth-protected-resource`: `200` with
  `authorization_servers`, `bearer_methods_supported: ["header"]`, `resource`.
- Gameplan bench (develop), `Authorization: Bearer nope` to `/api/method/ping`: `401` with
  the same `WWW-Authenticate` header.

Not verified: a full OAuth round trip from an MCP client against develop, and the Sketch
port itself (no code written).
