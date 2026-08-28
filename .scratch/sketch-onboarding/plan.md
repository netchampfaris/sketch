# Sketch onboarding: the fix plan

Input `.scratch/sketch-onboarding/problems.md`. Words `CONTEXT.md`. Paths and owner letters
`.scratch/sketch-mvp/build/contracts.md`. Branch `forge/mvp` at `91c551c`. Components from the
`frappe-ui` skill.

## Wave 1: an agent connects, and a failure names the fix

Worth: the whole product. A wrong token returns an HTML "Session Expired" page (E1) and the connect config is never on screen (C1). These two are the most likely cause of the difficulty.

**1.1 Raise the auth failure in `sketch/auth.py`.** Closes E1, E2, E3, E5. `validate_sketch_token`
raises `werkzeug.exceptions.Unauthorized` with a prebuilt `Response`, on `/mcp` only. Order: refuse
non-`/mcp`; return when the session is already a user; return when there is no `Authorization`
header; raise `wrong_auth_scheme` when the scheme is not `Bearer`; set the user on a good token;
raise `invalid_token` otherwise.
`sketch/auth.py`. Owner B3. Effort M. Verify:
`bench --site sketch-test.localhost run-tests --module sketch.tests.test_mcp_errors`, then
`curl -si -X POST http://sketch-test.localhost:8017/mcp -H "Authorization: Bearer sk_wrong" -H "Content-Type: application/json" -d '{}'`.
Tests run on `sketch-test.localhost` only. `sketch.localhost` is the beta site
with real users; see CONTEXT.md.

**1.2 Rewrite the `/mcp` 401 and 403 bodies.** Closes E4. Every 401 carries `WWW-Authenticate`.
Delete the false comment at `http.py:11-16`. `sketch/mcp/http.py`. Owner B3. Effort S. Verify:
`test_mcp_errors.py`, and `curl -si -X POST .../mcp -d '{}'` with no header.

**1.3 The Agent connection screen.** Closes C1, C2, C3, C5, C6, C7, D1, D2, D3, and the B3
signpost. Show the header name, the scheme, the endpoint and one ready block per client. Use `Tabs`
(`v-model:tab`) for the client picker, `Alert` theme `orange` for the claude.ai note, `Button` for each
Copy, `dialog.confirm` for Regenerate, and a `<pre>` on `bg-surface-gray-1 rounded-4 p-3` for each
snippet. `Tabs` and `Alert` are not used in the SPA yet; both ship in `frappe-ui@1.0.0-beta.55`. Do not
use `Card`; compose the surface. Give `agentToken` `initialData: { token: '', endpoint: '' }` so the
card does not collapse (C7). Add a `Show`/`Hide` toggle on the token (C6). Open Settings on Agent
connection when `session.data.has_token` is false.
`frontend/src/pages/SettingsScreen.vue`, `frontend/src/store.ts`. Owner C2. Effort L. Verify:
`cd frontend && yarn build`, open `/settings?tab=agent`, run the printed `claude mcp add` line,
then `claude mcp list`.

**1.4 Empty state points at Settings.** Closes B1. Rewrite `PrototypesScreen.vue:52-67`. The
header keeps its one solid `New prototype` action (spec 11); in the empty state the solid action is
`Connect your agent`. `frontend/src/pages/PrototypesScreen.vue`. Owner C2. Effort S. Verify:
`yarn build`, sign in as a user with no Prototype.

**1.5 Sidebar status becomes a live link.** Closes B2. Wrap the status row in a `router-link` to
`/settings?tab=agent`. Reload `session` after the first `agentToken` load, not only after
`regenerate`. `frontend/src/components/AppSidebar.vue`,
`frontend/src/pages/SettingsScreen.vue`. Owner C2. Effort S. Verify: `yarn build`, open Settings on
a fresh account, watch the sidebar text change with no page reload.

**1.6 Tests.** New file `sketch/tests/test_mcp_errors.py`. Owner D2. Effort M. Cases: a wrong token
returns JSON, not HTML; no traceback in the body at `developer_mode = 1`; the guest 401 names the
header; the wrong-scheme 401 differs from the guest 401; all four 401s carry `WWW-Authenticate`;
`Content-Type` is `application/json` on all four. Extends `test_auth_scope.py` and
`test_mcp_era.py`; repeats nothing from them.

## Wave 2: open signup

