# What to reuse from Builder's /mcp implementation

Type: research
Status: resolved
Blocked by: 

## Question

Read /home/faris/benches/builder-bench/apps/builder/builder/ai/mcp (branch forge/mcp-server) and docs/mcp.md. Report: how the stateless /mcp endpoint is wired into Frappe (hooks, route, request parsing), how token auth and the OAuth 401 metadata work, the dispatch and tool-registry pattern, and which files can be copied into the sketch app with minimal change. Note anything tied to Builder Pages that must be removed.

## Answer

- Copy `http.py` and `rpc.py` from `builder/ai/mcp/`. They hold the transport, the Guest 401, the JSON-RPC parser, and the error shapes. Swap the `Builder Page` permission check, the `INSTRUCTIONS` text, and the server name.
- Wire `/mcp` with one `page_renderer` hook entry (`builder/hooks.py:205-208`). Not a whitelisted method, not a route rule. POST reaches website renderers on both Frappe lines.
- Auth is Frappe core. `validate_auth` runs before dispatch and handles `token key:secret` and `Bearer`. Core stamps `WWW-Authenticate: Bearer resource_metadata=".../.well-known/oauth-protected-resource"` on every 401/403 while `OAuth Settings` metadata is on (default on).
- Keep the pattern from `tools.py` and `dispatch.py`: module-level `TOOLS` dict, `READ_ONLY` / `DESTRUCTIVE` sets, `annotations()`, `isError` when text starts with `FAILED`, savepoint + rollback around each handler. Rewrite the bodies. Drop `ctx.py` and `pages.py`.
- Remove: the page lock (`builder.ai.locks`), `McpCtx` snapshots and realtime mirror, agent-registry reuse, `CLIENT_OPS` / `SCRIPT_TWINS` / `CONFIRM_KINDS`, all `Builder Page` tools.
- Works on Frappe version-16 and develop. All APIs used are present in both. Verified by live curl on both benches.

Findings: /home/faris/benches/.scratch/sketch-mvp/research/09-builder-mcp-reuse.md

### 2026-08-26 — amendment: auth is Sketch's, not core's

From ticket 12. This ticket recorded "auth is Frappe core". It is not.

`/mcp` authenticates a `Sketch Token` sent as `Authorization: Bearer sk_...`,
resolved by one function registered in `auth_hooks` (`auth.py:772-774`).
The function refuses any path except `/mcp`.

Frappe's `api_key`/`api_secret` was rejected because it authenticates every
Frappe endpoint, so a leaked Sketch token would be a site-wide REST API
credential, and signup is open to anyone. Core also cannot take a Bearer
API key: `validate_auth` routes `Bearer` to the OAuth path and accepts API
keys only as `token <key>:<secret>` or `Basic` (`auth.py:640-741`).

OAuth stays deferred, unchanged. The 401 with the `WWW-Authenticate` header
copied from Builder's `http.py` is still correct and still wanted.
