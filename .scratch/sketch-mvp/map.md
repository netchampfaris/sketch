# Sketch MVP — wayfinder map

Label: wayfinder:map
Tracker: local markdown (`.scratch/sketch-mvp/`). Tickets live in `issues/`.

## Destination

A spec for the Sketch MVP that `/implement` can execute, plus the empty
`sketch-bench` and `sketch` app scaffold already created so the spec has a
repo to land in. Building the MVP is a separate effort.

## Notes

- Product: **Sketch**, hosted at `sketch.netchamp.dev`. Anyone signs up.
  Their own agent connects over MCP and writes high-fidelity frappe-ui
  prototypes. Sketch has no agent panel of its own.
- Skills every session must load: `frappe-ui` for any UI work, `grilling` +
  `domain-modeling` for grilling tickets, `research` for research tickets,
  `prototype` for prototype tickets, `devbox-services` for tunnel or service
  work.
- Standing preferences: ASD-STE100 writing. Subagents must not post, push,
  or write outside `/home/faris/benches` without Faris's confirmation.
  Branches from this box use the `forge/` prefix.
- Glossary lives in `CONTEXT.md` at the app repo root
  (`apps/sketch/CONTEXT.md`).
- SMTP for signup verification mail is ordinary deploy-time config, not a
  decision. Ticket 03 was removed 2026-08-26. The spec names it as a setup
  step and stops there.

## Decisions so far

<!-- one line per closed ticket: gist, then link -->

