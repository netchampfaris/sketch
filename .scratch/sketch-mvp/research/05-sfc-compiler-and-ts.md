# In-browser SFC compiler and TypeScript stripper

Ticket: `issues/05-sfc-compiler-and-ts.md`. Date: 2026-08-26.
Work split: a subagent fetched the npm, GitHub and docs facts. Another subagent fetched the import map and module resolution facts. The main agent ran the local measurements and tests in `/tmp/sfc-bench`.

## Recommendation

Use a hand-rolled pipeline: `@vue/compiler-sfc` (esm-browser build) plus `sucrase` for type stripping. This is the same pair that Vue's own SFC playground (`@vue/repl`) uses [R1].

Do not use `vue3-sfc-loader`. Do not use `esbuild-wasm`.

Reasons, in order of weight:

- `vue3-sfc-loader` is unmaintained. Last release 0.9.5 on 2024-02-06, last commit 2024-09-27 [L1][L2]. It pins compiler-sfc 3.4.15 inside its bundle [L3]. frappe-ui 1.0.0-beta.36 requires `vue >= 3.5.0` [G1]. The compiler and runtime would be from different minor versions.
- `vue3-sfc-loader` crashes on TypeScript syntax in template expressions (`{{ (count as number) + 1 }}`). Verified locally, see T4.
- `vue3-sfc-loader` swallows SFC parse errors (missing end tag). The component loads with a broken template. Only the `log` callback sees the error. Verified locally, see T4. Open upstream issue #225 [L4].
- `esbuild-wasm` costs a 13.3 MiB wasm download (3.7 MB gzip) [E1] and a worker init. It is 4.7x slower per SFC than sucrase in the local benchmark (T6). Its only advantage is structured error locations, which sucrase also gives (`err.loc.line`, `err.loc.column`) (T3).
- The hand-rolled bundle is the smallest option: 295 KB gzip for compiler-sfc plus sucrase, against 500 KB gzip for `vue3-sfc-loader` (T1).

Costs of the hand-rolled choice:

- Sketch must own about 100 lines of glue: parse, compileScript, compileStyleAsync, TS strip, import rewrite, style injection. `@vue/repl` `src/transform.ts` is a working reference for this glue [R1].
- Sucrase silently drops TS `namespace` blocks and does not typecheck (T5) [S4]. Acceptable: Sketch does type stripping only.

## Bundle size (T1)

Measured with `npm install` of latest versions in `/tmp/sfc-bench` and `gzip -9`. `esbuild --bundle --minify --format=esm` for the bundled rows. Brotli was not installed on this machine, so no brotli column.

| Option | File(s) | Raw | Gzip |
|---|---|---|---|
| vue3-sfc-loader 0.9.5 | `dist/vue3-sfc-loader.esm.js` (already minified) | 1,837,034 | 499,537 |
| @vue/compiler-sfc 3.5.41 | `dist/compiler-sfc.esm-browser.js` (unminified, ships with postcss) | 1,726,212 | 383,782 |
| @vue/compiler-sfc 3.5.41 | same, minified by esbuild | 800,240 | 247,644 |
| sucrase 3.35.1 | `transform` only, bundled and minified | 206,023 | 47,051 |
| compiler-sfc + sucrase | one bundle, minified | 1,007,913 | 295,119 |
| esbuild-wasm 0.28.2 | `esm/browser.min.js` | 52,913 | 15,013 |
| esbuild-wasm 0.28.2 | `esbuild.wasm` | 13,978,850 | 3,723,844 |
| compiler-sfc + esbuild-wasm | JS 800 KB + 53 KB, plus wasm | 14.8 MB | 3.99 MB |

Reference: `vue.esm-browser.prod.js` 3.5.41 is 171,457 raw and 62,338 gzip. The compiler is 4x the runtime in every option.

The `vue3-sfc-loader` README badges say min+gzip 488 kB [L5]. The measured file is 499.5 kB. Its browserslist is `> 1%, last 8 versions, Firefox ESR and not dead` [L6], so its bundle carries transpile helpers a 2026 evergreen browser does not need.

## Scoped CSS

| Option | `<style scoped>` | How |
|---|---|---|
| vue3-sfc-loader | Yes | Computes `data-v-<hash(filename)>`, sets `__scopeId`, calls `compileStyleAsync` with `scoped`, calls your `addStyle(css, scopeId)` [L7]. Verified in T4: output `.box[data-v-ee7e...] { color: red }`. |
| hand-rolled | Yes | `compileStyleAsync({ source, filename, id, scoped: true })` returns `{ code, errors }` [V1]. Verified in T2: `.box[data-v-abc123] { color: red }`. Caller must pick the `id`, pass the same `id` to `compileScript`, and inject the CSS into a `<style>` tag. |

