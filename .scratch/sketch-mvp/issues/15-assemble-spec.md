# Assemble the MVP spec

Type: task
Status: open
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