Worth: a second user. Blocked on decisions 1 and 2.

**2.1 Password at signup.** Closes A2, A3, A4. Add a password field to the form and set it in the
override. Log the user in on success. No mail, no verification link, no SMTP. `sketch/signup.py`,
`sketch/templates/includes/signup_extra.html`. Owner B1. Effort M. Verify: `test_signup.py`, then a
real signup on `https://sketch.netchamp.dev/login#signup`.

**2.2 Live username check.** Closes A5, A6. Add a whitelisted
`sketch.api.check_username(username: str) -> dict` returning `{"available": bool, "reason": str}`,
open to Guest. Call it on a debounce from the template. Keep the permanence warning and the URL
preview both on screen. `sketch/api.py` (C2 writes it),
`sketch/templates/includes/signup_extra.html` (B1 writes it). Effort M. Verify: `test_signup.py`,
case `test_check_username_is_open_to_guest`.

**2.3 Flip the switch.** Closes A1. Depends on decision 1. Set Website Settings
`disable_signup = 0` in `setup_site_settings`; drop the "stays shut" comment. `sketch/install.py`.
Owner: orchestrator. The file is not in the contracts table; it is site setup, like `hooks.py`.
Effort S. Verify: `bench --site sketch.localhost execute sketch.install.setup_site_settings`, then
`curl -s https://sketch.netchamp.dev/login | grep -c "Sign up"`.

**2.4 JSON throttle reply.** Closes A9. Replace `respond_as_web_page` with `frappe.throw`, so
the Sketch message reaches the login page. `sketch/signup.py`. Owner B1. Effort S.

**2.5 Tests.** New file `sketch/tests/test_signup.py`. Owner D2. Effort M. Cases: a signup with a
password logs in; the username stores as typed and is frozen after; `check_username` refuses a taken
name and answers Guest; the new user gets `Sketch User` and `user_type = "Website User"`; the
throttle returns JSON.

## Wave 3: branding, trust, endpoint edges

**3.1 Sketch branding before the SPA.** Closes A7. Set Website Settings `app_name`, the logo and
the login title in `setup_site_settings`. Add a welcome-mail template that says Sketch.
`sketch/install.py`, `sketch/templates/emails/sketch_welcome.html`. Owner: orchestrator. Hook needed:
`welcome_email = "sketch/templates/emails/sketch_welcome.html"`. Effort M. Verify:
`curl -s https://sketch.netchamp.dev/login | grep -i "<title>"`.

**3.2 One username rule text.** Closes A8. Copy the Settings wording into `signup_extra.html:67`
word for word: `3–30 characters. Use lowercase letters, numbers, and hyphens. Start with a letter.`
`sketch/templates/includes/signup_extra.html`. Owner B1. Effort S.

**3.3 Guest never loads the SPA.** Closes B4. Add a login guard to `get_context`.
`sketch/www/sketch.py`. Owner C2. Effort S. Verify: `curl -si https://sketch.netchamp.dev/ | head -1`
with no cookie.

**3.4 `last_used` on `Sketch Token`.** Closes C4. Add a `last_used` Datetime, stamped by
`sketch.auth` on a good token. Show it as `Last agent request: <relative time>` or `No agent has
connected yet.` `sketch/sketch/doctype/sketch_token/` (A1 leads), `sketch/auth.py` (B3),
`sketch/api.py` and `frontend/src/pages/SettingsScreen.vue` (C2). Effort M. Verify:
`test_mcp_errors.py`, case `test_last_used_moves`.

**3.5 Endpoint edges.** Closes E7, E8, E9. Match the `/mcp` path case-insensitively in
`auth.py` and `http.py` (E8). Add a `before_request` hook that answers `DELETE /mcp` with 405 and
`Allow: POST`, and `OPTIONS /mcp` with 204 and `Allow: POST, OPTIONS`. Core raises `NotFound` for
DELETE and returns a bare 200 for OPTIONS before any renderer runs (`frappe/app.py:104-118`), so a
renderer cannot fix either. `sketch/mcp/http.py`, `sketch/auth.py`. Owner B3. Effort M. Hook needed:
`before_request = ["sketch.mcp.http.before_request"]`. Verify: `curl -si -X DELETE .../mcp`,
`-X OPTIONS .../mcp`, `-X POST .../MCP`.