## TypeScript type stripping

| Option | `<script setup lang="ts">` | TS in template expressions | plain `.ts` modules |
|---|---|---|---|
| vue3-sfc-loader | Yes. Babel `@babel/plugin-transform-typescript` when `lang === 'ts'` [L8]. | No. Crashes with `Unexpected token, expected ","` on `{{ (count as number) + 1 }}` (T4). | Yes. Type `.ts` is handled by the same Babel path (T4). |
| compiler-sfc + sucrase | Yes. `compileScript` with `inlineTemplate: true` returns code that still contains TS (`setup(__props: any)`, `ref<number>(0)`) [V2]. One `sucrase.transform(code, { transforms: ['typescript'] })` strips it (T2). | Yes. Inline template mode passes `isTS` to the template compiler, so `as` casts survive into the render code and the same sucrase pass strips them (T2). | Yes. Same sucrase call (T5). |
| compiler-sfc + esbuild-wasm | Yes. `esbuild.transform(code, { loader: 'ts' })` (T2). | Yes (T2). | Yes (T5). |

compiler-sfc does not strip TS itself. The source says the user's TS setting should compile the output down [V2]. `@vue/repl` runs sucrase on the compileScript output and on `.ts` files when `lang` is `ts` [R1].

TS feature coverage of the two strippers (T5, `transforms: ['typescript'], disableESTransforms: true` for sucrase):

| Feature | sucrase | esbuild |
|---|---|---|
| `satisfies`, generics, `import type`, `export type`, non-null `!`, overloads, param properties, template literal types | strips | strips |
| `enum` | emits IIFE | emits IIFE |
| `const enum` | treated as `enum` (README says so [S4]) | inlines the value |
| `export namespace NS {}` | dropped silently, output is empty | emits IIFE |
| `abstract class` with fields | strips `abstract`, keeps class fields | same |
| decorators | left as-is | left as-is |

Sucrase without `disableESTransforms: true` also rewrites class fields to `__init` helpers and optional chaining to an `_optionalChain` helper (T5). Set `disableESTransforms: true` for evergreen browsers.

## Error message quality

All three give file, line and column for script syntax errors. The difference is in template errors.

| Case | vue3-sfc-loader | compiler-sfc + sucrase | compiler-sfc + esbuild-wasm |
|---|---|---|---|
| Missing end tag in template | Loads without throwing. Only `log('error', 'SFC template', '<code frame string>')` sees it (T4) [L4]. | `parse().errors[0]`: `{ message: 'Element is missing end tag.', code: 24, loc.start: { line: 6, column: 5, offset: 70 } }` (T3). | same |
| TS syntax error in `<script setup>` | Throws Babel `SyntaxError` with a code frame. Message `[vue/compiler-sfc] Unexpected token (4:0)` plus `Bad2.vue` and frame. `err.loc = { line: 4, column: 0, index: 46 }` (T4). | Same object, from `compileScript` (T3). Line numbers are SFC lines. | same |
| Bad expression `{{ a + }}` | Throws from the Babel pass over the generated render code: `Unexpected token (4:77)`. Line 4 col 77 is in generated code, not in the SFC. The `log` callback has the source-mapped frame (T4). | `parse().errors[0]`: `Error parsing JavaScript expression: Unexpected token (1:4)`, `loc.start: { line: 5, column: 9 }`. SFC line (T3). See caveat below. | same |
| Syntax error in `.ts` module | Throws Babel `SyntaxError`, `loc { line: 3, column: 0 }`, plus a `log` code frame with file name (T4). | `SyntaxError: Error transforming util.ts: Unexpected token (3:0)` with `err.loc = { line: 3, column: 0 }`, `err.pos` (T3) [S3]. | `TransformFailure` with `errors[0].location = { file: 'util.ts', line: 3, column: 0, lineText: '}', length: 1 }`. Message `util.ts:3:0: ERROR: Unexpected "}"` (T3) [E2]. |

Caveat for the hand-rolled path (verified in T3): template expression errors are reported by `parse()`, in `descriptor.errors`. `compileScript({ inlineTemplate: true })` then reuses the parsed AST and does not throw. It emits invalid JS (`_toDisplayString(a +)`), and the failure surfaces later as a sucrase error in generated code. Rule: check `parse().errors` first and stop on any error. Then compileScript errors are real SFC positions.

