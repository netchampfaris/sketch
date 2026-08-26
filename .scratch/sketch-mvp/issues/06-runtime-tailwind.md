# How do prototype Tailwind classes get styles at runtime

Type: research
Status: resolved
Blocked by: 

## Question

frappe-ui 1.0.0-beta needs Tailwind v3 with its preset and tokens. Prototype code will use arbitrary utility classes that no build step has scanned. Compare: Tailwind v3 Play CDN with the frappe-ui preset injected, a precompiled safelist, and twind. Report which one can consume frappe-ui's tailwind preset and tokens (`frappe-ui/tailwind`, `frappe-ui/tailwind/tokens.js`), size, and startup cost. Recommend one.

## Answer

Recommendation: build our own browser runtime from the MIT `tailwindcss@3.4` engine plus the frappe-ui preset. Do not use the Play CDN, a safelist, twind, or UnoCSS.

- frappe-ui's preset is code: four Tailwind plugins with `addComponents`, `@apply`, `matchUtilities`, `<alpha-value>` colours. Only the real Tailwind v3 engine runs it. twind and UnoCSS drop `text-sm-medium`, `focus-ring`, `prose-v3`, `.form-input`.
- Prototype built and verified in headless Chromium: 145 KB gzip script (253 KB with all 1962 lucide icons), 302 ms first compile, about 125 ms per later batch, classes added after first paint get styles, arbitrary values and dark mode work.
- Play CDN runs the preset too, but it is proprietary, not on npm, and served only from cdn.tailwindcss.com. Fails self-hosting.
- Safelist: the smallest useful set is 143 KB gzip CSS with no variants, 717 KB with five variants, and it can never cover `w-[13px]`. A `/.*/` safelist got killed by the OS.
- twind is abandoned (last real commit 2023-01) and its CDN preset builds throw. UnoCSS is active but needs a hand-kept translation of the frappe-ui theme and has no `@apply` at runtime.
- Ship two layers: precompiled CSS for frappe-ui internals (46.6 KB gzip) first, then the runtime for prototype utilities.

Findings: [research/06-runtime-tailwind.md](../research/06-runtime-tailwind.md)
