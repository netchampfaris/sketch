# Build the browser Runtime for frappe-ui 1.0.0-beta

Type: prototype
Status: resolved
Blocked by: 05, 06 (both resolved — unblocked)

## Question

Prototype one Runtime: a Vite library build that exposes vue, vue-router, frappe-ui@1.0.0-beta.<latest>, and the compiled frappe-ui CSS as ESM assets served from the sketch app's public folder, plus an import map so prototype code can `import { Button } from 'frappe-ui'`. Prove it by rendering a hand-written 2-page prototype with Sidebar, ListView, Dialog and a form. Measure bundle size and first-render time. Decide the Runtime directory layout: one folder per frappe-ui version.

## Comments

### 2026-08-26 — decisions from the grilling session

- **A Prototype renders in a same-origin iframe** (the Viewer). Its own
  document, its own global `fetch`, its own stylesheet, its own
  `window.onerror`. Sketch chrome stays outside it. Chosen over rendering in
  the SPA window: patching `fetch` there would break Sketch's own API calls,
  prototype Tailwind would collide with Sketch's stylesheet, and a prototype
  crash could take the SPA down. A separate origin was offered and not taken.
- Open, not decided here: same-origin means Prototype code can reach
  `parent` and Sketch's cookies. Signup is open to anyone. Revisit whether
  the iframe needs `sandbox="allow-scripts"` without `allow-same-origin`.
- **Stub `/api/method/upload_file` inside the Viewer.** From ticket 07: it is
  the only endpoint any frappe-ui component calls on its own. `FileUploader`,
  the editor's `media-upload-engine.ts`, and the TextEditor paste extension
  all hit it. Without a stub they throw. Nothing else needs stubbing.
- Ticket 05 is resolved, so this ticket is unblocked. Compiler is
  `@vue/compiler-sfc` (esm-browser) + `sucrase`.

### 2026-08-26 — from ticket 12

The Runtime directory layout is already decided, so this ticket implements
it rather than choosing it: `sketch/public/runtimes/<version>/` with a
`manifest.json`, one folder per frappe-ui version. There is **no** Sketch
Runtime doctype; `pin` is a plain `Data` field holding the version string.

Say so if the prototype finds a reason the layout cannot work. That reopens
ticket 12, it does not override it quietly.

The hand-written 2-page prototype should use the real tree: `src/pages`,
`src/components`, `src/App.vue`, `src/router.ts`.

## Answer

Resolved 2026-08-26. The Runtime works. Built, rendered, and measured in
headless Chromium against the live bench on port 8007.

Prototype branch: `forge/proto/04-runtime-bundle`, folder `runtime-prototype/`.
Evidence: `runtime-prototype/measurements.json` and the three screenshots.

### It renders

A hand-written 2-page Prototype (`src/App.vue`, `src/router.ts`,
`src/pages/*`, `src/components/*`) renders at full fidelity in the Viewer
iframe with `DesktopShell`, `Sidebar`, the `frappe-ui/list` family, `Dialog`,
`FormControl`, and `Badge`.

Verified in one run, zero compile errors and zero console errors:

- Both routes render. The hash router navigates between them.
- The Dialog opens, the form validates an empty title, and Create adds a row.
  The list goes from 4 rows to 5.
- `FileUploader` resolves through the stub. The success handler fires.
- `h-[13px]` and `bg-blue-500/30` on the second page, never in the DOM at
  first paint, get styles. Computed: 13px and `oklch(... / 0.3)`.

### Layout: one folder per version, as ticket 12 decided

`sketch/public/runtimes/<version>/`, served at
`/assets/sketch/runtimes/<version>/` through Frappe's existing `assets`
symlink. Nothing had to change to serve it. Ticket 12 stands.

`manifest.json` names the assets, the import map, and the stylesheets, and
records every asset's raw and gzip size. The SPA reads it to build the
Viewer, so no filename is hard-coded.

```
frappe-ui.js  frappe-ui-list.js  Tooltip-<hash>.js   # Vite lib build
vue.js  vue-router.js                                # esm-browser.prod, copied
frappe-ui.css  frappe-ui-components.css              # layer 1 + SFC styles
Inter.var.woff2  Inter-Italic.var.woff2
compiler.js  tailwind.js                             # the two compilers
viewer.html  boot.js  host.html  manifest.json
```

