# Pick the in-browser SFC compiler and TypeScript stripper

Type: research
Status: resolved
Blocked by: 

## Question

Compare vue3-sfc-loader against a hand-rolled @vue/compiler-sfc + esbuild-wasm or sucrase pipeline for compiling `<script setup lang="ts">`, `<style scoped>`, and plain `.ts` modules in the browser. Report: browser bundle size of each option, support for scoped CSS and TS type stripping, error message quality (file, line, message), maintenance status. Recommend one.

## Answer

Resolved 2026-08-26. Full report: `../research/05-sfc-compiler-and-ts.md`.

**Use `@vue/compiler-sfc` (esm-browser) + `sucrase` for type stripping.** Same
pair as Vue's own SFC playground (`@vue/repl`). Reject `vue3-sfc-loader`.
Reject `esbuild-wasm`.

Why:

- `vue3-sfc-loader` is unmaintained (last release 2024-02-06, last commit
  2024-09-27) and pins compiler-sfc 3.4.15 inside its bundle. frappe-ui
  `1.0.0-beta` needs `vue >= 3.5.0`, so compiler and runtime would split
  minor versions.
- `vue3-sfc-loader` crashes on TS syntax in template expressions, and
  swallows SFC parse errors: the component loads with a broken template.
- `esbuild-wasm` costs 3.7 MB gzip of wasm and is 4.7x slower per SFC than
  sucrase. Its only edge is richer error objects, which sucrase also gives.
- Hand-rolled is the smallest: 295 KB gzip, against 500 KB for
  `vue3-sfc-loader`.

Numbers (Node 24, 39 SFCs of ~15 lines, relative signal only):

| Pipeline | Gzip | ms per SFC |
|---|---|---|
| compiler-sfc + sucrase | 295 KB | 2.8 |
| vue3-sfc-loader | 500 KB | 12.8 |
| compiler-sfc + esbuild-wasm | 3.99 MB | 13.4 |

Rules the Runtime must follow:

- Sketch owns ~100 lines of glue: parse, `compileScript`,
  `compileStyleAsync`, TS strip, import rewrite, style injection.
  `@vue/repl` `src/transform.ts` is the working reference.
- **Check `parse().errors` first and stop on any error.** With
  `compileScript({ inlineTemplate: true })`, template expression errors do
  not throw; the compiler emits invalid JS and the failure surfaces later as
  a sucrase error in generated code, at a generated-code position.
- Call sucrase with `transforms: ['typescript'], disableESTransforms: true`.
  Without the flag it rewrites class fields and optional chaining to
  helpers, which evergreen browsers do not need.
- Set `filePath` on the sucrase call so the file name lands in the error.
- Errors surface as `file:line:col message` for the `check` step.

Accepted costs:

- Sucrase drops `export namespace` blocks silently and treats `const enum`
  as `enum`. Sketch does stripping only, so this is fine.
- Sucrase is in maintenance mode (one release in two years). If it stalls,
  `esbuild-wasm` is a drop-in for the strip step with the same call shape.
- Sucrase error columns can be wrong for arrow-function parameter types in
  `.ts` modules. `compileScript` (Babel) errors are correct.

Not verified: browser wall-clock, brotli sizes, Safari.
