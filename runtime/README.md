# The Sketch Runtime

One shared browser bundle per supported frappe-ui version. This folder is the
source. The build output is `sketch/public/runtimes/<version>/`, which is
gitignored and regenerated on deploy.

A Prototype ships no entry file. The Runtime owns the mount: `boot.js` reads
the tree out of the page, compiles it, links it, creates the hash-mode router,
and mounts `src/App.vue` inside `FrappeUIProvider`.

## Versions

Each frappe-ui version has its own build inputs in `versions/<version>/`:
a `package.json` and a committed `yarn.lock`. They pin frappe-ui and every
tool the build reads. Each version installs into its own `node_modules`.
The SPA in `../frontend/` has its own dependencies and does not affect a
Runtime.

The source in this folder is shared by every version. A change to it must
build and render on every version in `versions/`.

Do not remove a version while a Prototype pins it. A fresh server rebuilds
every Runtime from `versions/`.

## Build it

```sh
sh build-all.sh            # every version; skips a version that is up to date
sh build.sh 1.0.0          # one version
sh build.sh 1.0.0 --force  # one version, even if up to date
OUT=/tmp/check sh build.sh 1.0.0   # build into another folder
```

`build.sh` writes `.build-stamp` into the output: a hash of the version's
inputs and the shared source. A build with the same stamp is skipped. A
build goes to a staging folder and replaces the old output in one move.
`yarn build` and `bench build` run `build-all.sh`.

## Add a version

```sh
yarn runtime:add           # frappe-ui `latest` from npm
yarn runtime:add 1.0.1     # a given version
```

It copies the newest version's inputs, sets frappe-ui, installs and builds.
The other tools keep the versions the newest lockfile pins. Then:

1. Render every Recipe on the new Runtime. New Prototypes and Recipes use
   the newest Runtime.
2. Read the frappe-ui release notes. Apply any codemods to `../sketch/recipes/`
   and `sample-prototype/`.
3. Commit `versions/<version>/`.

## Test it

```sh
node measure.mjs           # payload and timings for the sample Prototype
node test-errors.mjs       # every error class, plus cycles, .css and empty
node test-upload.mjs       # the upload_file stub
```

The scripts use the newest built Runtime. Set `SKETCH_RUNTIME=<version>` to
use another. They need Playwright at `/tmp/pw-runner/node_modules/playwright`
and the bench running on port 8007.

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
| `versions/<version>/` | The pinned build inputs for one Runtime |
| `versions.mjs` | Version order: a release sorts after its prereleases |
| `build.sh`, `build-all.sh`, `add.sh` | Build one version, build all, add a version |
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
