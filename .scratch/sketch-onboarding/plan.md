# Sketch onboarding: the fix plan

v2, 2026-08-29. v1 is in git at `5e105c0`. Input `.scratch/sketch-onboarding/problems.md`.
Branch `forge/mvp`. Words `CONTEXT.md`. Components from the `frappe-ui` skill,
`frappe-ui@1.0.0-beta.55`.

## What changed since v1

Three things overtook v1.

1. **Signup is GitHub only.** The email signup form, `sketch/signup.py` and the password
   question are deleted. **Wave 2 is dead.** A1 to A6, A8 and A9 all describe a form that
   no longer exists.
2. **Branding landed** (v1 step 3.1). A7 is closed.
3. **Faris asked for a simpler UI.** The sidebar goes. That is new work, and it is now
   wave 2.

One v1 fact was wrong, and it changes a step. v1 says no 401 carries `WWW-Authenticate`
because OAuth Settings `show_protected_resource_metadata` is off. It is **on**. Every 401
on the test site carries
`WWW-Authenticate: Bearer resource_metadata=".../.well-known/oauth-protected-resource"`,
and that document returns 200, naming the site as an OAuth authorization server. Sketch
serves no OAuth on `/mcp`. So a client that reads the header starts a flow that cannot
finish, instead of asking the user for a token. Sketch must send its own header on `/mcp`,
with no `resource_metadata` parameter. See the error contract below.

## Closed already

| Problem | How |
|---|---|
| A1 signup shut | Open through GitHub. `sketch/install.py`, `oauth_hooks.py` |
| A2 A3 A4 A5 A6 A8 A9 | Moot. The email signup form is deleted |
| A7 Frappe branding before the SPA | Website Settings in `install.py`, two SVG marks |

## Wave 1: an agent connects, and a failure names the fix

Worth: the whole product. A wrong token returns an 8 KB HTML page (E1), and the connect
config is never on screen (C1).

**1.1 Raise the auth failure in `sketch/auth.py`.** Closes E1, E2, E5. `validate_sketch_token`
raises `werkzeug.exceptions.Unauthorized` with a prebuilt `Response`, on `/mcp` only.
Order: refuse non-`/mcp`; return when the session is already a user; return when there is
no `Authorization` header; raise `wrong_auth_scheme` when the scheme is not `Bearer`; set
the user on a good token; raise `invalid_token` otherwise. Effort M.

**1.2 Rewrite the `/mcp` 401 and 403 bodies.** Closes E3, E4. Every 401 carries the Sketch
`WWW-Authenticate` header. Delete the false comment in the `http.py` docstring.
`sketch/mcp/http.py`. Effort S.

**1.3 The connection screen.** Closes C1, C2, C3, C5, C6, C7, D1, D2, D3, B3. One screen,
not a tab in a settings tree. Token, endpoint, then one ready-made block per harness in a
`Tabs`. `Show` / `Hide` on the token (C6). `dialog.confirm` on Regenerate (C5).
`initialData` on `agentToken` so the card does not collapse while it loads (C7).
`frontend/src/pages/SettingsScreen.vue`, `frontend/src/store.ts`. Effort L.

**1.4 Empty state points at the connection screen.** Closes B1. `PrototypesScreen.vue`.
Effort S.

**1.5 Connection state is live, not dead text.** Closes B2, C4. `has_token` is the wrong
signal: `get_agent_token` mints a token on read, so it turns true the moment a user opens
the screen, connected or not. The real signal is `last_used` on `Sketch Token`, stamped by
`sketch/auth.py` on a good token. Read it from `get_session`, so no screen mints a token
just by rendering. Effort M.

**1.6 Tests.** New `sketch/tests/test_mcp_errors.py`. Cases: a wrong token returns JSON,
not HTML; no traceback at `developer_mode = 1`; the guest 401 names the header; the
wrong-scheme 401 differs from the guest 401; every failure body carries `error`, `message`
and `settings_url`; every 401 carries `Bearer realm="sketch"` and no `resource_metadata`;
`last_used` moves; and a token still opens `/mcp` and nothing else. Effort M.