**3.6 Delete the dead parse branch.** Closes E6 as far as it can close. Frappe throws `DataError`
inside `make_form_dict`, which runs before every app hook (`frappe/app.py:302,333`), so
`rpc.py:106`'s `-32700` branch is unreachable over HTTP. Keep it for the in-process tests, comment
the reason, stop claiming it serves HTTP. `sketch/mcp/rpc.py`. Owner B3. Effort S.

## The copy

### Settings → Agent connection

Heading `Agent connection`. Lead: `Your agent talks to Sketch over MCP. Copy the token, then
paste one block below into your client.`

Token block: label `Token`; description `One user, one token. Anyone who holds it can write
your prototypes.`; actions `Copy token`, `Show` / `Hide`, `Regenerate`; under the field
`Last agent request: 2 minutes ago` or `No agent has connected yet.` Regenerate confirm,
title `Regenerate token?`, body `Every agent that holds the old token stops working at once.
You must paste the new token into each client again.`, confirm `Regenerate`, theme `red`.

Endpoint block: label `Endpoint`, value `https://sketch.netchamp.dev/mcp`, action
`Copy endpoint`, three help lines: `Transport: streamable HTTP. POST only.` /
`Header name: Authorization` / `Header value: Bearer <token>`.

`Set up your client`, a `Tabs` with five tabs. Each snippet gets a `Copy` button; the toast reads `Copied`.

**Claude Code**
`Run this once. It adds Sketch to every project on this machine.`
`claude mcp add --transport http --scope user sketch https://sketch.netchamp.dev/mcp --header "Authorization: Bearer <token>"`
`--scope user is not optional. Without it Claude Code binds Sketch to one directory.`
`Check it:` then `claude mcp list`
`You want this line: sketch: https://sketch.netchamp.dev/mcp (HTTP) - Connected`

**Cursor**: `Add this to ~/.cursor/mcp.json, then restart Cursor.`
```json
{ "mcpServers": { "sketch": {
  "url": "https://sketch.netchamp.dev/mcp",
  "headers": { "Authorization": "Bearer <token>" } } } }
```
**VS Code**: `Add this to .vscode/mcp.json in your project, or to your user mcp.json. The top-level key is servers, not mcpServers.`
```json
{ "servers": { "sketch": {
  "type": "http",
  "url": "https://sketch.netchamp.dev/mcp",
  "headers": { "Authorization": "Bearer <token>" } } } }
```
**Claude Desktop**: `Claude Desktop reads stdio servers only, so it needs the mcp-remote bridge. Add this to claude_desktop_config.json, then restart Claude Desktop. Node 18 or newer is required.`
```json
{ "mcpServers": { "sketch": {
  "command": "npx",
  "args": ["-y", "mcp-remote", "https://sketch.netchamp.dev/mcp",
           "--header", "Authorization: Bearer <token>"] } } }
```
**claude.ai**: an `Alert` theme `orange`. Title `claude.ai connectors do not work yet`. Body
`A claude.ai custom connector takes a URL only. It cannot send the Authorization header Sketch
needs. Sketch will support claude.ai when OAuth ships. Use Claude Code, Cursor, VS Code, or Claude
Desktop today.`

### Prototypes screen empty state, and the sidebar footer

`No prototypes yet` / `Sketch has no editor. Your own agent writes the prototypes over MCP.` /
`Connect an agent first, then ask it to build something.` / solid `Connect your agent` →
`/settings?tab=agent` / outline `New prototype`. Sidebar footer, with a token
`Agent token ready`; without, `Connect your agent`, linked to `/settings?tab=agent`.

## The `/mcp` error contract

Every body is `Content-Type: application/json`. `settings_url` is always `https://sketch.netchamp.dev/settings?tab=agent`.

| Case | Status | Raised in | Body |
|---|---|---|---|
| No `Authorization` header | 401 | `mcp/http.py` | `no_credentials` |
| `Authorization` with a scheme that is not `Bearer` | 401 | `auth.py` | `wrong_auth_scheme` |
| `Bearer <token>` that resolves to no user | 401 | `auth.py` | `invalid_token` |
| Valid token, no `Sketch Prototype` read right | 403 | `mcp/http.py` | `no_access` |
| Method is not POST | 405 | `mcp/http.py`; `before_request` for DELETE | JSON-RPC `-32600`, `Allow: POST` |

