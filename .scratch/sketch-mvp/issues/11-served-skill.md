# What the served frappe-ui skill contains

Type: grilling
Status: resolved
Blocked by: 08 (resolved — unblocked)

## Question

Decide what get_skill returns for a given pin: the frappe-ui skill on this box (SKILL.md, COMPONENTS.md, TOKENS.md, DESIGN.md) trimmed for the Runtime, plus Sketch-specific rules: the `src/` file layout, `router.ts`, imports available, what is not available (no server, no backend, no Vite plugins). Decide how the skill is stored and versioned with the Runtime folder.

## Comments

### 2026-08-26 — from ticket 07 (closed out of scope)

Unblocked from 07. Two rules the skill must carry:

- Prototype data lives in plain `ref`s. Show the loading pattern:
  `onMounted(() => setTimeout(...))` for a skeleton, then rows, then the
  empty state.
- Forbid `useList`, `useDoc`, `useCall`, `useDoctype`, `useNewDoc`,
  `createResource`, `createListResource`, `createDocumentResource`,
  `frappeRequest`, `call`. There is no server. They will throw.

### 2026-08-26 — from ticket 12

- The skill documents an app-like tree: `src/components`, `src/pages`,
  `src/App.vue`, `src/router.ts`. Paths in every MCP call are full relative
  paths such as `src/pages/Home.vue`.
- **No Fixture API.** Ticket 07 closed it out of scope and the question text
  above is corrected. All fixture data is inline in plain `ref`s inside the
  prototype files.
- Storage: the skill ships in the runtime folder it belongs to,
  `sketch/public/runtimes/<version>/`, so it is versioned with the Pin by
  construction. No doctype (ticket 12).

### 2026-08-26 — from ticket 04

- **A Prototype ships no entry file.** The Runtime owns the mount. It imports
  `src/App.vue` and the routes from `src/router.ts`, then calls
  `createApp(App).use(router).use(FrappeUI)`. So `src/router.ts` exports a
  **routes array**, not a router. The skill must say this.
- The router is hash mode. The skill must not show `createWebHistory`.
- **Only listed import specifiers resolve.** The import map covers `vue`,
  `vue-router`, `frappe-ui`, and `frappe-ui/list`. Every frappe-ui export
  subpath needs its own Runtime asset, so the skill decides which ones exist.
  `frappe-ui/editor`, `frappe-ui/charts`, and `frappe-ui/icons` are not built
  yet. Note that `ListView` is gone from the root barrel; lists come from
  `frappe-ui/list`.
- Import cycles between Prototype files are not supported.
- `FileUploader` works. The Viewer stubs `upload_file`, so the skill may
  allow it.

## Answer

Resolved 2026-08-27 with Faris.

The skill is a **Sketch-owned rewrite**, not a trim of the box skill. Too much
of the box skill is wrong here rather than surplus: its rule 10 sends every
data call through `useCall`, its rule 12 is a Vite setup guide, its rule 2
names `Editor` from `frappe-ui/editor`, and its rule 8 lets the agent pick any
lucide name. A trim leaves the original reading as authoritative.

It lives at **`sketch/skill/frappe-ui.md`**, in app source, **not in the
Runtime folder**. This overrides ticket 12's comment above. One file serves
every Pin, so editing the skill is an app deploy and the new text reaches
Prototypes made before the edit. Cost accepted: at a second Pin the file
describes one frappe-ui version while some Prototypes render with another.

`get_skill` **takes no arguments**. Its `prototype` argument selected a Pin,
and there is one file, so it selected nothing. It also forced the agent to
call `list_prototypes` first, which `INSTRUCTIONS` contradicts. Amends
ticket 08.

2,900 words, near 21 KB, one blob. Eight sections: mount contract, file tree,
rules, what you can import, tokens, design language, whole files, what does
not exist.

### The four rules that are new

- **Every lucide icon works.** No list, no subset.
- **Eight specifiers resolve** and nothing else: `vue`, `vue-router`,
  `frappe-ui`, `frappe-ui/list`, `frappe-ui/editor`, `frappe-ui/charts`,
  `frappe-ui/icons`, `dayjs`. Any other bare import fails to compile. The skill
  gives the workaround: a helper in `src/lib/`, plus `Intl` and `Date`.
- **`dayjs` is frappe-ui's instance**, with nine plugins already applied. Never
  call `.extend`.
- **Sketch owns the theme.** Never `useColorScheme`, `setColorScheme` or
  `ThemeSwitcher`, and never write `localStorage`. Semantic tokens make both
  schemes work. The Viewer and the Sketch UI share an origin and both use the
  `theme` key, so a Prototype that sets it overwrites its author's preference.

`frappe-ui/experimental` is out. `Accordion`, `Calendar`, `FloatingWindow`,
`MultiEmailInput` and `CodeEditor` are not available.

### Dark mode is in the MVP

The Viewer sets `data-theme` on its own `<html>`, to `light` or `dark`, never
`system`, and never writes `localStorage`. It resolves in this order: a `theme`
parameter in the URL, then `localStorage['theme']`, then
`prefers-color-scheme`. One rule covers all three cases: the owner inside
Sketch chrome, the owner in the fullscreen route, and a visitor on a public
link. `check` passes the URL parameter to force light, so its screenshots stay
deterministic. Amends tickets 10 and 14.