## Wave 2: the shell loses the sidebar

Worth: one less thing between a new user and the connect screen. Faris asked for it.

Sketch has two screens and one action. A 14 rem sidebar to hold two links is furniture.

**2.1 Delete `AppSidebar.vue` and `DesktopShell`.** `App.vue` renders one top bar and the
router view in a centred column. Effort M.

**2.2 The top bar.** Left: the Sketch mark, linking to `/`. Right: the account `Dropdown`
on an `Avatar`. The dropdown holds `@username` as a group label, `Agent connection`, a
theme submenu, and `Log out`. `ThemeControl.vue` folds into that submenu and the file goes.
Fixed height, so nothing moves while the session loads. Effort M.

**2.3 Settings becomes one column.** The local nav column, the `?tab=` query and the
`Profile` / `Agent connection` split all go. One scroll: `Agent connection` first, because
that is why anyone opens the page, then `Profile`. Effort S.

## Wave 3: endpoint edges

**3.1 Guest never loads the SPA.** Closes B4. Login guard in `get_context`.
`sketch/www/sketch.py`. Effort S.

**3.2 Endpoint edges.** Closes E7, E8, E9. Match `/mcp` case-insensitively in `auth.py`
and `http.py`. A `before_request` hook answers `DELETE /mcp` with 405 and `Allow: POST`,
and `OPTIONS /mcp` with 204. Core raises `NotFound` for DELETE and returns a bare 200 for
OPTIONS before any renderer runs, so a renderer cannot fix either. Effort M.

**3.3 A broken body answers the parse error.** Closes E6. Frappe throws `DataError`
inside `make_form_dict` (`frappe/app.py:302-308`), called from `init_request` at
`frappe/app.py:178`. That is ahead of `before_request`, ahead of `validate_auth()` and
ahead of every renderer, so no hook on the way in can catch it, and the client gets a 417
HTML page. The way out is open: `run_after_request_hooks` is in the `finally` of
`application` (`frappe/app.py:132-134`) and is handed the same `Response` object core
returns (`frappe/app.py:141`). An `after_request` hook rewrites that page as
`-32700` with HTTP 400. Scope is two tests: the path is `/mcp`, and Sketch did not build
the response. `sketch/mcp/http.py`, `sketch/mcp/rpc.py`, `sketch/hooks.py`. Effort M.

## The `/mcp` error contract

Every body is `Content-Type: application/json`. `settings_url` is the public base plus
`/settings`, derived from `_public_base()`, never hardcoded.

| Case | Status | Raised in | `error` |
|---|---|---|---|
| No `Authorization` header | 401 | `mcp/http.py` | `no_credentials` |
| Scheme is not `Bearer` | 401 | `auth.py` | `wrong_auth_scheme` |
| `Bearer <token>` resolving to no user | 401 | `auth.py` | `invalid_token` |
| Valid token, no `Sketch Prototype` read right | 403 | `mcp/http.py` | `no_access` |
| Method is not POST | 405 | `mcp/http.py`, `before_request` for DELETE | JSON-RPC `-32600`, `Allow: POST` |

Messages:

- `no_credentials`: `Sketch needs a token. Send the header Authorization: Bearer sk_... on every request to /mcp. Copy your token from Settings.`
- `wrong_auth_scheme`: `Sketch reads the Authorization header with the Bearer scheme only. Send Authorization: Bearer sk_... Do not use a custom header name, and do not send the token on its own.`
- `invalid_token`: `This Sketch token is not valid. It was regenerated, mistyped, or it belongs to another account. Copy the current token from Settings and paste it into your MCP client again.`

Body shape `{"error": ..., "message": ..., "settings_url": ...}`. Plain JSON, not JSON-RPC:
auth fails before the body is parsed, so there is no request `id` to answer, and `id: null`
would claim a reply to a message the server never read.

