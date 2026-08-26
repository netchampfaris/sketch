# Prototype the check step: compile, render, screenshot

Type: prototype
Status: resolved
Blocked by: 04 (resolved — unblocked)

## Question

Prototype a worker path that takes a prototype id, compiles every file server-side with the same compiler the Runtime uses, then opens the viewer URL in headless Chrome (Playwright chromium already in ~/.cache/ms-playwright), captures console errors and one screenshot per route, and returns them as MCP content. Must not run inside a Frappe web worker request. Decide: RQ job plus polling, or a separate Node service. Measure latency.

## Comments

### 2026-08-26 — from ticket 08

- `check({ prototype, screenshot })`. Screenshots are opt-in, one image per
  route. Errors are always returned as text.
- The MCP transport is stateless POST-only with no SSE, so `check` **cannot
  stream progress**. Either it returns fast enough for a synchronous
  JSON-RPC reply, or it becomes a job plus a separate poll tool. Decide
  which, and measure against the latency numbers this ticket asks for.
- Return compile errors as `file:line:col message`. The compiler is
  `@vue/compiler-sfc` + `sucrase` (ticket 05); check `parse().errors` first,
  or template errors report at generated-code positions.
- Use `structuredContent` for the error lists, not a text blob.

### 2026-08-26 — from ticket 04

The Viewer already reports what `check` needs. `boot.js` posts
`{ status, errors, consoleErrors, timings, tailwind }` to `parent` and sets
`window.__sketch`. Four error classes are verified with file and line:
SFC parse errors, TS syntax errors, unresolvable relative imports, and Vue
runtime errors. Build `check` on this rather than inventing a channel.

Two things this ticket must decide:

- **Prod builds emit no Vue and no reka-ui warnings.** The Runtime ships
  `vue.runtime.esm-browser.prod.js` and defines
  `process.env.NODE_ENV = "production"`, which is what makes reka-ui work at
  all. Dev builds would give warnings for `check` at the cost of a
  `@vue/devtools-api` shim and a second asset set per Pin.
- The screenshot. Ticket 04 took screenshots with Playwright against the
  live site and they are faithful. Decide where that browser runs.

Import cycles between Prototype files are not supported and report as a
`cycle` error. Decide whether `check` should say so plainly.

## Answer

Resolved 2026-08-27. `check` is a **synchronous MCP tool call**. The Frappe
handler proxies to a small Node service that drives headless Chromium. There
is no server-side compile and no poll tool.

Prototype branch: `forge/proto/10-check-step`, folder `check-prototype/`.
Evidence: `check-prototype/measurements*.json` and `shot-*.png`.

### The path

```
agent -> POST /mcp check(prototype, screenshot)
      -> Frappe web worker: HTTP POST 127.0.0.1:8010
      -> sketch-checkd (Node, one Chromium): open the Viewer, read
         window.__sketch, walk the routes, screenshot each
      -> back up the same wire, in one JSON-RPC reply
```

The web worker never runs a browser. It blocks on one local HTTP call.

### No server-side compile

The ticket asked for one. It is not needed and would be wrong. The Viewer
already compiles, links, mounts and reports (ticket 04). A second compiler on
the server is a second source of truth that can disagree with what the user
sees. `check` opens the Viewer URL and reads `window.__sketch`.

### Latency, measured

Headless Chromium against the live bench on 8007. Median of 5, or of 3 for
the slower cases. Sample Prototype: 7 files, 2 routes.

| Case | ms |
|---|---|
| End to end through Frappe, with screenshots | **913** |
| Node service, with screenshots | 951 |
| Node service, no screenshots | 813 |
| One process per check (no daemon) | 1299 |
| Compile error: fails before mount | 210 |
| Import cycle: fails before mount | 227 |
| Runtime throw on a walked route | 825 |
| 30 files, 12 routes, with screenshots | 2578 |

