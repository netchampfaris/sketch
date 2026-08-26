# Build the browser Runtime for frappe-ui 1.0.0-beta

Type: prototype
Status: open
Blocked by: 05, 06

## Question

Prototype one Runtime: a Vite library build that exposes vue, vue-router, frappe-ui@1.0.0-beta.<latest>, and the compiled frappe-ui CSS as ESM assets served from the sketch app's public folder, plus an import map so prototype code can `import { Button } from 'frappe-ui'`. Prove it by rendering a hand-written 2-page prototype with Sidebar, ListView, Dialog and a form. Measure bundle size and first-render time. Decide the Runtime directory layout: one folder per frappe-ui version.