`WWW-Authenticate` per case, on `/mcp` only:

- `no_credentials` -> `Bearer realm="sketch"`
- `wrong_auth_scheme` -> `Bearer realm="sketch", error="invalid_request"`
- `invalid_token` -> `Bearer realm="sketch", error="invalid_token"`

No `resource_metadata` parameter, for the reason at the top of this file. Add one when
OAuth ships.

### Why the wrong-token case is caught in `auth.py`, not `http.py`

Verified against the installed Frappe (`apps/frappe` at `0219b22`) and werkzeug 3.1.6:

- `frappe/app.py` calls `validate_auth()` before `get_response()`, so a `page_renderer`
  never sees a bad token. `http.py` is too late.
- `frappe/auth.py` `validate_auth_via_hooks` discards the hook return value. There is no
  `auth_hooks` return contract. Raising is the only stop.
- `frappe/app.py` does `e.get_response(request.environ)` for an `HTTPException`, and
  werkzeug returns the constructor's `response` unchanged. So the exact bytes are emitted,
  `handle_exception` is bypassed, and no traceback leaks at any `developer_mode`. That
  closes E2.
- `_is_mcp_path` scopes the raise, so it cannot reach Desk or `/api`.

## The copy

### The connection screen

Heading `Agent connection`. Lead: `Your agent talks to Sketch over MCP. Copy the token,
then paste one block below into your client.`

Token block: label `Token`; description `One user, one token. Anyone who holds it can write
your prototypes.`; actions `Copy token`, `Show` / `Hide`, `Regenerate`; under the field
`Last agent request: 2 minutes ago` or `No agent has connected yet.` Regenerate confirm:
title `Regenerate token?`, body `Every agent that holds the old token stops working at
once. You must paste the new token into each client again.`, confirm `Regenerate`, theme
`red`.

Endpoint block: label `Endpoint`, action `Copy endpoint`, three help lines:
`Transport: streamable HTTP. POST only.` / `Header name: Authorization` /
`Header value: Bearer <token>`.

`Set up your client`: a `Tabs`, one tab per harness. Every snippet gets a `Copy` button and
the toast reads `Copied`. Every snippet carries the live token, not a placeholder. The
snippets themselves are in `harnesses.md` next to this file, each one verified against the
vendor's own documentation.

Harnesses, in tab order: Claude Code, Codex, OpenCode, Cursor, VS Code, Claude Desktop,
Gemini CLI. claude.ai is an `Alert` theme `orange`, not a tab: a claude.ai custom connector
takes a URL only and cannot send the `Authorization` header Sketch needs.

### Prototypes empty state

`No prototypes yet` / `Sketch has no editor. Your own agent writes the prototypes over
MCP.` / `Connect an agent first, then ask it to build something.` / subtle
`Connect your agent` -> `/settings` / outline `New prototype`. No button is
solid, anywhere.

## Decisions Faris already made

1. Signup: GitHub only. Closed.
2. Password at signup: moot, no form.
3. OAuth for claude.ai: no. Ship the honest `Alert`.
4. Sidebar: remove it.

## Still open for Faris

- `developer_mode = 0` on the public site. Wave 1 stops the traceback leak on its own, so
  this is defence in depth. Recommend yes after wave 1.
- The test site's web server on port 8017 runs under `setsid nohup`, not systemd. It dies
  on reboot, and the web tests then skip instead of failing.

## Out of scope

- OAuth for `/mcp` and the three `.well-known` documents. Spec 16 defers it. Wave 1 says so
  on screen instead.
- Rate limits, prototype counts and storage caps. Spec 16 defers them.
- A username-change flow. Spec 3 freezes the username on purpose.
- Core's other failures on `/mcp`: the rate limit, maintenance mode. They still serve an
  HTML page. `after_request` rewrites the broken-body 417 only, because keeping a status
  is worth more than making every page JSON.