`no_credentials`, `WWW-Authenticate: Bearer realm="sketch"`:
```json
{"error": "no_credentials",
 "message": "Sketch needs a token. Send the header Authorization: Bearer sk_... on every request to /mcp. Copy your token from Settings.",
 "settings_url": "https://sketch.netchamp.dev/settings?tab=agent"}
```
`wrong_auth_scheme`, `WWW-Authenticate: Bearer realm="sketch", error="invalid_request"`:
```json
{"error": "wrong_auth_scheme",
 "message": "Sketch reads the Authorization header with the Bearer scheme only. Send Authorization: Bearer sk_... Do not use a custom header name, and do not send the token on its own.",
 "settings_url": "https://sketch.netchamp.dev/settings?tab=agent"}
```
`invalid_token`, `WWW-Authenticate: Bearer realm="sketch", error="invalid_token"`:
```json
{"error": "invalid_token",
 "message": "This Sketch token is not valid. It was regenerated, mistyped, or it belongs to another account. Copy the current token from Settings and paste it into your MCP client again.",
 "settings_url": "https://sketch.netchamp.dev/settings?tab=agent"}
```

These bodies are plain JSON, not JSON-RPC. Auth fails before the body is parsed, so there is no
request `id` to answer, and `id: null` would claim a reply to a message the server never read. This
overrides E4's "make it JSON-RPC" wording and keeps E4's real fix: every body names the mistake and
the Settings URL.

### Where the wrong-token case is caught, and why

In `sketch/auth.py`, not `sketch/mcp/http.py`. Verified against the installed Frappe
(`apps/frappe` at `0219b22`) and werkzeug 3.1.6:

- `frappe/app.py:80` calls `validate_auth()` before `get_response()`, so a `page_renderer`
  never sees a bad token. `http.py` is too late.
- `frappe/auth.py:643-658`: `validate_auth()` calls `validate_auth_via_hooks()` first, then
  raises `frappe.AuthenticationError` when the `Authorization` header splits into two parts
  and the user is still Guest. Sketch's hook runs inside that window.
- `frappe/auth.py:772-774`: `validate_auth_via_hooks` discards the return value. **There is no
  `auth_hooks` return contract.** Raising is the only stop. `frappe.local.flags` holds no
  auth-suppression flag either; `frappe/auth.py:98` sets only `disable_traceback`, which does not
  change the HTML page.
- `frappe/app.py:121` does `e.get_response(request.environ) if isinstance(e, HTTPException)`, and
  werkzeug 3.1.6 `HTTPException.get_response` returns `self.response` unchanged when the constructor
  was given one. So `raise Unauthorized(response=Response(...))` emits the exact bytes above,
  bypasses `handle_exception`, and leaks no traceback at any `developer_mode`. That closes E2 as
  well. `sketch/auth.py:_is_mcp_path` already scopes it, so the raise cannot reach Desk or `/api`.
- `WWW-Authenticate`: core attaches it only when OAuth Settings
  `show_protected_resource_metadata` is on (`frappe/app.py:242`). It is off, so no 401 carries it
  today (E3). Sketch sets its own header with no `resource_metadata` parameter, because
  `/.well-known/oauth-protected-resource` returns 404. Add it when OAuth ships.

## Decisions only Faris can make

1. Open signup now? Recommend yes, right after wave 1, so the connect path is fixed before the first stranger meets it.
2. SMTP, or a password at signup? Recommend the password: it closes A2, A3 and A4 together and needs no mail server.
3. OAuth for claude.ai in scope? Recommend no; ship the honest `Alert` in wave 1 and reopen after signup is live.
4. `developer_mode = 0` on the public site? Recommend yes after wave 1, as defence in depth; wave 1 stops the traceback leak on its own.
5. Reserve the first usernames? Recommend yes before 2.3: take `sketch`, `admin`, `api`, `u` and `www`, because a name is frozen forever.

## Out of scope

- OAuth for `/mcp` and the three `.well-known` documents. Spec 16 defers it. Wave 1 says so on screen instead.
- Rate limits, prototype counts and storage caps. Spec 16 defers them; wave 2 opens signup, so they become the next effort.
- A username-change flow. Spec 3 freezes the username on purpose. Recovering the accounts lost to A2: five Error Log rows, and a manual fix is cheaper than code.
- E6 over HTTP. Frappe parses the body before any Sketch hook runs. Fixing it means a core change.
- Any new SPA screen. Every fix above edits a file that already exists.
