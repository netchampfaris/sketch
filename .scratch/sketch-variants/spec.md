# Variants: a standard switcher for design options

Status: built on `forge/variants`, stacked on PR #8 (`forge/annotate`).

## Problem

Designers ask for two or three versions of a card, a section or a page, flip between them, and pick one, often by showing the founder. Today every Prototype hand-builds its own switcher pill, and only when the user explains the pattern. The losing versions then stay in the code.

## What it is

- **A primitive.** Sketch ships one component, `<Variants>`. A Prototype wraps each version in a named slot.
- **One pill per page.** Every set on the page appears in it, for every viewer, including a Guest on a public link.
- **A way to pick.** The owner presses "Keep" on a version. That leaves a note for the agent, which deletes the others.

The agent learns this from the skill, so a comment like "give me 3 variants of this" is enough.

## Principles for this build

These come from ponytail and Karpathy's guidelines, and they bind every decision below.

- Reuse before adding. Keep is an annotate note, the hover outline is one absolutely positioned box, and the state is a `reactive` map.
- Nothing speculative. Cut from v1: cross-page sets, keyboard shortcuts, a reason line per option, and side-by-side compare.
- Touch only what the feature needs. Annotate changes in two places only (launcher offset and the Keep handler). Existing Prototypes with hand-made pills are left alone.
- Each step has a check (see Tests).

## Decisions

### The component

```vue
<script setup>
import { Variants } from 'sketch:variants'
</script>

<template>
  <Variants name="Leave card">
    <template #compact>…</template>
    <template #detailed>…</template>
    <template #timeline>…</template>
  </Variants>
</template>
```

- **Slots.** The slot names are the options, in slot order. Labels are humanised (`scan-first` becomes "Scan first").
- **No wrapper element.** It renders the chosen slot only. There is no extra `div`, so layout is unchanged.
  - For the outline and for Keep, it finds the slot's first element through a zero-size comment-anchored ref. If the slot renders several roots, it uses the union of their rects.
- **`name`.** Required. It is unique on a page, and the key is its slug.
  - When two mounted sets share a key, the second gets ` 2` added to its label and a `console.warn`.
- **Default.** The first slot is the default. The agent puts the current design first.
- **One export.** `Variants` is the only export. There are no props beyond `name`, and no composable.

### Scope: per page

- **What is listed.** A set is listed while it is mounted, so the pill always shows the sets on the current page. Cross-page sets are out of scope until people ask for them.
- **Choices survive navigation.** They live in one in-memory `reactive` map keyed by `route.path + key`. Going to Inbox and back to Home keeps Home's choices.

### URL

- **Mirroring.** The current page's non-default choices are mirrored into the route query as `v=<key>.<option>`, comma-separated, with `router.replace` and no new history entry.
- **Opening a link.** The query is read on load. A link like `…#/inbox?v=leave-card.timeline` opens on Timeline, so it can be shared with the founder.
- **Prototype queries are untouched.** All other query keys, such as `as=manager`, are left as they are. The key is a single `v`, so it cannot collide with a Prototype's own query names, which are normally words.

### The pill

The host is body-level and marked `data-sketch-ui`, so annotate's pins and Tweak skip it. It is fixed bottom-right, 12px from the edges, and uses frappe-ui tokens. There are no solid buttons, and it follows `.scratch/sketch-review/conventions.md`.

- **No sets on the page.** Nothing renders.
- **One set.** The pill shows the set's name followed by its options as a frappe-ui `TabButtons`. No expanding.
- **Two or more sets, collapsed.** A button reads "Variants" followed by the count, for example "Variants 3", with `lucide-layers` on the left.
  - A small dot shows when any set is off its default.
- **Expanded.** A panel opens above the pill.
  - It has one row per set, ordered by the set's position on the page (top to bottom, then left to right).
  - Each row shows the name on the left and a `TabButtons` of options on the right.
  - A set off its default shows a dot before its name.
  - The panel is at most 360px wide, with `max-h-[60vh]` and scroll.
  - Esc, a click outside and the pill itself close it.
- **Hover a row.** One outline box, 2px `outline-blue-6` with radius 6, is drawn over the set's rect, so "which Card is this" is answered by pointing.
- **Switching.** It swaps the slot instantly, with no animation, because comparing needs the snap.
- **Mobile, under 640px.** The panel is full width minus the 12px gutters. The pill stays as it is.
- **Hidden** when the Viewer is framed (gallery cards) or rendering for `check`, so thumbnails and check screenshots show the design only.
  - boot.js sets `document.documentElement.dataset.sketchChrome = 'off'` in those cases.
  - The implementer finds the existing check signal in boot.js rather than adding a new one.

### Living with annotate

- **Corner.** When the pill shows, annotate's launcher (`triggerStyle`, default corner bottom-right) moves up by the pill's height plus 8px.
  - This only happens while the launcher sits in a bottom-right anchor. The pill exposes its height as the `--sketch-variants-h` CSS variable on `<html>`.
- **Keep.**
  - A Keep button (`lucide-check`, ghost) shows on each row, and on the single-set pill, only for the owner's live tab.
  - It only shows when the set is off its default, or when the owner hovers the row. Picking the default is also a real choice, so hovering reveals it.
  - Annotate registers the handler: `sketch:variants` exports an internal `setKeepHandler(fn)`. The skill does not mention it.
  - Pressing Keep adds a normal annotate note anchored on the set's element. The note reads "Keep "<Option>" for <name>. Remove the other variants and the <Variants> wrapper."
  - The row then shows "Kept" (`lucide-check`, gray) until reload. The agent applies the note the usual way: get_annotations, edit, commit, clear_annotations.