Inside one run: 25 ms for the browser context, 570 ms to load and report
(the Viewer's own boot is 435 ms of that, and Tailwind is 300 ms of *that*),
then 160 ms per route with a screenshot, 80 ms without.

### A service, not a job, not a subprocess

- **Synchronous beats RQ plus a poll tool.** 0.9 s is inside one tool call.
  A job plus a poll costs an extra agent round trip — slower than the check
  itself — and a 12th tool. Ticket 08's `check(prototype, screenshot)` stands.
- **A daemon beats one process per check**, by 350 ms. The gap is Node boot
  and the Playwright import, *not* the browser: Chromium launches in 45 ms,
  so keeping it warm is worth 40 ms. One process per check is the fallback if
  a second daemon is unwanted; it costs 350 ms and one Chromium per
  concurrent check.
- One browser, one fresh context per check. 1, 2, 4 and 8 concurrent checks
  all pass; 8 at once degrades to 3.1 s each. About 250 MB resident idle.
  Cap concurrency and queue past it.
- `sketch-checkd` needs a systemd user unit next to `sketch-bench.service`.

### Screenshots

Opt-in, one PNG per route, 1280x800. 28-35 KB each, 37-47 KB as base64.
JPEG q70 saves about 20% and is not worth the loss for a design tool. Keep
PNG. Twelve routes came to 222 KB.

The walk drives the router through `window.__sketchGoto(path)`, never through
the DOM. Routes with a param (`/issue/:id`) cannot be visited blind and are
reported as skipped, with the reason.

Cap the walk at 20 routes and hard-timeout the check at 30 s. Say plainly
what was skipped; a silent cap reads as "everything is fine".

### Keep the production Runtime. No dev asset set.

Verified as caught by the production build: SFC parse errors, TS syntax
errors, unresolvable relative imports, import cycles, a bad named import from
`frappe-ui` (`boot-failed`, "does not provide an export named 'Buton'"), and
Vue runtime errors.

Verified as silently dropped: "Failed to resolve component" and prop type
warnings.

The first of those is recoverable without a dev build. The template compiler
emits `_resolveComponent("Badgee")` for every tag it could not bind to an
import. Scan the generated code for those names, then filter them against
`app._context.components` after the plugins install, plus `RouterView` and
`RouterLink`. Verified: zero false positives on the sample tree, and the typo
is caught. It is now a `warnings` array on the report.

Prop type warnings stay lost. They do not justify a second asset set per Pin
and a `@vue/devtools-api` shim.

### Import cycles: say so plainly

Already handled. Status `link-failed`, one error:
`Import cycle: src/router.ts -> src/a.ts -> src/b.ts -> src/a.ts`. `check`
passes it through unchanged.

### Return shape

`structuredContent`, per ticket 08:

```json
{ "status": "ok | errors | compile-failed | link-failed | boot-failed",
  "errors": [{ "kind": "compile", "file": "src/pages/About.vue",
               "line": 3, "column": 5, "message": "Element is missing end tag." }],
  "warnings": [{ "kind": "unresolved-component", "file": "...", "message": "..." }],
  "routes": ["/", "/about"],
  "timings": { "compileMs": 55, "mountMs": 55, "tailwindMs": 302 } }
```

Plus one image content block per route when `screenshot` is set. Render
errors as `file:line:col message`.

### Three Runtime defects this prototype found

1. **Status was fixed at mount.** A route reached during the walk could throw
   and the report still read `ok`. `check` recomputes status after the walk.
   Verified: the throw case now reports `errors`.
2. **A template-only SFC did not compile.** `<template>` with no `<script>`
   threw "[@vue/compiler-sfc] SFC contains no `<script>` tags", because
   `compileScript` needs a script block. Fixed with `compileTemplate` when the
   descriptor has neither `script` nor `scriptSetup`. This amends ticket 04's
   recipe; it does not reopen it.
3. **The Viewer could not enumerate or drive its routes.** `boot.js` now
   reports `routes` from `router.getRoutes()` and exposes
   `window.__sketchGoto(path)`.

### Left open

The checker opens the Viewer URL as an anonymous browser. Every Prototype in
this prototype is a `files.json` on disk. In the MVP the Viewer must read the
owner's files through an API, and headless Chromium must authenticate as the
owner to open a private Prototype. New ticket 17.
