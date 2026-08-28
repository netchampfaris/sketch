# Sketch onboarding: what is broken

Reviewed 2026-08-29 on branch `forge/mvp` at `91c551c`. Four read-only agents
walked the flow: signup, the first screen, the token and the connect config,
the live `/mcp` endpoint, and the client side. Nobody created a user or a
token. Every claim below carries evidence.

Severity: **blocker** stops a new user. **friction** costs time or trust.
**polish** is cosmetic.

---

## A. Sign up

**A1. Signup is shut. Nobody can make an account. (blocker)**
`disable_signup = 1` on `sketch.localhost`. The login page hides the sign-up
link and answers `#signup` with "Signups have been disabled for this website."
`sketch/install.py:25` says this is on purpose until the MVP is done. Every
item below A1 is therefore reasoned from code, not observed in a browser.

**A2. No outgoing email account. The verification mail never leaves. (blocker)**
`Email Account` with `enable_outgoing = 1` returns `[]`. `site_config.json`
has no `mail_server`. Core swallows the send error (`user.py:481-486`), so
`sketch/signup.py:85-88` returns code 2, and `login.js:352-360` paints a green
banner: "Please ask your administrator to verify your sign-up". A dead end,
painted as success. Five Error Log rows already record the failure.

**A3. The user never picks a password. (blocker)**
`sketch/signup.py:66` sets a random password. The form takes Full Name, Email
and Username only. The mail link from A2 is the only way in. When that mail
fails the account is lost, and the username is burned: `sketch/user_hooks.py:130`
freezes it. Recovery needs a manual database edit.

**A4. The verification link dies in 20 minutes, with no resend. (friction)**
`reset_password_link_expiry_duration = 1200`. The expiry page offers no way
out. The fallback, `/login#forgot`, needs the same missing SMTP.

**A5. "Username taken" is known only after submit. (friction)**
`sketch/signup.py:53` throws after the whole form is sent. There is no live
check. The name is permanent, so this is the one field that most needs one.

**A6. The permanence warning vanishes as the user types. (friction)**
`signup_extra.html:34` says "It cannot be changed later". Lines 91-97 replace
that same element with the URL preview on the first keystroke.

**A7. Every page before the SPA is branded Frappe. (friction)**
Login title "Login", the Frappe logo, Website Settings `app_name = "Frappe"`,
and a welcome mail with subject "Complete Registration" and body "Welcome to
Frappe". No `welcome_email` hook in `sketch/hooks.py`.

**A8. Two different texts for one username rule. (polish)**
`signup_extra.html:67` and `SettingsScreen.vue:96` word it differently. Spec 11
pins the Settings wording.

**A9. The signup throttle answers a JSON call with an HTML page. (polish)**
`sketch/signup.py:44-51` calls `respond_as_web_page`, so the Sketch message is
never shown and the user reads the generic "Too many requests". Not verified.

---

## B. The first screen

**B1. The empty state never says to connect an agent. (blocker)**
Full text at `PrototypesScreen.vue:57-58`: "No prototypes yet" and "Pick a
recipe and your agent takes it from there." Nothing links to Settings. Nothing
names a token or an endpoint. The word "MCP" appears once in the whole SPA, at
`SettingsScreen.vue:121`.

**B2. The sidebar token status is dead text, and it goes stale. (friction)**
`AppSidebar.vue:39-49` renders "No agent token yet" in a plain `div`. It has no
link. Opening Settings creates the token but never reloads `session`, so the
sidebar keeps saying "No agent token yet" until a full page reload.
`regenerate` does call `session.reload()`; the first load does not.

**B3. Two clicks and no signpost to reach the token. (friction)**
Settings opens on the Profile tab (`SettingsScreen.vue:22`). "Agent connection"
is a second click.

**B4. A signed-out visitor loads the whole SPA before the bounce. (friction)**
`/` returns 200 to Guest with 578 kB of JS. `sketch/www/sketch.py` has no login
guard. The shell paints, two calls 403, then `App.vue:14-20` redirects.

---

## C. The token and the connect config

**C1. The config is invisible. The user copies blind. (blocker)**
The screen renders one bare URL. The JSON config exists only inside the "Copy
config" handler (`SettingsScreen.vue:48-62`). The header name `Authorization`,
the scheme `Bearer`, and the shape are never on screen. A user whose client
asks "header name?" must paste into an editor to find out.

**C2. The config names no client and no file. (friction)**
Surrounding copy is "Connect endpoint. Streamable HTTP. Bearer authentication."
It does not say which client, which file, or where.

**C3. There is no `claude mcp add` command anywhere. (friction)**
Grepped: not in the frontend, not in `sketch/`, not in `README.md`. Verified
correct syntax on the installed Claude Code 2.1.246:
`claude mcp add --transport http --scope user sketch <url> --header "Authorization: Bearer <token>"`.
`--scope` defaults to `local`, which binds the server to one directory. Sketch
is not a per-directory tool, so the missing `--scope user` is a real trap.

**C4. Nothing ever confirms the agent connected. (friction)**
`Sketch Token` holds `user` and `token` only. No `last_used`. No status. The
user cannot tell whether the failure is the token, the URL or the client.