- **No handler.** For a Guest, or when annotate failed to load, Keep never renders.

### Build and loading

- **Source.** `runtime/variants/` holds `Variants.vue`, `Pill.vue` and `index.ts`.
- **Build.** A second entry in `runtime/vite.annotate.config.js` produces `variants.js` with the same externals. The config is not renamed.
- **Imports.** Add `sketch:variants` to the import map, `manifest.json`, the runtime README, and this time the skill's specifier table, which becomes ten specifiers, because Prototypes import it.
- **Mounting the pill.** The pill mounts lazily the first time a `<Variants>` mounts. A Prototype without sets gets no pill and no extra DOM.

### Skill (agent guidance)

Add a short "Variants" section to `sketch/skill/frappe-ui.md`, with the example above and these rules:

- When the user asks for variants, options, alternatives or versions of anything, use `<Variants>`. Never build a switcher.
- Make 2 to 4 options. Put the current design first. Name each slot after its idea (`compact`, `timeline`), never `a`, `b` or `v1`.
- Give each set a `name` that says what it is ("Leave card", "Inbox layout").
- A set covers the smallest part that differs. A whole page is fine when the whole page differs.
- When a note says "Keep …", replace the `<Variants>` block with the kept slot's content, delete the other slots and any code only they used, then commit.

Also update the MCP server instructions with one sentence: "Asked for variants, use `<Variants>` from `sketch:variants`."

## Out of scope

- Sets that span pages, and app-level sets.
- Keyboard switching.
- Reason or description text per option.
- Side-by-side comparison.
- Voting or comments from Guests.
- Migrating Prototypes that already have hand-made pills.

## Tests

- **Python:**
  - The drift tests pass with `sketch:variants` in the import map, the manifest, the runtime README and the skill table.
  - The skill's import-specifier test resolves `import { Variants } from 'sketch:variants'`.
- **Browser, by script on the local bench** (owner sid plus a Guest on a public Prototype):
  1. A page with one set shows the inline pill. A page with three sets shows "Variants 3". A page with none shows no pill.
  2. Switching updates the DOM and the `v=` query. A reload restores the choice. Going to another route and back keeps it.
  3. Hovering a row draws the outline over the right element.
  4. The Guest sees the pill and switches, with no Keep.
  5. A framed page and a `check` run show no pill, and the check screenshot has no pill.
  6. Keep creates a note that `get_annotations` returns, with the right text and anchor.
  7. Annotate's launcher sits above the pill, and Comment and Tweak cannot pick the pill.
  8. No console errors on any of the above.

## Demo states (added 7 Oct)

Phases of a workflow ("Self, 360, Manager, Results") and personas ("Employee, Manager") are not variants. Every option is real, none is ever removed, and they usually drive data across the page or the app, not one block. So they are a value, not slots.

### API

```ts
import { useDemoState } from 'sketch:variants'
const phase = useDemoState('Cycle phase', ['Self', '360', 'Manager', 'Results'])
// phase.value === 'Self'; writable, so a demo flow can move it (`phase.value = '360'` on submit)
```

- Options are labels. The value is the label. The URL uses slugs.
- The first option is the default.
- **Global, not per page.** The value is keyed by the name's slug only, so the same name called from two components shares one value.
- **Listed while any caller is mounted.** A state declared in App.vue (a persona) is always listed. One declared in a page is listed on that page only.
- **URL.** Non-default values are mirrored as `s=<key>.<option>`, comma separated, with `router.replace`, read on load, and independent of `v`.

### Two pills

- **Order.** States sit at the bottom-right corner, and the Variants pill stacks 8px above it. States are the lasting context; variants come and go.
- **Each pill on its own** follows the existing rules:
  - one item shows inline, with its name and TabButtons;
  - two or more show a button: "States N" with `lucide-sliders-horizontal`, or "Variants N" with `lucide-layers`.
- **States carry no Keep, no default dot and no hover outline.** They have no element.
- **Only one panel is open at a time.** Opening one closes the other. Each panel opens directly above its own pill, so the States panel pushes the Variants pill up.
- **Launcher offset.** `--sketch-variants-h` measures the whole stack.
- **Hidden** in framed and check pages, the same as before.

### Skill

- Personas, roles, workflow phases, and data states (empty, full, error) use `useDemoState`.
- Never build a switcher, a persona menu or a phase pill.
- Declare a persona in App.vue. Declare a phase in the page that uses it.

## As built

- **Lazy mount.** `mount.ts` mounts the pill host for the first set or state. It skips the mount when `sketchChrome` is `off`, and re-applies `s=` after each navigation, so a persona outlives links that drop the query.
- **One query mirror.** `v` and `s` share `mirrorParam` in `state.ts`, and links are read through `fromQuery`.
- **Row props.** Rows are a `createReusableTemplate` with declared props (`s`, `solo`, `plain`), so a bare `solo` arrives as true and nothing leaks onto the DOM.
- **Panel layout.** The panel is `w-max max-w-full`, which replaces the spec's 360px cap. Rows are a subgrid, so names, options and Keep line up in columns.
- **Keep.** It is labelled "Keep", with an aria-label naming the option and set. In the single-set pill it always shows for the owner. In the panel it shows on hover, or when the set is off its default.
- **Notes keep their tags.** Keep notes name `<Variants>`, which Frappe used to strip from a Guest's form. PR #8 makes `save_annotations` `xss_safe` for that reason.
