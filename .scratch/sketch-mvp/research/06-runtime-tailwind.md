# 06: How prototype Tailwind classes get styles at runtime

Date: 2026-08-26. Ticket: `../issues/06-runtime-tailwind.md`.

## Recommendation

Build our own browser runtime from the MIT `tailwindcss@3.4` engine plus the frappe-ui preset. Do not use the Play CDN, a safelist, twind, or UnoCSS.

- It is the only option that runs frappe-ui's preset unchanged: `plugin()` functions, `@apply` inside `addComponents`, `<alpha-value>` colours, `matchUtilities`, typography `theme.typography` extensions.
- It is self-hosted. Every input is MIT: `tailwindcss`, `postcss`, `@tailwindcss/forms`, `@tailwindcss/typography`, `frappe-ui` (`license` fields in each `package.json` under `apps/gameplan/frontend/node_modules`).
- Measured in headless Chromium on this VM: 145 KB gzip script, 302 ms first compile, about 125 ms per later batch of new classes. Classes added after first paint get styles.
- A working prototype exists at `/tmp/tw-browser` (not durable). The recipe is in the appendix.

Ship it in two layers:

1. Precompiled CSS for frappe-ui's own components (46.6 KB gzip, see B2). Loaded first. Components render styled at first paint.
2. The runtime script. It watches the DOM and compiles only the prototype's utilities. Its `<style>` comes after the precompiled CSS, so runtime rules win on equal specificity.

## The constraint that decides it

frappe-ui's preset is code, not data. `tailwind/preset.js` registers four plugins: `@tailwindcss/forms`, `@tailwindcss/typography`, its theme plugin, and a lucide icon plugin (`/home/faris/benches/frappe-bench/apps/gameplan/frontend/node_modules/frappe-ui/tailwind/preset.js`, line 34). The theme plugin (`tailwind/plugin.js`) calls `addBase`, `addComponents`, `matchUtilities`, writes `@apply` strings for `.form-input`, and builds `text-<size>-<weight>`, `focus-ring*`, `list-gap-*`, `prose-v3` (`plugin.js` lines 190-260, 462-505). Colours use Tailwind's `<alpha-value>` placeholder in `oklch()` and `color-mix()` strings (`tailwind/colorPalette.js`, `withAlphaPlaceholder`, `generateSemanticColors`). `tailwind/tokens.js` exports only static `borderRadius`, `boxShadow`, `fontSize` plus the colour helpers; it does not export the component classes.