- [Scaffold sketch-bench and the sketch app](issues/01-scaffold-bench-and-app.md): done 2026-08-26. Bench `/home/faris/benches/sketch-bench` on Frappe develop `0219b22`, site `sketch.localhost` (web 8007), app `apps/sketch` on branch `forge/mvp`, frappe-ui `1.0.0-beta.55` with Vite 8, SPA scaffolded at `/sketch` (the spec moves it to `/`; see the charting decisions). Passwords in `sites/sketch.localhost/site_config.json`. Tracker now lives in `apps/sketch/.scratch/sketch-mvp/`.
- [Route sketch.netchamp.dev through the tunnel](issues/02-tunnel-route.md): done 2026-08-26. `https://sketch.netchamp.dev` serves `sketch.localhost`; SPA scaffolded at `/sketch`, moving to `/`; `/socket.io` → 9007, rest → 8007. Site `host_name` set.
- [Run sketch-bench as a service](issues/16-sketch-bench-service.md): done 2026-08-26. `sketch-bench.service` user unit, enabled, linger on. `Procfile` has no `watch`; rebuild the frontend with `yarn build`. Scheduler enabled. Backup cron removed 2026-08-26: it was DB-only, and prototype files live on disk.
- [How do prototype Tailwind classes get styles at runtime](issues/06-runtime-tailwind.md): self-host the MIT `tailwindcss@3.4` engine in the browser with the frappe-ui preset (145 KB gzip, ~300 ms first compile, handles classes added after first paint). Ship precompiled frappe-ui internals CSS first. Reject Play CDN, safelist, twind, UnoCSS.
- [What to reuse from Builder's /mcp implementation](issues/09-builder-mcp-reuse.md): copy `http.py` and `rpc.py`, wire `/mcp` with one `page_renderer` hook, auth is a Sketch `auth_hooks` function reading a `Sketch Token` Bearer header (amended by ticket 12; was Frappe core `api_key`/OAuth), keep the `TOOLS`/annotations pattern, drop `ctx.py` and `pages.py`.
- [Pick the in-browser SFC compiler and TypeScript stripper](issues/05-sfc-compiler-and-ts.md): hand-roll `@vue/compiler-sfc` (esm-browser) + `sucrase` for type stripping, the `@vue/repl` pair. 295 KB gzip, 2.8 ms per SFC. Reject `vue3-sfc-loader` (unmaintained, pins compiler-sfc 3.4.15, swallows parse errors) and `esbuild-wasm` (3.7 MB wasm, 4.7x slower). Check `parse().errors` before `compileScript`.
- [Define the MCP tool surface and server instructions](issues/08-mcp-tool-surface.md): 11 tools. `list_prototypes`, `create_prototype(name)`, `list_files`, `read_files`, `write_files`, `edit_file`, `delete_file`, `check(screenshot)`, `get_skill`, `set_public`, `set_name`. No `delete_prototype`; deletion is a UI act. Destructive: `delete_file`, `set_public`. Users pick a unique Username; URLs are `sketch.netchamp.dev/u/<username>/<slug>`, slug frozen at creation (amended by ticket 12; was root level). Short `INSTRUCTIONS` (~1.2k chars) always in context, full ~9k-token skill behind `get_skill`.
- [Define the doctypes and permission model](issues/12-data-model.md): two doctypes only. `Sketch Prototype` (hash name, `title`/`slug`/`pin`/`is_public`, unique `(owner, slug)`) and `Sketch Token` (Bearer, `auth_hooks`, refused outside `/mcp`, one retrievable token per user). Prototype files and Runtimes live on disk, not in the DB. Username is Frappe's `User.username`, enforced by a Sketch `User.validate` hook that runs after core's. URLs move to `/u/<username>/<slug>` and the reserved list is dropped. Role `Sketch User` with `if_owner`; Guest gets nothing, and the Viewer serves public links with `ignore_permissions` after checking `is_public`.
- [Build the browser Runtime for frappe-ui 1.0.0-beta](issues/04-runtime-bundle.md): built and measured 2026-08-26. `sketch/public/runtimes/1.0.0-beta.55/` with a `manifest.json`, served through Frappe's existing assets symlink; ticket 12's layout stands. Static import map for `vue`, `vue-router`, `frappe-ui`, `frappe-ui/list`; every frappe-ui subpath needs its own asset. A hand-written 2-page Prototype renders with Sidebar, List, Dialog and a form, zero errors. 313 KB gzip to render, 443 KB for the two compilers, 559 KB Inter fonts. 398 ms boot to painted, of which Tailwind is 286 ms. The Runtime owns the mount, so `src/router.ts` exports routes. `upload_file` goes over XHR, not `fetch`. Prototype on `forge/proto/04-runtime-bundle`.
- [Prototype the check step: compile, render, screenshot](issues/10-check-step.md): done 2026-08-27. `check` is one synchronous MCP call: the Frappe worker proxies to `sketch-checkd`, a Node service holding one Chromium, which opens the Viewer and reads `window.__sketch`. No server-side compile, no RQ job, no poll tool. 913 ms end to end for 7 files and 2 routes; 2.6 s for 30 files and 12 routes. Chromium launches in 45 ms, so the daemon buys Node boot, not browser warmth. Keep the production Runtime: unresolved components are rebuilt from `_resolveComponent` names filtered against `app._context.components`, and prop type warnings stay lost. One PNG per static route, 28-35 KB. Three Runtime defects fixed on the way.
- [How Frappe develop handles open signup and email verification](issues/13-signup-on-develop.md): done 2026-08-26. Open signup is Website Settings `disable_signup = 0` plus the `max_signups_allowed_per_hour` throttle. Verification is the password-reset link, and signup returns 200 even when the mail fails, so SMTP is not optional. Role comes from Portal Settings `default_role`, and `Sketch User` must set `desk_access = 0` or the user is flipped to System User. `website_route_rules` cannot claim `/`; use the `home_page` hook. No hook adds a field to `sign_up`, so use `override_whitelisted_methods`. version-16 is identical on all of it.
- [Prototype the three Sketch screens](issues/14-sketch-ui-prototype.md): Faris chose B — Studio: persistent sidebar, visual Prototype gallery with UI-only management and visible Public URLs, structured profile/agent settings, and a fullscreen Viewer with no Sketch chrome. Prototype preserved on `forge/proto/14-sketch-ui` at `4d9536d`.
- [What the served frappe-ui skill contains](issues/11-served-skill.md): done 2026-08-27. A Sketch-owned rewrite, not a trim of the box skill, at `sketch/skill/frappe-ui.md` in app source, **not** in the Runtime folder, so an edit reaches Prototypes made before it. One file for every Pin. `get_skill()` takes no arguments. 2,900 words, one blob, eight sections. Every lucide icon works. Eight specifiers resolve and nothing else. `dayjs` is frappe-ui's instance with nine plugins. Sketch owns the theme, and dark mode is in the MVP. Runtime work folded in and committed at `a4a932d`: the icon map, `frappe-ui/editor`, `frappe-ui/charts`, `frappe-ui/icons`, `dayjs`, and `FrappeUIProvider` in the mount. 320 KB gzip to render, 543 KB for the compilers, 426 ms boot. `sketch/tests/test_skill_names.py` keeps the skill honest.
- [How the Viewer and the checker read a private Prototype's files](issues/17-viewer-file-access.md): done 2026-08-27. **There is no files endpoint.** The `page_renderer` on `/u/<username>/<slug>` serves the pinned Runtime's own `viewer.html` from disk with the source tree substituted into a `sketch-data` slot, so one authorisation guards everything. Ticket 04's `files.json` is gone. The serialiser must escape `<` as `\u003c`, or the `</script>` in any Vue file breaks the Viewer. `check` mints a 60-second signature over the hash id and `sketch-checkd` opens `127.0.0.1:8007` with a `Host` header; a planted session and the Sketch Token were both rejected. Usernames are frozen at signup. Response carries `no-store` and `frame-ancestors 'self'`. Four Runtime changes: read the DOM, a module registry so import cycles work, `.css` imports injected, and an `empty` status. Nine specifiers now, not eight: `@vueuse/core` joins for the Compose recipe. Recipes are the eight from `ui.frappe.io/recipes`, desktop only, plus Blank, vendored in Sketch. Inter italic dropped. Theme control in the sidebar footer.
- [Which MCP protocol revision Sketch speaks](issues/18-mcp-protocol-revision.md): done 2026-08-27. **Dual-era.** One endpoint serves legacy `2025-06-18` and modern `2026-07-28`; the server picks by how the client opens, and the spec permits it. `2025-11-25` is not served. Modern only was rejected because the newest TypeScript SDK client defaults to `mode: 'legacy'` and would get a 400. Legacy only works today (Claude Code 2.1.246 was captured falling back and running), but ships two revisions behind. Two premises corrected: Builder is not `2025-06-18`-only (`rpc.py:17` has two revisions) and already has `server/discover`; the method is new as a server *requirement*, not as a method. About 70 lines in `rpc.py`, 1-3 in `http.py`. `rpc.handle` must gain HTTP 400. Modern path unverified against a running client.

Decisions made while charting (no ticket, recorded here once):

- Name is Sketch. App and repo `sketch`. Prototypes are high fidelity.
- Prototype = Vue SFC files, compiled in the browser. No server build per
  prototype.
- Each prototype pins one frappe-ui version. Launch supports only the newest
  `1.0.0-beta.x`.
- MCP auth is a per-user Bearer token on a streamable-HTTP `/mcp` endpoint.
  Transport is stateless (SEP-2575): no session ids, POST only, no SSE.
- The frappe-ui skill is served through MCP, versioned with the pin.
- Signup is email + password with a verification email.
- Prototypes are private by default with a public toggle. Every user picks
  a unique Username. A Prototype renders in a same-origin iframe (the
  Viewer) at `sketch.netchamp.dev/u/<username>/<slug>`.
- Data: plain `ref`s in prototype files, inline. No backend, no stubs, no
  Fixture API. (Revised 2026-08-26; see the Out of scope entry.)
- Sketch UI: prototypes list, fullscreen viewer with no Sketch chrome,
  settings (token + connect snippet). No in-browser editor. Rename and
  delete are UI-only; neither is an MCP tool.
- The SPA serves at the site root `/`, not `/sketch`. Prototypes sit under
  `/u/`, so the root is free. The scaffold still serves `/sketch`; moving it
  is implementation work.
- Nothing is backed up. The backup cron is removed. Prototypes are
  disposable.
- Multi-page prototypes with vue-router (hash mode). A Prototype is an
  app-like tree: `src/pages`, `src/components`, `src/App.vue`,
  `src/router.ts`.
- Feedback: writes are silent. A `check` tool at the end of each agent
  loop returns compile errors, console errors, and a screenshot.
- TypeScript allowed. Type stripping only in the browser. Type checking is
  not in the MVP.
- Stack: `sketch-bench` on Frappe `develop` (v17), Python 3.14, ports
  web 8007, socketio 9007, redis 13007/11007, site `sketch.localhost`.
  Faris chose `develop` over `version-16` knowing public users ride an
  unstable branch.

## Not yet specified

- Abuse controls for open signup: prototype count, file size, `check`
  rate, storage per user. Ticket 10 gives the numbers to rate-limit
  against: one check holds a Chromium context for about a second, and
  eight at once take 3.1 s each. Bandwidth counts too: ticket 11 added
  the editor and charts bundles, 345 KB and 273 KB gzip each.
- OAuth for claude.ai connectors. Builder's `/mcp` gets it almost free from
  Frappe's OAuth provider; revisit after the MCP server ticket.
- Adding a second frappe-ui version and moving a prototype's pin.
- Snapshots or revert history for a prototype.
- Live reload of the viewer when the agent writes files (socketio).
- Type checking (`vue-tsc`) inside `check`.
- A skill per Pin. One file serves every Pin today. At a second Pin it
  describes one frappe-ui version while some Prototypes render with
  another, and nothing tells the agent. Ticket 11 accepted the cost.
- Dark-mode screenshots in `check`. It renders light only. A raw colour
  that shows up only in dark is invisible to the agent.
- Iframe sandboxing. The Viewer is same-origin, so Prototype code can reach
  `parent` and Sketch's cookies, and signup is open to anyone. Revisit
  whether the iframe needs `sandbox="allow-scripts"` without
  `allow-same-origin`, and what that costs the Runtime.
- Onboarding copy: what a new user sees before any prototype exists.
- Mobile recipe variants. Ticket 14 took the eight desktop recipes only,
  because the Viewer and `check` are a 1280x800 frame.

## Out of scope

- A real Vite dev server in the browser, in a WebContainer. Ruled out
  2026-08-27 by ticket 17's session. Verified: Vite 8.2.2 has one entry
  point, `dist/node/index.js`, and depends on `rolldown` and `lightningcss`,
  both native `.node` binaries. So it means Node in the browser. It would buy
  real fidelity (`main.ts`, history routing, asset imports, any npm package)
  and real HMR, and it would cost Node boot plus `npm install` per Prototype
  against a measured 426 ms, void ticket 10's 913 ms, boot a Node VM to show
  a public read-only link, move previews to `*.webcontainer.io`, and raise a
  licence question on an open-signup public site. It voids tickets 04, 05, 06
  and 10, so it is a separate effort, not a ticket.

- Browsing other users' public Prototypes. Usernames are in the MVP, so
  `/u/<username>` and a discovery surface can be added later without moving a
  single URL. The browse page itself is a separate effort.
- [Design the Fixture API and the stubbed resources](issues/07-fixtures-and-stubs.md):
  ruled out 2026-08-26. No frappe-ui component fetches its own data, so a
  Prototype needs no stubs to render. Prototype data lives in `ref`s.

- In-browser code editor. The agent is the editor.
- Sharing to a specific other user. Only owner-private or public link.
- A Sketch-owned agent or chat panel.
- Mock API backend per prototype.
- The frappe-ui `0.1.x` line.
- Building the MVP itself. That is the next effort, fed by the spec.