### The import map

Static, in `viewer.html`, so `import { Button } from 'frappe-ui'` works
unchanged in Prototype code:

```json
{ "vue": "…/vue.js", "vue-router": "…/vue-router.js",
  "frappe-ui": "…/frappe-ui.js", "frappe-ui/list": "…/frappe-ui-list.js",
  "sketch:compiler": "…/compiler.js", "sketch:tailwind": "…/tailwind.js" }
```

vue and vue-router are external to the frappe-ui build, so the Prototype,
frappe-ui, and vue-router all share one Vue instance.

**Each frappe-ui export subpath needs its own asset.** `frappe-ui/list` is not
in the root barrel (`ListView` moved to `frappe-ui/experimental` in #985).
`frappe-ui/editor`, `frappe-ui/charts`, and `frappe-ui/icons` will each need
an entry too. Vite shares the common code as one chunk. Ticket 11 must list
the subpaths the skill is allowed to name.

### Cost

Runtime assets, gzip, measured from `manifest.json`:

| Group | gzip |
|---|---|
| Render (vue, vue-router, frappe-ui, both CSS layers, viewer, boot) | 313 KB |
| Compilers (`compiler.js` 296 KB, `tailwind.js` 147 KB) | 443 KB |
| Inter fonts (already compressed) | 559 KB |
| **Total** | **1.31 MB** |

All of it is static, cacheable, and shared by every Prototype on the same
Pin. `compiler.js` matches ticket 05's 295 KB. `tailwind.js` matches ticket
06's 145 KB. `frappe-ui.css` is 46 KB, matching ticket 06's B2.

First render, headless Chromium on this VM, warm server, five files:

| Step | ms |
|---|---|
| Compile 7 files (5 SFC, 2 TS) | 50 |
| Link and mount | 55 |
| Tailwind first compile (116 classes) | 286 |
| Boot to painted | 398 |
| Navigation to load, `window.__check` set | 549 |

A later batch of 12 new classes compiles in 112-126 ms.

**The Tailwind engine is 72% of first render.** It is also the only step that
scales with the Prototype. Layer 1 means the page is already styled while it
runs, so this is time-to-final-paint, not time-to-first-paint.

### Facts the ticket had wrong

- **`upload_file` goes over XMLHttpRequest, not `fetch`.** Both call sites
  (`src/utils/fileUploadHandler.ts:134`, `src/utils/useFileUpload.ts:257`)
  open an XHR for upload progress. The comment above says "its own global
  `fetch`"; a `fetch` patch would have stubbed nothing. The Viewer subclasses
  `XMLHttpRequest` and returns a data-URL File doc.

### Two build traps, both cost real time

- **`process.env.NODE_ENV` must be defined in the Vite lib build.** Vite does
  not substitute it in lib mode. reka-ui guards its dev warnings with it, so
  `process` was undefined in the browser, `DialogContentImpl` threw inside
  `setup()`, and every Dialog rendered as an empty comment node with only a
  "Component is missing template or render function" warning to go on.
  Fix: `define: { 'process.env.NODE_ENV': '"production"' }`.
- **Use `vue-router.esm-browser.prod.js`.** The dev build imports
  `@vue/devtools-api`, which no import map entry covers, and the module fails
  to resolve.

### The Viewer owns the mount

A Prototype ships no entry file. `boot.js` imports `src/App.vue` and the
routes from `src/router.ts`, creates the hash-mode router, and calls
`createApp(App).use(router).use(FrappeUI)`. So `src/router.ts` exports a
routes array, not a router. Ticket 11's skill must say this.

Linking: compile every file, resolve relative specifiers (`.ts`, `.js`,
`.vue`, `/index.*`), topologically sort, then create one blob URL per module
leaf-first and rewrite each import to the blob it points at. Bare specifiers
are left for the import map. **Import cycles are not supported** and report
as a `cycle` error.

### Errors surface with file and line

Four classes, all verified (`runtime-prototype/test-errors.mjs`):

| Case | Status | Reported |
|---|---|---|
| Missing end tag in a template | `compile-failed` | `About.vue` 3:5 "Element is missing end tag." |
| TS syntax error in a `.ts` file | `compile-failed` | `data.ts` 1:33 "Unexpected token" |
| Import of a file that does not exist | `link-failed` | `router.ts` "Cannot resolve ./pages/Missing.vue" |
| `null.boom()` in `<script setup>` | `errors` | Vue error handler, with the error-reference link |

The Viewer posts `{ status, errors, consoleErrors, timings, tailwind }` to
`parent` and sets `window.__sketch`. Ticket 10 builds `check` on this.

### Open, for ticket 10

- **Prod builds mean no Vue and no reka-ui warnings.** `check` may want dev
  builds. That costs a `@vue/devtools-api` shim and a second asset set per
  Pin. Ticket 10 decides.
- The Inter faces are 559 KB gzip, 43% of the total, and the italic face is
  half of that. Decide whether a Prototype needs italic.
- Not measured: Firefox, Safari, cold cache, a Prototype with 50 files.

### 2026-08-27 — amendment: sizes superseded, three defects fixed

From ticket 11, which folded Runtime work in rather than opening a ticket.
Committed on this branch at `a4a932d`.

Three defects in what this ticket delivered:

- **`shims/iconPackBrowser.js` was never wired in**, and the
  `tailwind/lucide-map.json` it imports did not exist. `preset-browser.js`
  dropped the icon plugin and said so in a comment. Only the 201 icon classes
  baked into the precompiled `frappe-ui.css` resolved. An unknown name drew an
  empty box, and `check` reported `ok`.
- **`FrappeUIProvider` was not mounted.** `dialog.confirm()` and
  `toast.success()` did nothing and reported no error.
- **The import map was hand-written in `viewer.html`** and did not match
  `make-manifest.mjs`. Both now list the same specifiers.

The Runtime now resolves eight specifiers, not four: `frappe-ui/editor`,
`frappe-ui/charts`, `frappe-ui/icons` and `dayjs` are added, and Rollup splits
the shared chunks so `Button`, `Tooltip`, `useId`, `dayjs` and
`useColorScheme` exist once across the entries. The editor and charts download
only when a Prototype imports them.

Measured numbers above are superseded:

| | this ticket | after ticket 11 |
|---|---|---|
| eager render payload | 313 KB gzip | 320 KB gzip |
| the two compilers | 443 KB gzip | 543 KB gzip |
| plain boot to painted | 398 ms | 426 ms |

The Inter font question this ticket handed over is still open.

### 2026-08-27 — amendment: the Viewer reads the DOM, and four Runtime changes

From ticket 17. The `files.json` this ticket fetched is gone.

- **`boot.js` reads the source tree from the DOM**, not `fetch('./files.json')`.
  The renderer puts it in a `<script id="sketch-data" type="application/json">`
  slot with `name`, `title`, `pin`, `is_public`, owner-or-not, and the theme.
- **`build.sh` gains a second placeholder.** Step 5 already stamps a per-Pin
  `viewer.html` with `sed "s#RUNTIME#$BASE#g"`. It now stamps the empty data
  slot too. The renderer substitutes it per request.
- **The blob-URL linker becomes a module registry.** Import cycles work. The
  `cycle` error this ticket introduced goes away, and so does ticket 10's
  cycle case.
- **`.css` imports are injected as a stylesheet.** Today `import './style.css'`
  resolves to a blob that does not exist and the import rewrites to
  `undefined`.
- **A precondition check on `src/App.vue`**, and a new status **`empty`** for a
  Prototype with no files. Today a missing `App.vue` becomes `import(undefined)`
  and the agent gets a message about `undefined`, not about the file.

Unchanged on purpose: the Runtime still owns the mount. A Prototype that owns
`createApp` can skip `FrappeUIProvider`, skip the error handler, or never call
`mount`, and then `check` reports nothing useful.

**The Inter italic question is closed: drop it.** 297 KB gzip, half the font
payload, to render text almost no Prototype sets in italic. Adding it back is
one file and one line in `inter.css`.

**Nine specifiers, not eight.** `@vueuse/core` is added; see the ticket 11
amendment.