Only the real Tailwind v3 engine executes that plugin API. UnoCSS states it "does not support Tailwind CSS's plugin system or configurations" (https://unocss.dev/guide/why). twind's config type has no `plugins` key (https://github.com/tw-in-js/twind/blob/main/packages/core/src/types.ts). Both lose `text-sm-medium`, `focus-ring`, `prose-v3`, and `.form-input` styling.

The lucide icon plugin reads SVG files with `node:fs` (`tailwind/iconPackPlugin.js`, `tailwind/lucideIconsPlugin.js`). Any browser runtime needs a browser variant that reads a prebuilt name-to-data-URI map. Measured map for 1962 icons: 1.49 MB raw, 107 KB gzip.

## Comparison

| | (a) Play CDN | (a') self-built Tailwind v3 runtime | (b) precompiled safelist | (c1) twind v1 | (c2) UnoCSS runtime |
|---|---|---|---|---|---|
| Runs `frappe-ui/tailwind` preset as is | Yes, if the preset is bundled and assigned to `tailwind.config.presets` (function plugins accepted) | Yes, verified | Yes at build time | No. Takes a resolved `theme` only; no plugins | No. Needs theme rewrite; no plugins |
| `tokens.js` values (radius, shadow, fontSize, colours) | Yes | Yes, verified | Yes | Mostly; `<alpha-value>` OK | Partly; fontSize tuple keys come out camelCase, nested colour keys not found |
| forms + typography | Yes, `?plugins=forms,typography` (server-built bundle) | Yes, bundled from npm | Yes | Ports: `@twind/preset-tailwind-forms`, `@twind/preset-typography` (targets Tailwind 3.2) | `@unocss/preset-typography` (not 1:1, `--un-prose-*`); forms only via community `@julr/unocss-preset-forms` |
| Script size gzip | 123 KB; 150 KB with 4 plugins | 145 KB; 253 KB with lucide map | 0 KB script; CSS 143 KB to 717 KB gzip (see B3) | 18.6 KB (`cdn.global.js`); about 24 KB with forms + typography | 49.6 KB (`uno.global.js`); +5.9 KB typography |
| Startup cost | Same engine as (a'); no first-party numbers | 302 ms first compile, 125 ms per batch (Chromium, this VM) | Zero compile; 143 KB to 717 KB CSS parse | Node only: init 1 ms, 27 classes 19 ms | Node only: init 20 ms, 27 classes 34 ms |
| Self-host | No. Proprietary, no licence, not on npm | Yes. All MIT | Yes | Yes, on npm. Preset `.global.js` files are broken (`twind.core` undefined, issue #453) | Yes, on npm |
| Classes added after first paint | Yes, MutationObserver | Yes, verified | Only if safelisted. Arbitrary values never | Yes, MutationObserver | Yes, MutationObserver on `document.body` |
| Arbitrary values `w-[13px]` | Yes | Yes, verified | No | Yes | Yes |
| `@apply` in prototype `<style>` | Yes, `<style type="text/tailwindcss">` | Yes, append the SFC style text to the PostCSS input | Build only | In `css()` only | No. Build-time transformer only |
| Maintenance | Frozen at 3.4.17 | Tailwind v3 branch, MIT, we own the bundle | n/a | Abandoned. Last real commit 2023-01-24 | Active. 66.8.1 on 2026-08-21 |

Sources per row are in sections A to D.

## A. Tailwind v3 Play CDN

Agents fetched `https://cdn.tailwindcss.com/3.4.17` and the docs. Facts:

- The script runs the full Tailwind PostCSS engine on the main thread. It observes `document.documentElement` with `MutationObserver` (`attributeFilter: ["class"], childList, subtree`), collects every class from `[class]` elements, and writes one `<style>` in `<head>`. Source: the served file, tail section (`/tmp/tw-cdn.js`).
- `window.tailwind.config` is spread into the engine. `presets`, `theme.extend`, and function `plugins` work (docs example: https://v3.tailwindcss.com/docs/installation/play-cdn; function plugin example by the maintainer: https://github.com/tailwindlabs/tailwindcss/discussions/8460). String plugin names do not resolve.
- First-party plugins come from the server: `?plugins=forms,typography,aspect-ratio,line-clamp,container-queries` (https://v3.tailwindcss.com/docs/installation/play-cdn). The base file bundles none of them (`W5=[]` in the served file). An unknown name returns `console.error("Unknown plugin ...")`.
- Size: 407,279 B raw, 123,110 B gzip. With forms, typography, aspect-ratio, container-queries: 512,534 B raw, 149,870 B gzip. Measured 2026-08-26.
- Not self-hostable. Not on npm (`https://unpkg.com/tailwindcss@3.4.17/?meta` lists no cdn file). Maintainer: "The project isn't open source so the source isn't available." and "The code is just proprietary with no license" (https://github.com/tailwindlabs/tailwindcss/discussions/10386). Verified by re-fetching the discussion.
- Docs warning: "The Play CDN is designed for development purposes only, and is not the best choice for production." (https://v3.tailwindcss.com/docs/installation/play-cdn). The script logs the same warning at load.
- Dynamic classes: yes, via the observer. The maintainer notes flashes of unstyled content on late-added elements (https://github.com/tailwindlabs/tailwindcss/discussions/7637).
- `<style type="text/tailwindcss">` supports `@apply` and `@layer` (docs above).
- Limits: inline `<style>` needs a CSP `style-src` nonce or `'unsafe-inline'` (https://github.com/tailwindlabs/tailwindcss/discussions/13326). No Shadow DOM scan. Frozen at 3.4.17; `3.4.18` returns "Unknown Tailwind version".

Verdict: technically able to run the frappe-ui preset, but it is a third-party proprietary script. It fails the self-host requirement.

## A'. Self-built Tailwind v3 runtime (the same idea, MIT)

I built it and ran it. Files: `/tmp/tw-browser/{entry.js,preset-browser.js,shims/,build.sh,test.html,run.mjs}`.

- Inputs: `tailwindcss@3.4.19`, `postcss@8.5.15`, `@tailwindcss/forms@0.5.11`, `@tailwindcss/typography@0.5.19`, `frappe-ui@1.0.0-beta.36` `tailwind/plugin.js`, all from `apps/gameplan/frontend/node_modules`. Bundled with `esbuild@0.28.2`, `--platform=browser --format=iife --minify`.
- Shims (about 60 lines total): `fs` (reads `preflight.css` text and an in-memory `/template.html`), `path`, `url.parse`, `crypto.createHash`, `fast-glob` (`sync`, `escapePath`, `generateTasks`), `micromatch`, `glob-parent`, `util`, `os`, and empty stubs for `jiti` and `sucrase` (config-file loading). Defines: `process.env.*` to `undefined`, `__dirname` to `"/tw"`.
- Content feed: `content: { files: ['/template.html'], extract: { html: s => s.split(' ') } }`, the same trick the Play CDN uses. Tailwind also accepts `{ raw, extension }` entries (https://v3.tailwindcss.com/docs/content-configuration).
- Preset: `preset.js` minus the lucide plugin, plus a browser icon plugin fed by a JSON map (`shims/iconPackBrowser.js`).

Measured (headless Chromium via Playwright 1.62.1, `run.mjs`):

| Build | Raw | gzip | First compile | Later batch |
|---|---|---|---|---|
| No icon plugin | 524,564 B | 144,847 B | 302 ms (60 classes, 100.7 KB CSS) | 125 ms (6 new classes), 132 ms (100 new `mt-[Npx]`) |
| With lucide map | 2,013,815 B | 253,383 B | 277 ms (62 classes) | 123 ms |

Verified in the same run (computed styles):

- `bg-surface-sidebar`, `bg-surface-base`, `text-ink-gray-9`: semantic colours resolve. Dark flip via `data-theme="dark"` changes `body` background.
- `rounded-5` = 10px. `h-17` = 68px (integer spacing). `w-[13px]` = 13px. `bg-blue-500/30` = `oklch(... / 0.3)` (alpha placeholder works).
- `.form-input` height 28px with the `@apply` chain from `componentStyles`. `text-sm-medium` = 500 / 13px. `list-gap-3` sets `--list-gap`. `prose prose-v3` h2 weight 600. `lucide-plus` renders a mask-image icon; `lucide-trash-2` added after first paint also renders.
- `html` font-family is `InterVar, ...` from `globalStyles`.

Notes:

- The runtime must ignore mutations from its own `<style>` and skip compiles with no new class. Without that gate it loops. Fixed in `entry.js`.
- Each compile regenerates the full stylesheet (`@tailwind base` included). Feed only `@tailwind components; @tailwind utilities;` once the precompiled base CSS is loaded, or keep base; both are cheap. Not measured separately.
- Startup numbers come from one VM. Browser parse of the 2 MB script took 10 ms locally; network cost is the gzip size.
- Not verified: Firefox and Safari, CSP nonce handling, memory over a long session.

## B. Precompiled CSS with a safelist

B1. Docs: "Patterns can only match against base utility names", safelisting is for cases where "it's impossible to scan certain content", and Tailwind finds only classes that exist "as complete unbroken strings" (https://v3.tailwindcss.com/docs/content-configuration). Arbitrary values (`w-[13px]`, `grid-cols-[1fr_auto]`) cannot be safelisted. Presets merge `theme.extend` and `plugins` but `safelist` and `content` are replaced by the top-level config (https://v3.tailwindcss.com/docs/presets), so frappe-ui's own `safelist: ['prose','prose-v3']` is dropped when the app sets its own.

B2. Baseline, frappe-ui internals only (`content: node_modules/frappe-ui/src/**`): 514,013 B minified, 46,623 B gzip, 2.0 s (`/tmp/tw-internals`). This is the layer ticket 04 should ship regardless.

B3. Safelist runs with the frappe-ui preset (`/tmp/tw-curated`, `tailwindcss` CLI 3.4.19, `--minify`):

| Safelist | Rules (approx) | Minified | gzip | Compile |
|---|---|---|---|---|
| Semantic colours on bg/text/border, spacing on p/m/gap/w/h/size, radius, shadow, text, font, flex, grid; no variants | 23,844 | 2.22 MB | 143 KB | 6.6 s |
| Same, plus `hover`, `dark`, `sm`, `md`, `lg` on colours and `sm`, `md`, `lg`, `hover` on the rest | 116,781 | 12.9 MB | 717 KB | 58 s |
| `{ pattern: /.*/ }` (everything) | n/a | none | none | Process killed by the OS at 31 s and again at 8 min; never wrote output |

Verdict: the smallest useful safelist already costs as much on the wire as the runtime script, covers no arbitrary values, and each added variant multiplies it. It also needs a rebuild whenever the safelist changes. Reject.

## C. twind v1 and UnoCSS runtime

Agents read docs and source and ran both engines in Node/jsdom against the resolved frappe-ui theme (`/tmp/cssrt`). No browser run.

C1. twind (`@twind/core@1.1.3`, `@twind/preset-tailwind@1.1.4`)

- Runtime: `install(config)` injects a `<style>` and starts a `MutationObserver` on `document.documentElement` for class changes and added nodes (https://github.com/tw-in-js/twind/blob/main/packages/core/src/observe.ts). Late classes verified in jsdom.
- Config: no `plugins`; preset-tailwind "does not explicitly accept a tailwind.config", it reads a Tailwind-shaped `theme` (https://twind.style/packages/@twind/preset-tailwind). With frappe-ui's resolved theme: `text-sm`, `bg-surface-gray-1/50`, `rounded-4`, `shadow-sm`, `h-17`, `dark:`, `w-[13px]` work. `text-sm-semibold`, `focus-ring`, `size-17` miss. `border-[--surface-gray-2]` compiles wrong. `prose-v3` emits junk.
- forms and typography: `@twind/preset-tailwind-forms` (compat `@tailwindcss/forms >=0.5 <0.6`), `@twind/preset-typography` (compat `>=0.5.3 <0.6`) (https://github.com/tw-in-js/twind/blob/main/documentation/preset-tailwind-forms.md, https://github.com/tw-in-js/twind/blob/main/documentation/preset-typography.md). Tracks Tailwind 3.2 (https://github.com/tw-in-js/twind/blob/main/documentation/preset-tailwind.md).
- Size: `cdn.global.js` 49,594 B raw, 18,645 B gzip; core + tailwind + autoprefix + forms + typography about 24.3 KB gzip (jsDelivr, 2026-08-26).
- Self-host: on npm, but the per-preset `.global.js` builds reference an undefined `twind.core` and throw; open since 2023 (https://github.com/tw-in-js/twind/issues/453). The production build turns on class hashing by default and rewrites `class` attributes.
- Maintenance: last non-bot commit 2023-01-24; "Is Twind still maintained?" has no maintainer reply (https://github.com/tw-in-js/twind/discussions/495).

C2. UnoCSS (`@unocss/runtime@66.8.1`, preset-wind3)

- Runtime: `MutationObserver` on `document.body`, batched with `setTimeout(0)`, starts at `DOMContentLoaded`; styles are prepended to `<html>` before `<head>` unless `runtime.inject` is set (https://github.com/unocss/unocss/blob/main/packages-integrations/runtime/src/index.ts, https://unocss.dev/integrations/runtime). Docs warn about FOUC and suggest `un-cloak`.
- Config: "UnoCSS does not support Tailwind CSS's plugin system or configurations" (https://unocss.dev/guide/why). Measured against frappe-ui's theme: fontSize tuples emit `lineHeight:1.15` (camelCase, invalid CSS); nested semantic colours (`surface['gray-1']`) are not found and need flattening; `screens` must become `breakpoints`. `rounded-4`, `shadow-sm`, `h-17`, `size-17`, `w-[13px]`, `dark` via `presetWind3({ dark: { dark: '[data-theme="dark"]' } })` work. `text-sm-semibold`, `prose-v3`, `.form-input` styling miss.
- forms and typography: `@unocss/preset-typography` is not a 1:1 port (`--un-prose-*` vars) (https://unocss.dev/presets/typography). Forms only via community `@julr/unocss-preset-forms` (ESM only, no `.global.js`) (https://github.com/Julien-R44/unocss-preset-forms). `@apply` is build-time only (https://unocss.dev/transformers/directives).
- Size: `uno.global.js` 181,482 B raw, 49,589 B gzip; typography +5,869 B gzip.
- Self-host: yes, all files on npm. Maintenance: active, 66.8.1 published 2026-08-21.

Verdict: both need a hand-written translation of frappe-ui's plugin output, and that translation drifts on every frappe-ui release. UnoCSS is healthy but is a different engine with a documented "complete compatibility may not be guaranteed" (https://unocss.dev/presets/wind3). twind is abandoned. Reject both.

## D. frappe-ui expectations (local source)

- Consumers must use Tailwind v3 with `presets: [frappeUIPreset]` from `frappe-ui/tailwind`, `@import 'frappe-ui/style.css'` then the three `@tailwind` directives (`/home/faris/.claude/skills/frappe-ui/SETUP.md`). `src/style.css` is only the Inter font import plus `@tailwind base; components; utilities;`.
- Package exports expose `./tailwind` and `./tailwind/tokens.js` only (`package.json` lines 79-86).
- `darkMode: ['selector', '[data-theme="dark"]']` (`preset.js` line 22). Tokens flip on that attribute (`colorPalette.js`, `generateCSSVariables`).
- Gameplan's own config adds `@tailwindcss/container-queries` and a `standalone` variant on top of the preset (`apps/gameplan/frontend/tailwind.config.js`). The Sketch runtime should add the same container-queries plugin if prototypes may use `@container`.

## Open items for ticket 04

- Decide whether the runtime compiles `@tailwind base` or only components + utilities.
- Decide whether to ship the 107 KB gzip lucide map, or a smaller map of the icons the frappe-ui skill lists.
- Add a CSP nonce to the injected `<style>` if the sketch site sets `style-src`.
- Measure in Firefox and Safari.

## Appendix: build recipe

```
esbuild entry.js --bundle --format=iife --platform=browser --minify \
  --loader:.css=text --loader:.json=json \
  --alias:fs=./shims/fs.js --alias:path=./shims/path.js --alias:url=./shims/url.js \
  --alias:crypto=./shims/crypto.js --alias:util=./shims/util.js --alias:os=./shims/os.js \
  --alias:fast-glob=./shims/fast-glob.js --alias:micromatch=./shims/micromatch.js \
  --alias:glob-parent=./shims/glob-parent.js \
  --alias:jiti=./shims/empty.js --alias:sucrase=./shims/empty.js --alias:jiti/dist/babel.js=./shims/empty.js \
  --define:process.env.DEBUG=undefined --define:process.env.NODE_ENV='"production"' \
  --define:process.env.JEST_WORKER_ID=undefined --define:process.env.TAILWIND_MODE=undefined \
  --define:process.env.TAILWIND_DISABLE_TOUCH=undefined --define:process.env.OXIDE=undefined \
  --define:process.env.TAILWIND_TOUCH_DIR=undefined --define:__dirname='"/tw"' \
  --inject:./shims/process.js --outfile=dist/tw-runtime.js
```

`entry.js` core loop:

```js
const seen = new Set()
config = { presets: [preset], content: { files: ['/template.html'], extract: { html: s => s.split(' ') } } }
async function compile(force) {
  let added = 0
  for (const el of document.querySelectorAll('[class]')) for (const c of el.classList) if (!seen.has(c)) { seen.add(c); added++ }
  if (!added && !force) return
  globalThis.__twfiles['/template.html'] = [...seen].join(' ')
  const res = await postcss([tailwindcss(config)]).process('@tailwind base;@tailwind components;@tailwind utilities;', { from: '/input.css' })
  styleEl.textContent = res.css   // styleEl appended once to document.head
}
new MutationObserver(records => { if (!ownStyleOnly(records)) compile() })
  .observe(document.documentElement, { attributes: true, attributeFilter: ['class'], childList: true, subtree: true })
```

## Credit

Agents researched the Play CDN, twind, and UnoCSS and ran the Node/jsdom tests. I inspected the frappe-ui source, built the browser runtime, ran the Chromium tests, and ran the safelist compiles.