Sucrase error locations for arrow function parameter types can point at the wrong column. Example: an unclosed call on line 2 was reported at `1:31` (T3). This only matters for errors in `.ts` modules, where the parse fails after backtracking. compileScript errors (Babel) do not have this issue.

esbuild has the richest error object (`file`, `line`, `column`, `length`, `lineText`) [E2]. sucrase gives `loc.line`, `loc.column`, `pos`, and the file name in the message when `filePath` is set [S3]. Both are enough for a "file:line:col message" surface.

## Maintenance status

| Package | Latest | Published | Repo activity | Open issues |
|---|---|---|---|---|
| vue3-sfc-loader | 0.9.5 | 2024-02-06 [L1] | last push 2024-09-27, 1,354 stars [L2] | 15 issues, 1 PR [L2]. Includes #225 parse errors ignored (2026-03), #220 TS parser plugin error (2025-04), #216 `</script>` string in script (2025-03) [L4][L9] |
| @vue/compiler-sfc | 3.5.41 | 2026-08-05 [V3] | 3.6.0-rc.5 on 2026-08-21 [V3] | part of vuejs/core |
| sucrase | 3.35.1 | 2025-11-19 [S1] | last push 2025-11-19, previous commit 2023-12-22, 5,870 stars [S2] | 69 issues [S2] |
| esbuild-wasm | 0.28.2 | 2026-08-08 [E3] | active, evanw/esbuild | not counted |

Sucrase is in maintenance mode (one release in two years) but it still ships, and Vue's playground depends on `sucrase ^3.35.0` [R2]. Its scope (strip syntax, no typecheck) is stable. If it goes stale, `esbuild-wasm` is a drop-in replacement for the strip step with the same call shape.

## Compile speed (T6)

Node 24, one warm-up run, average of 39 SFCs of about 15 lines each. Same SFC for all options. This is a relative signal only; browser numbers will differ.

| Pipeline | ms per SFC |
|---|---|
| compiler-sfc only (parse + compileScript inline + compileStyleAsync) | 5.8 |
| compiler-sfc + sucrase | 2.8 (total, cache-warm) |
| compiler-sfc + esbuild-wasm transform | 13.4 |
| vue3-sfc-loader (full loadModule) | 12.8 |

The esbuild transform crosses into wasm per call. esbuild's own docs say the wasm build is much slower than native [E4].

## Import resolution

See the section "Import resolution details" below for sources and the recommended design.

## How vue3-sfc-loader compiles (for the record)

- Calls `compileScript` with `inlineTemplate: false`, then runs Babel with `plugin-transform-modules-commonjs` on the script and on the render function separately. Every module becomes CommonJS and runs through a custom `require` [L8][L10].
- Compiles in production mode. `defineProps<{ items: Item[] }>()` came out as `props: { items: {} }` (T4). Runtime prop type checks are lost.
- Bare specifiers (`vue`, `frappe-ui`) must be present in `moduleCache`, else `require("frappe-ui") failed. module not found in moduleCache` [L10]. Relative paths go through `pathResolve` and `getFile` [L11].

## Local tests

All scripts are in `/tmp/sfc-bench/t/`. Packages: vue3-sfc-loader 0.9.5, esbuild-wasm 0.28.2, sucrase 3.35.1, @vue/compiler-sfc 3.5.41, vue 3.5.41, esbuild 0.28.2 (for bundling only).

- T1 size: `gzip -9c file | wc -c`, and `esbuild src.js --bundle --format=esm --minify --platform=browser`.
- T2 `hand.mjs`: parse, compileScript inline, sucrase strip, esbuild strip, compileStyleAsync scoped on one SFC with `lang="ts"`, `defineProps<T>()`, an `as` cast in the template, imports from `vue`, `frappe-ui`, `./util.ts`.
- T3 `errors.mjs`, `errors2.mjs`, `bad3.mjs`: error shapes for the hand-rolled path.
- T4 `loader.mjs`, `loader-esm.mjs`, `loader-dump.mjs`: vue3-sfc-loader (browser ESM build, run in Node) on the same SFC and on four broken inputs, plus a dump of its compiled cache.
- T5 `tsfeat.mjs`, `sucrase2.mjs`: 16 TS syntax cases through sucrase and esbuild.
- T6 `bench.mjs`: timing.

Not verified: browser wall-clock for esbuild-wasm `initialize()`; brotli sizes; behaviour on Safari.