### Runtime work, folded into this ticket

Faris chose to build it here rather than open a ticket. Committed on
`forge/proto/04-runtime-bundle` at `a4a932d`. Ticket 04's measured sizes are
superseded.

**All lucide icons now resolve.** frappe-ui's `lucideIconsPlugin` reads SVG
files with `node:fs`, so ticket 04 dropped it from the browser preset and left
`shims/iconPackBrowser.js` unwired with no map to read. Only the 201 classes
baked into the precompiled `frappe-ui.css` worked, and an unknown name drew an
empty box that `check` reported as `ok`. `make-lucide-map.mjs` now writes all
2,035 icons as data URIs at build time. The map is generated, not committed.

**Four import-map entries added**: `frappe-ui/editor`, `frappe-ui/charts`,
`frappe-ui/icons`, `dayjs`. Rollup splits the shared chunks, so `Button`,
`Tooltip`, `useId`, `dayjs` and `useColorScheme` exist once across the entries.
The editor and charts are lazy by construction: the import map fetches them
only when a Prototype imports them. Their CSS folds into
`frappe-ui-components.css`, which the Viewer loads eagerly, so a chart is
styled the moment its bundle lands.

**`FrappeUIProvider` now mounts in `boot.js`.** Without it `dialog.confirm()`
and `toast.success()` did nothing, reported no error, and `check` said `ok`.
The Runtime owns the mount, so it owns the provider. Verified before and after.

Measured headless against `sketch.localhost`, median of five runs:

| | before | after |
|---|---|---|
| eager render payload | 313 KB gzip | 320 KB gzip |
| the two compilers | 443 KB gzip | 543 KB gzip |
| plain boot to painted | 398 ms | 426 ms |

The eager payload barely moves: editor and charts cost nothing until imported.
The 100 KB is the icon map inside `tailwind.js`, and the 28 ms is the 2,035
entry lookup table.

### Verification

`sketch/tests/test_skill_names.py`, seven tests. It reads the skill, pulls
every import specifier, imported name and component tag out of the fenced code
blocks, and asserts each resolves against the newest built Runtime. It also
asserts the reverse: the six components the skill says are missing really are
missing, so the skill cannot go stale in either direction. Whole-file examples
must import what they render; fragments need only name something real. It
skips when no Runtime is built, because the Runtime is a build artifact and is
not in git. Mutation-checked: inserting `SuperWidget` into the catalog fails it.

The skill's own four example files were extracted and rendered through the
Runtime: `status: ok`, zero errors, list with badges and relative dates, the
Dialog opens, the detail route resolves. Writing them found two real defects in
this ticket's own draft, both fixed: `Editor` is renderless and needs
`EditorContent` in its slot, and the `List` API takes CSS grid track strings
with `ListRows :items`, not column objects.

### Recipes are UI only

Faris asked for a "Select a Recipe" picker when creating a Prototype in the
Sketch UI. The skill does not index recipes and there is no `get_recipe` tool:
the human picks a recipe at creation and the agent finds a working tree, which
teaches the house style better than prose. This means the **UI creates
Prototypes**, which is new: today only `create_prototype` does. Handed to
tickets 14 and 08.

### Rejected

- **A trim of the box skill.** The served copy drifts, and the wrong parts read
  as authoritative because the text around them is unchanged.
- **Generating the skill from the box skill at build time.** The transform must
  encode every inversion, and a personal skill is not a stable input.
- **Listing the 201 icon names.** Faris ruled that all lucide icons must work.
- **Fetching only the icons a Prototype uses.** Near 4 KB instead of 109 KB,
  but it adds a request in series before first paint and misses a class name
  built at run time.
- **A sectioned `get_skill(topic)`.** Ticket 08's reason still holds at 21 KB:
  an agent that skips the tokens section invents off-palette colours.
- **A `get_recipe` tool.** Recipes became a UI affordance.
- **A skill doctype.** Ticket 12 allows two doctypes, and a Desk edit surface
  has no review and no diff.
- **`check` screenshotting both themes.** It doubles ticket 10's measured time
  for failures the agent mostly cannot act on.

### 2026-08-27 — amendment: nine specifiers, not eight

From ticket 17's session. `@vueuse/core` is added to the Runtime import map.

Reason: the recipe set comes from `ui.frappe.io/recipes`, and the **Compose**
recipe, both variants, imports `@vueuse/core`. Every other recipe stays inside
the existing eight.

Cost, measured: `@vueuse/core` **14.4.0**, whole barrel, minified ESM with
`vue` external: **135 KB raw, 49 KB gzip**. Two things make the real cost
lower:

- frappe-ui `1.0.0-beta.55` already depends on `@vueuse/core ^14.1.0`, so part
  of it is already inside the Runtime's frappe-ui chunk and Rollup shares it,
  as it does for `Button`, `Tooltip` and `dayjs`. The marginal number is not
  measured.
- It downloads only when a Prototype imports it, like `frappe-ui/editor` and
  `frappe-ui/charts`. Zero for Prototypes that do not.

Version tracks frappe-ui's own dependency, not a separately chosen one.

**This touches four places, and `sketch/tests/test_skill_names.py` exists to
catch exactly this drift:** the Runtime build entry, `manifest.json`, the
`viewer.html` import map, and the skill's own list of what resolves. Read
"eight specifiers" above as nine.