**C5. Regenerate fires on one click, with no confirmation. (friction)**
`SettingsScreen.vue:138-143`. Every connected agent breaks at once, and the
screen never says so.

**C6. The token sits on screen in plain text. (polish)**
`SettingsScreen.vue:125-130` is a text input with no mask and no reveal toggle.
Spec 2 wants it readable, so a toggle keeps both.

**C7. The endpoint block collapses while the token loads. (polish)**
`agentToken` has no `initialData` (`store.ts:34-37`), so the card jumps.

---

## D. The client side

**D1. A claude.ai or Claude Desktop connector cannot use a Sketch token. (blocker)**
The custom-connector dialog takes a URL plus optional OAuth client id and
secret. It has no header field
(support.claude.com/en/articles/11175166). Sketch serves no OAuth: all three
`.well-known` paths answer 404, live. Spec 16 defers OAuth, so the gap is
known. The UI never says it, so a claude.ai user tries and fails with no clue.

**D2. The one config blob is wrong for two of four common clients. (friction)**
Claude Code: correct. Cursor: works, with a surplus `type` key. VS Code:
**wrong**, the top-level key is `servers`, not `mcpServers`. Claude Desktop
config file: **wrong**, it documents stdio only and needs the `mcp-remote`
bridge. Sources cited in the agent report.

**D3. No verify step is offered. (polish)**
`claude mcp list` answers clearly and is not mentioned:
`sketch: http://sketch.localhost:8007/mcp (HTTP) - Connected`.

---

## E. What the user sees when it fails

Tested live, local and through the tunnel. The tunnel passes POST `/mcp` and
the `Authorization` header through unchanged; every public response byte-matched
its local twin.

**E1. A wrong token returns an 8,583-byte HTML "Session Expired" page. (blocker)**
The worst message on the endpoint. `Content-Type: text/html`. Visible text:
"Session Expired. 401: Your session has expired, please login again to
continue." An MCP client cannot parse it. An agent that reads it will try to
log in, which is the wrong fix. The right fix is "your token is wrong or was
regenerated; copy a new one from Settings". Cause: core raises inside
`validate_auth()` (`frappe/app.py:80`) before the renderer runs, because
`sketch/auth.py:44` returns silently on a failed lookup.
This is the most likely failure a real user meets. It is very probably what
made the connection hard to set up.

**E2. The same failure leaks a Python traceback on the public URL. (blocker)**
With `Accept: application/json` the body is a JSON exception dump with file
paths and line numbers. `developer_mode = 1` on this site, so production shows
less, but the shape stays: an exception, never an MCP error object.

**E3. No 401 carries `WWW-Authenticate`, and a code comment claims it does. (blocker)**
Spec 8.1 says keep it. `sketch/mcp/http.py:11-16` documents it as attached by
core. Core gates it on OAuth metadata, which is off, so no 401 in the whole run
carried the header. The comment is false and it hides D1.

**E4. The Guest 401 body is not JSON-RPC and names no fix. (blocker)**
`{"error": "authentication required"}` from `http.py:42`. Every other error on
this endpoint is a JSON-RPC object. It names no header, no scheme, no URL, and
does not point at the Settings page that hands out the token.

**E5. A wrong header name is indistinguishable from no header. (friction)**
`X-Sketch-Token:` and a bare `Authorization: sk_...` both give the identical
generic 401. A lowercase `bearer` scheme is accepted, then falls into E1's HTML
page. Same class of mistake, two different answers.

**E6. A malformed JSON body answers HTTP 417 with an HTML error page. (friction)**
Frappe parses the body in `init_request`, so the `-32700` branch at
`sketch/mcp/rpc.py:106` is dead code.

**E7. `DELETE /mcp` answers 404, not 405. (friction)**
Streamable-HTTP clients send DELETE to tear a session down. GET correctly
answers 405 with `Allow: POST`; DELETE never reaches the renderer.

**E8. The path is case sensitive and misses into a marketing 404. (polish)**
`POST /MCP` returns an 8 kB Frappe 404 page. Trailing slash is handled.

**E9. `OPTIONS /mcp` returns 200 with no `Allow` header. (polish)**

---

## What works. Do not break it.

- The protocol is correct on both eras, live, local and public. `-32022` with
  HTTP 400 names `supported` and `requested`. The `-32020` header errors name
  the missing header. The cross-era `-32601` messages are the best writing on
  the endpoint.
- The token needs no knowledge: opening Settings creates it. It is retrievable
  forever, encrypted at rest, and comparison is constant-time.
- The snippet matches the server on every axis: path, host, header, scheme,
  prefix, transport. The copied URL is the public one; `:8007` never leaks.
- The `Sketch Token` is refused on every path except `/mcp`.
- Username validation, roles (`desk_access = 0`), and the `if_owner`
  permissions are all correct.
- Copy works without `navigator.clipboard`, and each button raises its own
  toast.

## Not verified

No agent created a user, enabled signup, or configured SMTP. Section A is read
from code, the database and the login page HTML. A9 is code-only. The wrong-token
page was not seen with `developer_mode = 0`.
