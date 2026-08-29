# Sketch UI conventions

Binding for the fix sweep on `forge/onboarding-ui-fixes`. One rule per row, no
options. Sources: frappe-ui skill `DESIGN.md` (Hierarchy, Empty state, Geometry)
and `TOKENS.md` (Typography, Color tokens, Radius, Shadow).

Standing rules: no `variant="solid"` (commit `54f7fdc`); no hardcoded hex, rgb
or arbitrary bracket values; every size and weight is one composite class.

## 1. Heading ladder (4.1, 4.9)

| Role | Class |
|---|---|
| Page title, `h1` in `PageHeader` | `text-2xl-semibold text-ink-gray-8` |
| Page subtitle under `h1` | `text-p-xs text-ink-gray-5` |
| Section heading, `h2` | `text-lg-semibold text-ink-gray-8` |
| Sub-section heading, `h3` | `text-base-semibold text-ink-gray-8` |
| Card title, `h2` in a card | `text-base-medium text-ink-gray-8` |
| Dialog title | the `Dialog` `title` prop. Do not restyle. |

The page title must be the largest text on the screen. 18 > 16 > 14 px, and the
card title drops to medium so it sits under `h3` at the same size.
TOKENS > Typography: the composite carries tuned letter-spacing, so never write
`text-lg font-semibold`.

## 2. Ink ladder (4.8, 5.1)

| Step | Role |
|---|---|
| `text-ink-gray-9` | Not used in Sketch. Remove it from the App wrapper. |
| `text-ink-gray-8` | Page default, all headings, card titles, code text |
| `text-ink-gray-7` | Descriptions and section intro paragraphs |
| `text-ink-gray-5` | Helper text, meta, timestamps, counts, file paths |
| `text-ink-gray-4` | Disabled state only, applied by frappe-ui |

Set `text-ink-gray-8` once on the App shell and once on the viewer body.
DESIGN > Hierarchy reserves gray-9 for unread titles and KPI figures, which
Sketch does not have. Readable text never sits on `ink-gray-4`: it measures
2.85:1 on `surface-base` and fails AA.

## 3. Body against label type (4.6, 3.9)

- `text-p-*` for any text that can reach a second line: paragraphs, helper
  lines, empty-state body, alert body, code blocks, dialog prose.
- `text-*` for one line that never wraps: headings, button labels, badges,
  timestamps, counts, and any node that carries `truncate` or `line-clamp-*`.

The prototype card description carries `truncate`, so it stays `text-sm`.

## 4. Empty state, the one recipe (4.7)

48px circle, 24px icon, `gap-3`, one action at `variant="subtle"`.
DESIGN > Empty state, with the solid button swapped for subtle.

```vue
<div class="flex flex-col items-center justify-center gap-3 py-16 text-center">
  <span class="grid size-12 place-items-center rounded-full bg-surface-gray-2 text-ink-gray-5">
    <span class="lucide-panels-top-left size-6" aria-hidden="true" />
  </span>
  <p class="text-base-medium text-ink-gray-8">No prototypes yet</p>
  <p class="max-w-sm text-p-sm text-ink-gray-5">
    One sentence that says who fills this.
  </p>
  <Button class="mt-2" icon-left="lucide-plus" label="New prototype" theme="gray" variant="subtle" />
</div>
```

Inside a dialog, replace `py-16` with `h-full` and keep every other class.
`size-6` is the empty-state glyph size in DESIGN > Hierarchy icon ladder.

## 5. Skeleton, the one recipe (4.2, 4.4)

Use frappe-ui `Skeleton`. It takes no props; size it with classes. Never a bare
`bg-surface-gray-2` box, and never `LoadingText` in a grid (it has no `lines`
prop).

The placeholder repeats the loaded node's own height and margin classes and
replaces only the text, so the grid cannot jump.

```vue
<div v-for="n in 3" :key="n">
  <Skeleton class="aspect-[16/10] w-full rounded-6" />
  <div class="mt-3 flex h-10 flex-col gap-2">
    <Skeleton class="h-4 w-40" />
    <Skeleton class="h-3.5 w-56" />
  </div>
  <div class="mt-2 flex h-9 items-center pt-2"><Skeleton class="h-4 w-32" /></div>
  <div class="flex h-7 items-center"><Skeleton class="h-3.5 w-48" /></div>
</div>
```

For one value inside a fixed-height slot, such as the header count line, put
`<Skeleton class="h-4 w-24" />` in the same slot. Do not hide the slot.

## 6. Code block (3.2, 3.9, 3.14)

```vue
<p class="text-p-sm text-ink-gray-7">{{ item.help }}</p>
<p class="mt-1 truncate font-mono text-xs text-ink-gray-5">{{ path }}</p>
<div class="mt-3 flex justify-end">
  <Button icon-left="lucide-copy" label="Copy" @click="copy(...)" />
</div>
<pre class="mt-2 whitespace-pre-wrap break-all rounded-4 bg-surface-gray-1 p-3 font-mono text-p-xs text-ink-gray-8">{{ snippet }}</pre>
```

- Wrap, never scroll sideways: `whitespace-pre-wrap break-all`.
- `text-p-xs` gives 12px at paragraph leading. Do not add `leading-5` on top.
- The copy Button sits above the block, right aligned, always labelled. It must
  not float over the code, because wrapped text reaches the top-right corner.
- The mono path slot holds a path only. Prose belongs in the help paragraph.

## 7. Tinted status block (3.11)

Do not use `Alert` for a tinted warning. Its container is always gray, so the
theme colors the icon alone. Build the block from tokens
(TOKENS > `bg-surface-*`, tinted status block).

```vue
<div class="flex gap-2 rounded-6 border border-outline-amber-3 bg-surface-amber-2 p-3 text-ink-amber-7">
  <span class="lucide-triangle-alert mt-0.5 size-4 shrink-0" aria-hidden="true" />
  <div class="min-w-0">
    <p class="text-base-medium">Title in sentence case</p>
    <p class="mt-1 text-p-sm">Body copy.</p>
  </div>
</div>
```

Swap `amber` for `red`, `green` or `blue` in all three classes together. One
tinted block per screen, per DESIGN principle 7.

## 8. Helper and meta text (3.15)

One helper size: `text-p-xs text-ink-gray-5` (12px, wrapping). One meta size:
`text-xs text-ink-gray-5` (12px, single line).

`FormControl`'s `description` prop renders 13px and cannot be retuned, so do not
pass it. Render the helper as a sibling: `<p class="mt-2 text-p-xs
text-ink-gray-5">`. One card then holds one helper size.

## 9. Spacing rhythm (3.16, 3.7)

| Step | Gap |
|---|---|
| Heading to its intro paragraph | `mt-1` |
| Section intro to first card | `mt-4` |
| Card to sibling card | `mt-4`, or `space-y-4` on the wrapper |
| Section to next section | `mt-10` |
| Section heading to `h3` inside it | `mt-8` |
| Card padding, and steps inside a card | `p-5`; `mt-2` helper, `mt-3` actions |

DESIGN > Geometry sets `space-y-6` for generic sections; Sketch cards are dense,
so siblings use one step, `mt-4`. If a panel needs a height reserve, use a scale
value such as `min-h-80`. Bracket values like `min-h-[22.6rem]` are banned.
