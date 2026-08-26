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

- [Scaffold sketch-bench and the sketch app](issues/01-scaffold-bench-and-app.md): done 2026-08-26. Bench `/home/faris/benches/sketch-bench` on Frappe develop `0219b22`, site `sketch.localhost` (web 8007), app `apps/sketch` on branch `forge/mvp`, frappe-ui `1.0.0-beta.55` with Vite 8, SPA served at `/sketch`. Passwords in `sites/sketch.localhost/site_config.json`. Tracker now lives in `apps/sketch/.scratch/sketch-mvp/`.
- [Route sketch.netchamp.dev through the tunnel](issues/02-tunnel-route.md): done 2026-08-26. `https://sketch.netchamp.dev` serves `sketch.localhost`; SPA at `/sketch`; `/socket.io` → 9007, rest → 8007. Site `host_name` set.
- [Run sketch-bench as a service](issues/16-sketch-bench-service.md): done 2026-08-26. `sketch-bench.service` user unit, enabled, linger on. `Procfile` has no `watch`; rebuild the frontend with `yarn build`. Scheduler enabled.
- [How do prototype Tailwind classes get styles at runtime](issues/06-runtime-tailwind.md): self-host the MIT `tailwindcss@3.4` engine in the browser with the frappe-ui preset (145 KB gzip, ~300 ms first compile, handles classes added after first paint). Ship precompiled frappe-ui internals CSS first. Reject Play CDN, safelist, twind, UnoCSS.
- [What to reuse from Builder's /mcp implementation](issues/09-builder-mcp-reuse.md): copy `http.py` and `rpc.py`, wire `/mcp` with one `page_renderer` hook, auth is Frappe core (token and OAuth Bearer both work on develop), keep the `TOOLS`/annotations pattern, drop `ctx.py` and `pages.py`.
- [Pick the in-browser SFC compiler and TypeScript stripper](issues/05-sfc-compiler-and-ts.md): hand-roll `@vue/compiler-sfc` (esm-browser) + `sucrase` for type stripping, the `@vue/repl` pair. 295 KB gzip, 2.8 ms per SFC. Reject `vue3-sfc-loader` (unmaintained, pins compiler-sfc 3.4.15, swallows parse errors) and `esbuild-wasm` (3.7 MB wasm, 4.7x slower). Check `parse().errors` before `compileScript`.
- [Define the MCP tool surface and server instructions](issues/08-mcp-tool-surface.md): 11 tools. `list_prototypes`, `create_prototype(name)`, `list_files`, `read_files`, `write_files`, `edit_file`, `delete_file`, `check(screenshot)`, `get_skill`, `set_public`, `set_name`. No `delete_prototype`; deletion is a UI act. Destructive: `delete_file`, `set_public`. Users pick a unique Username; URLs are `sketch.netchamp.dev/<username>/<slug>` at the site root, slug frozen at creation. Short `INSTRUCTIONS` (~1.2k chars) always in context, full ~9k-token skill behind `get_skill`.

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
  Viewer) at `sketch.netchamp.dev/<username>/<slug>`.
- Data: plain `ref`s in prototype files. No backend, no stubs. (Revised
  2026-08-26; see the Out of scope entry for the Fixture API.)
- Sketch UI: prototypes list, fullscreen viewer with no Sketch chrome,
  settings (token + connect snippet). No in-browser editor. Rename and
  delete are UI-only; neither is an MCP tool.
- Multi-page prototypes with vue-router (hash mode) and a `routes.js`.
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
  rate, storage per user. Depends on the data model and the check design.
- OAuth for claude.ai connectors. Builder's `/mcp` gets it almost free from
  Frappe's OAuth provider; revisit after the MCP server ticket.
- Adding a second frappe-ui version and moving a prototype's pin.
- Snapshots or revert history for a prototype.
- Live reload of the viewer when the agent writes files (socketio).
- Type checking (`vue-tsc`) inside `check`.
- Whether `2025-06-18` is still the current MCP protocol revision. Builder
  knows no later one. Not verified against the spec.
- Iframe sandboxing. The Viewer is same-origin, so Prototype code can reach
  `parent` and Sketch's cookies, and signup is open to anyone. Revisit
  whether the iframe needs `sandbox="allow-scripts"` without
  `allow-same-origin`, and what that costs the Runtime.
- Keeping the reserved-username list correct as Frappe adds routes. A new
  core route can shadow an existing user at the site root.
- Onboarding copy: what a new user sees before any prototype exists.

## Out of scope

- Browsing other users' public Prototypes. Usernames are in the MVP, so
  `/<username>` and a discovery surface can be added later without moving a
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
