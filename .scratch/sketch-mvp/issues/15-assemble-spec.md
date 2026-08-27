# Assemble the MVP spec

Type: task
Status: resolved
Blocked by: nothing (01, 02, 04, 05, 06, 08, 09, 10, 11, 12, 13, 14, 16, 17, 18 resolved; 03 removed; 07 closed out of scope)

## Question

Write `apps/sketch/.scratch/sketch-mvp/spec.md` from every resolved ticket. It must let /implement build the MVP without new decisions. Include: doctypes, MCP tools, Runtime layout, check step, Sketch screens, signup flow, deployment on this box. No Fixture API: ticket 07 closed it, and all fixture data is inline in `ref`s. Close the map.

## Comments

### 2026-08-27 — from ticket 11

The spec must carry these, none of which are in the tickets they contradict:

- The skill is `sketch/skill/frappe-ui.md` in **app source**, not in the
  Runtime folder. Ticket 12's comment on ticket 11 says otherwise and is
  superseded.
- `get_skill()` takes **no arguments**. Ticket 08's tool table says
  `get_skill(prototype)` and is superseded.
- **Dark mode is in the MVP.** The Viewer resolves a `theme` URL parameter,
  then `localStorage['theme']`, then `prefers-color-scheme`, and sets
  `data-theme` on its own `<html>`. `check` forces light.
- The Runtime resolves **eight** specifiers, not four. Ticket 04's list is
  superseded, and so are its measured sizes.
- The **Sketch UI creates Prototypes**, with a recipe picker. Ticket 08
  recorded creation as an agent-only act. Ticket 08 and ticket 14 both carry
  amendments; the recipe set itself is still undecided.

### 2026-08-27 — from ticket 17

The spec must carry these. Several supersede the tickets they amend:

- **There is no files endpoint.** The `page_renderer` on `/u/<username>/<slug>`
  serves the pinned Runtime's own `viewer.html` with the source tree inside it.
  Ticket 04's `files.json` is gone.
- **The serialiser escapes `<` as `\u003c`.** Without it, the `</script>` in any
  Vue file breaks the Viewer. This is the single most likely thing to be missed.
- **Usernames are frozen at signup.** Amends ticket 12.
- **`create_prototype(name)` takes no recipe argument.** Recipes are UI-only.
  Amends the ticket 08 amendment that asked the question.
- **Nine specifiers, not eight.** `@vueuse/core` is added. Amends tickets 04 and
  11, and the served skill and `test_skill_names.py` with them.
- **Recipes: the eight from `ui.frappe.io/recipes`, desktop only, plus Blank**,
  vendored at `sketch/recipes/<slug>/src/…`.
- **Drop the Inter italic face.** Amends ticket 04.
- **Four Runtime changes**: the Viewer reads the DOM, the linker becomes a
  module registry so import cycles work, `.css` imports are injected, and a new
  `empty` status with a precondition check on `src/App.vue`.
- **`check` mints a 60-second signed URL** over the hash id, and
  `sketch-checkd` opens `127.0.0.1:8007` with a `Host: sketch.localhost` header.
- Headers on the Viewer response: `Cache-Control: no-store` and
  `Content-Security-Policy: frame-ancestors 'self'`.
- The theme control sits in the sidebar footer.

Ticket 18 must land first: it decides the MCP protocol revision, and tickets 08
and 09 are written against one that is two revisions old.

### 2026-08-27 — from ticket 18

The spec must carry these. They supersede the tickets they amend:

- **`/mcp` is dual-era.** It serves legacy `2025-06-18` and modern
  `2026-07-28` on the one endpoint, branching on the presence of
  `params._meta["io.modelcontextprotocol/protocolVersion"]`. Ticket 08's
  `PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26")` is superseded.
  `2025-11-25` is not served.
- **`rpc.handle` must be able to return HTTP 400.** Builder returns 200 for
  every protocol error. This is the single most likely thing to be missed in
  the port.
- **Modern requires three headers and two `_meta` keys**: `MCP-Protocol-Version`,
  `Mcp-Method`, `Mcp-Name`; `io.modelcontextprotocol/protocolVersion` and
  `io.modelcontextprotocol/clientCapabilities`. Builder reads none of them.
- **Two new error codes**: `-32020` header mismatch or missing, `-32022`
  `UnsupportedProtocolVersionError` with `data: {supported, requested}`.
- **`server/discover` must be rewritten**, not copied. Builder's body is wrong
  in four fields: no `resultType`, no `ttlMs`, no `cacheScope`, and `serverInfo`
  is not in `_meta`.
- **Every modern result carries `resultType`.** `tools/list` also carries
  `ttlMs` and `cacheScope`. Legacy results carry none of them.
- **Legacy keeps `initialize` and `ping`. Modern deletes them.**
- `Mcp-Name` needs no Base64 sentinel decode, because Sketch slugs are
  `[a-z0-9-]`. Record the limit in the spec.
- Ticket 08's `outputSchema` and `structuredContent` work is separate and
  still needed.

## Answer

Done 2026-08-27. `.scratch/sketch-mvp/spec.md`, 1,243 lines, 17 sections.

Assembled from the 16 resolved tickets and the three research reports. Where
two tickets disagree, the spec carries the later one and the superseded text
stays in the ticket for the reasoning. No new decisions were made.

Sections: environment, data model, signup, routing, Runtime, Viewer, `check`,
MCP server, served skill, recipes, Sketch UI, theme, tests, traps, build order,
out of scope, sources.

Three sections carry more than the tickets do, because the spec is what
`/implement` reads:

- **Section 14, Traps.** Eighteen items, each one a "must be built" or a
  "single most likely to be missed" line pulled out of a ticket body. The
  `<` escaping, HTTP 400 from `rpc.handle`, `process.env.NODE_ENV`,
  `desk_access = 0`, the `auth_hooks` path scope, the `Host` header on
  `sketch-checkd`.
- **Section 15, Build order.** Eight steps, each ending in something runnable.
  Steps 3, 4 and 5 are the critical path: `check` needs the Viewer, and the
  Viewer needs the Runtime.
- **Section 13, Tests.** One test exists. Eight to build, named.

### Drift found while assembling

- `sketch/skill/frappe-ui.md:88` still says **"Eight specifiers resolve"** and
  has no `@vueuse/core` row. Ticket 11's amendment made it nine. The spec
  records the edit as work in sections 5.3 and 9.
  `sketch/tests/test_skill_names.py` reads the manifest, so it will pass on its
  own once the Runtime entry lands; only the prose needs the row.
- The built Runtime on this box still has `files.json` and `host.html`. Both
  are prototype-only and the spec says to delete them, along with
  `make-files-json.mjs`.

Neither is a contradiction between tickets. Both are the later ticket's work
not yet applied to the earlier ticket's artifact.

### Verified while writing

- Ticket 15's own "Blocked by" list is accurate: 01, 02, 04, 05, 06, 08, 09,
  10, 11, 12, 13, 14, 16, 17, 18 are `resolved`, 03 is removed, 07 is closed
  out of scope. No open ticket remains.
- The three prototype branches exist and hold what the tickets say:
  `forge/proto/04-runtime-bundle` at `a4a932d`, `forge/proto/10-check-step` at
  `3bec4ec`, `forge/proto/14-sketch-ui` at `4d9536d`.
- The Runtime `manifest.json` on disk lists the ten import-map entries ticket
  11 recorded, minus `@vueuse/core`.

### The map is closed

The destination was a spec `/implement` can execute plus the scaffold to land
it in. Both exist. Nothing is left to decide before the build starts.

Building the MVP is the next effort. It is fed by `spec.md`, not by this map.