## Sources

Vue:
- [V1] compileStyle options and return: https://github.com/vuejs/core/blob/main/packages/compiler-sfc/src/compileStyle.ts
- [V2] compileScript keeps TS in output, comment at lines 1042-1047: https://github.com/vuejs/core/blob/main/packages/compiler-sfc/src/compileScript.ts . TS parser plugins: https://github.com/vuejs/core/blob/main/packages/compiler-sfc/src/script/context.ts
- [V3] npm registry: https://registry.npmjs.org/@vue/compiler-sfc
- [V4] README, workflow parse / compileScript / compileTemplate / compileStyle: https://github.com/vuejs/core/blob/main/packages/compiler-sfc/README.md (local copy: `/home/faris/benches/frappe-bench/apps/gameplan/frontend/node_modules/@vue/compiler-sfc/README.md`)
- [V5] Error types: https://github.com/vuejs/core/blob/main/packages/compiler-core/src/errors.ts , https://github.com/vuejs/core/blob/main/packages/compiler-core/src/ast.ts

@vue/repl:
- [R1] transform.ts, sucrase on script and `.ts` files: https://github.com/vuejs/repl/blob/main/src/transform.ts
- [R2] package.json devDependencies: https://github.com/vuejs/repl/blob/main/package.json

vue3-sfc-loader:
- [L1] npm registry, `time["0.9.5"]`: https://registry.npmjs.org/vue3-sfc-loader
- [L2] GitHub API: https://api.github.com/repos/FranckFreiburger/vue3-sfc-loader and issue search `is:issue is:open`
- [L3] package.json pins `@vue/compiler-sfc ^3.4.15`; dist contains `version="3.4.15"`: https://cdn.jsdelivr.net/npm/vue3-sfc-loader@0.9.5/package.json
- [L4] Issue #225 parse errors ignored: https://github.com/FranckFreiburger/vue3-sfc-loader/issues/225
- [L5] README size badges: https://github.com/FranckFreiburger/vue3-sfc-loader/blob/main/README.md
- [L6] browserslist in package.json (local copy `/tmp/sfc-bench/node_modules/vue3-sfc-loader/package.json`)
- [L7] scoped style handling: https://github.com/FranckFreiburger/vue3-sfc-loader/blob/main/src/createVue3SFCModule.ts lines 96-119, 274-300
- [L8] TS via Babel, `inlineTemplate: false`: same file lines 164-186
- [L9] Issues #220, #216: https://github.com/FranckFreiburger/vue3-sfc-loader/issues/220 , https://github.com/FranckFreiburger/vue3-sfc-loader/issues/216
- [L10] CommonJS require and moduleCache lookup: https://github.com/FranckFreiburger/vue3-sfc-loader/blob/main/src/tools.ts lines 327-352
- [L11] pathResolve, getResource, options: https://github.com/FranckFreiburger/vue3-sfc-loader/blob/main/docs/api/README.md , https://github.com/FranckFreiburger/vue3-sfc-loader/blob/main/src/index.ts lines 65-110

sucrase:
- [S1] npm registry: https://registry.npmjs.org/sucrase
- [S2] GitHub API: https://api.github.com/repos/alangpierce/sucrase
- [S3] Error format: https://github.com/alangpierce/sucrase/blob/main/src/parser/traverser/util.ts lines 94-104 , https://github.com/alangpierce/sucrase/blob/main/src/index.ts lines 64-67
- [S4] README "What Sucrase is not", transforms list: https://github.com/alangpierce/sucrase/blob/main/README.md

esbuild:
- [E1] wasm size, registry unpacked size: https://registry.npmjs.org/esbuild-wasm/0.28.2 ; local file `/tmp/sfc-bench/node_modules/esbuild-wasm/esbuild.wasm`
- [E2] Message and Location types: https://github.com/evanw/esbuild/blob/main/lib/shared/types.ts lines 186-215, 285-298 ; https://esbuild.github.io/api/#transform
- [E3] npm registry: https://registry.npmjs.org/esbuild-wasm
- [E4] Browser usage, `initialize({ wasmURL })`, worker: https://esbuild.github.io/api/#browser ; TS caveats: https://esbuild.github.io/content-types/#typescript-caveats

Gameplan:
- [G1] frappe-ui 1.0.0-beta.36 `peerDependencies.vue: ">=3.5.0"`: `/home/faris/benches/frappe-bench/apps/gameplan/frontend/node_modules/frappe-ui/package.json`
