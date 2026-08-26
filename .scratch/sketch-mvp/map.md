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
- Glossary lives in `CONTEXT.md` at the app repo root once the scaffold
  exists. Until then the terms below are the glossary.

### Glossary (moves to CONTEXT.md after ticket 01)

- **Prototype**: a set of Vue SFC files, `.ts`/`.js` files, and a
  `routes.js`, owned by one User, rendered in the browser. High fidelity:
  real frappe-ui components and tokens, not a mock.
- **Runtime**: the shared browser bundle (Vue, vue-router, frappe-ui,
  Tailwind, SFC compiler, TS stripper) that renders a Prototype. One Runtime
  per supported frappe-ui version.
- **Pin**: the frappe-ui version a Prototype targets. Set at creation. A
  Prototype renders with the Runtime that matches its Pin.
- **Fixture**: sample data declared inside Prototype files. Stubbed
  resources resolve from Fixtures instead of a server.
- **Check**: the MCP step the agent runs once at the end of a user request.
  Returns compile errors, console errors, and a screenshot.
- **Public link**: an owner-set toggle. When on, anyone with the URL can
  view the Prototype read-only, without Sketch chrome.
- **Token**: the per-user Bearer credential an agent sends to `/mcp`.

## Decisions so far

<!-- one line per closed ticket: gist, then link -->

- [How do prototype Tailwind classes get styles at runtime](issues/06-runtime-tailwind.md): self-host the MIT `tailwindcss@3.4` engine in the browser with the frappe-ui preset (145 KB gzip, ~300 ms first compile, handles classes added after first paint). Ship precompiled frappe-ui internals CSS first. Reject Play CDN, safelist, twind, UnoCSS.
- [What to reuse from Builder's /mcp implementation](issues/09-builder-mcp-reuse.md): copy `http.py` and `rpc.py`, wire `/mcp` with one `page_renderer` hook, auth is Frappe core (token and OAuth Bearer both work on develop), keep the `TOOLS`/annotations pattern, drop `ctx.py` and `pages.py`.

Decisions made while charting (no ticket, recorded here once):

- Name is Sketch. App and repo `sketch`. Prototypes are high fidelity.
- Prototype = Vue SFC files, compiled in the browser. No server build per
  prototype.
- Each prototype pins one frappe-ui version. Launch supports only the newest
  `1.0.0-beta.x`.
- MCP auth is a per-user Bearer token on a streamable-HTTP `/mcp` endpoint.
- The frappe-ui skill is served through MCP, versioned with the pin.
- Signup is email + password with a verification email.
- Prototypes are private by default with a public-link toggle.
- Data: in-file fixtures behind stubbed frappe-ui resources. No backend.
- Sketch UI: prototypes list, fullscreen viewer with no Sketch chrome,
  settings (token + connect snippet). No in-browser editor.
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
- Process management and backups for `sketch-bench` (systemd user service
  like `builder-bench.service`).
- Onboarding copy: what a new user sees before any prototype exists.

## Out of scope

- In-browser code editor. The agent is the editor.
- Sharing to a specific other user. Only owner-private or public link.
- A Sketch-owned agent or chat panel.
- Mock API backend per prototype.
- The frappe-ui `0.1.x` line.
- Building the MVP itself. That is the next effort, fed by the spec.
