# The Sketch Runtime

One shared browser bundle per supported frappe-ui version. This folder is the
source. The build output is `sketch/public/runtimes/<version>/`, which is
gitignored and regenerated on deploy.

A Prototype ships no entry file. The Runtime owns the mount: `boot.js` reads
the tree out of the page, compiles it, links it, creates the hash-mode router,
and mounts `src/App.vue` inside `FrappeUIProvider`.

## Build it

```sh
sh build.sh                # -> ../sketch/public/runtimes/1.0.0-beta.55/
node measure.mjs           # payload and timings for the sample Prototype
node test-errors.mjs       # every error class, plus cycles, .css and empty
node test-upload.mjs       # the upload_file stub
```

Needs `../frontend/node_modules` (build.sh symlinks it in as `node_modules`),
an esbuild binary, Playwright at `/tmp/pw-runner/node_modules/playwright` for
the three test scripts, and the bench running on port 8007.

## What is here

| Path | What |
|---|---|
| `vite.runtime.config.js` | Vite lib build: the frappe-ui export subpaths as ESM, vue and vue-router external |
| `runtime-entry/` | One entry per import-map specifier |
| `runtime-entry/compiler.js` | In-browser SFC compiler: `@vue/compiler-sfc` plus sucrase |
| `tailwind/` | The browser Tailwind engine with the frappe-ui preset |
| `internals.css`, `internals.tailwind.config.js` | Layer 1: precompiled frappe-ui CSS |
| `fonts/inter.css` | Inter, roman only |
| `viewer/viewer.html` | The document: stylesheets, import map, the data slot |
| `viewer/boot.js` | Read the tree, compile, link, mount, report |
| `make-manifest.mjs` | `manifest.json`: assets, import map, sizes. The SPA reads it |
| `make-lucide-map.mjs` | All 2,035 lucide icons as data URIs, for the browser preset |
| `sample-prototype/src/` | A hand-written two-page Prototype, used by every script |
| `harness.mjs` | Substitutes the data slot the way the renderer does |

## The data slot

`build.sh` stamps this line into each per-Pin `viewer.html`:

```html
<script id="sketch-data" type="application/json">SKETCH_DATA</script>
```

The renderer replaces the **first** occurrence of `SKETCH_DATA` with the
payload, and nothing else. The placeholder must never appear earlier in the
document. The serialiser escapes `<` as `\u003c`, or the `</script>` in any Vue
file closes the block early.

## Adding an import specifier

Four places, every time: the build entry, `manifest.json`, the `viewer.html`
import map, and `sketch/skill/frappe-ui.md`.
`sketch/tests/test_skill_names.py` catches the drift.

## Two traps that cost time once

- `define: { 'process.env.NODE_ENV': '"production"' }` in the Vite lib build,
  or every Dialog renders as an empty comment node.
- `vue-router.esm-browser.prod.js`, never the dev build. The dev build imports
  `@vue/devtools-api`, which no import map entry covers.
