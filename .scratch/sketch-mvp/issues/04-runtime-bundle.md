# Build the browser Runtime for frappe-ui 1.0.0-beta

Type: prototype
Status: open
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
