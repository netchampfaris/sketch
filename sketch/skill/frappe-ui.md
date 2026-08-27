# Writing a Sketch Prototype

High-fidelity frappe-ui screens that render in the browser. Real components,
real design tokens, no mock markup.

Read this once per session, before you write a file.

---

## 1. How a Prototype mounts

Sketch owns the mount. A Prototype ships no entry file, no `main.ts`, no
`index.html`, and never calls `createApp`.

The Runtime does this for you:

```js
const App = await import('src/App.vue')
const routes = await import('src/router.ts')      // the default export
const router = createRouter({ history: createWebHashHistory(), routes })
createApp(FrappeUIProvider wrapping App).use(router).use(FrappeUI).mount('#app')
```

Three consequences:

- **`src/router.ts` default-exports a routes array**, not a router. Never call
  `createRouter` yourself. Never import `createWebHistory`.
- **The router is hash mode.** Links are `/#/issues`, and `<RouterLink to="/issues">`
  writes that for you. Do not write `history` mode paths.
- **`FrappeUIProvider` is already mounted.** `dialog.confirm()`, `dialog.prompt()`
  and `toast.success()` work straight away. Do not mount it again.

Files compile in the browser. TypeScript is stripped, not type-checked, so a
type error is invisible and a syntax error is fatal.

Import cycles between Prototype files are not supported.

## 2. The file tree

```
src/
  App.vue          the shell: nav or sidebar, plus <RouterView />
  router.ts        export default [ { path, component }, ... ]
  pages/           one file per route
  components/      everything reused across pages
```

Every path you pass to a tool is the full relative path, such as
`src/pages/Issues.vue`. Any other file under `src/` is yours: put helpers in
`src/lib/`, data in `src/data.ts`.

Put the fixture data in plain `ref`s in the file that uses it, or in a shared
`src/data.ts`. There is no backend to fetch it from.

## 3. Rules

1. **Pick the component, do not build one.** Reach for raw HTML only for
   layout: flex, grid, spacing. Never hand-roll `<button class="bg-blue-500">`.
2. **Semantic tokens, never raw colours.** `bg-surface-*`, `text-ink-*`,
   `border-outline-*`. Never `bg-gray-100`, `text-gray-900`, `border-gray-300`.
   Raw colours do not follow the theme, and Sketch renders dark as well as light.
3. **Colour is `variant` plus `theme`.** `variant` is `solid | outline | subtle |
   ghost`. `theme` is `gray | blue | green | red | orange`. There is no `intent`,
   `kind`, `severity` or `appearance` prop.
4. **Two-way state through `v-model`.** Inputs take `v-model`. Overlays take
   `v-model:open`. Comboboxes take `v-model` plus `v-model:query`. Never
   `:value` with `@change`. Never a bare `v-model` on `<Dialog>`.
5. **Use the labelling contract.** Every control accepts `label`, `description`,
   `error` and `required`. Use them. Never a placeholder as a label, never a
   separate `<label>`.
6. **Slot names are fixed.** `#prefix`, `#suffix`, `#trigger`, `#empty`,
   `#header`, `#footer`, `#default`, and per item `#item-prefix` and
   `#item-suffix`. There is no `#icon-left`.
7. **Icons are CSS classes.** `<span class="lucide-rocket size-4" aria-hidden="true" />`.
   Every lucide icon name works. For a component's `icon` prop, pass the string
   `"lucide-rocket"`. Never import an icon as a Vue component from lucide.
8. **Use the imperative helpers for one-shot UI.** `dialog.confirm`,
   `dialog.alert`, `dialog.prompt`, `toast.success`, `toast.error`, `toast.info`.
   Never hand-mount a `<Dialog>` to ask "are you sure?".
9. **Style through `data-slot` and `data-state`, not class injection.** There is
   no `triggerClass` or `contentClass` prop, by design.
10. **Sketch owns the theme.** Never call `useColorScheme` or `setColorScheme`.
    Never render `ThemeSwitcher`. Never write to `localStorage`. Use semantic
    tokens and both light and dark work with no effort from you.

## 4. What you can import

Nine specifiers resolve. Nothing else does, and a bare import of anything else
fails to compile.

| Specifier | Holds |
|---|---|
| `vue` | the framework |
| `vue-router` | `RouterLink`, `RouterView`, `useRoute`, `useRouter` |
| `frappe-ui` | 136 exports: every core component |
| `frappe-ui/list` | the List family |
| `frappe-ui/editor` | rich text, TipTap based |
| `frappe-ui/charts` | the chart family, ECharts based |
| `frappe-ui/icons` | 8 hand-drawn Frappe icons that lucide has no match for |
| `dayjs` | dates. Same instance frappe-ui uses |
| `@vueuse/core` | Vue composables. Same version frappe-ui uses |

`frappe-ui/editor` and `frappe-ui/charts` are large. They download only when a
Prototype imports them, so import them only on the page that draws them.

### `frappe-ui`

**Actions.** `Button` is the default trigger: `<Button label icon iconLeft
iconRight variant theme size loading disabled />`. `size` runs `sm | md | lg |
xl | 2xl`. Pass `route` for in-app navigation or `link` for an external URL and
it renders the right element. A primary action is `variant="solid"
theme="gray"`. A destructive one is `theme="red"`.
`Dropdown` is a menu anchored to its first child: `<Dropdown :options="[{ label,
icon, onClick }]"><Button icon="lucide-ellipsis" /></Dropdown>`.

**Overlays.** `Dialog` with `v-model:open`, plus `title`, `message`, `icon`,
`theme`, `size`, `actions`, `dismissible`. Each action's `onClick` receives
`{ close }`. `bare` drops the chrome, for a command palette. `Popover` for
arbitrary anchored content, slots `#target` and `#body`. `Tooltip` for a hover
hint only, never for anything clickable. `HoverCard` for a rich hover preview.
`ContextMenu` for right-click.

**Inputs.** `FormControl` is the wrapper you want by default: pass
`type="text" | "textarea" | "select" | "checkbox"`. Underneath sit `TextInput`,
`Textarea`, `Password`, `Select`, `MultiSelect` (`v-model` is an array),
`Combobox` (`v-model` plus `v-model:query`), `Checkbox`, `Switch`, `Radio`,
`RadioGroup`, `Slider`, `Rating`, `Duration`, `DatePicker`, `TimePicker`,
`DateTimePicker`, `DateRangePicker` (`v-model` is a two-item array).
`FileUploader` works: Sketch stubs the upload endpoint, so it reports progress
and returns a file.

**Display.** `Badge` for a status pill, same `theme` and `variant` axes as
`Button`. `Alert` for an inline notice: `title`, `description`, `theme`,
`primary-action`, `secondary-action`, `dismissible`. A `description` or a
second action switches it to the stacked layout. `Avatar` builds initials from
`label` when there is no `image`. `Progress`, `Spinner`, `LoadingIndicator`,
`LoadingText`, `Skeleton`, `Divider`, `Breadcrumbs`, `KeyboardShortcut`,
`Tabs` with `v-model:tab` for page sections, `TabButtons` for an inline
segmented control, `Tree` for hierarchy, `Icon`, `ScrollArea` for any scroll
region you own.

**Layout.** `DesktopShell` with slots `#rail`, `#sidebar` and default.
`MobileShell` with default and `#nav`. The Sidebar family: `Sidebar`,
`SidebarHeader`, `SidebarSection`, `SidebarLabel`, `SidebarItem`,
`SidebarCard`, `SidebarCollapseToggle`, plus `Rail` and `RailItem`.
`PageHeader` and `PageHeaderBase` (padding free, for two-pane layouts).
`MobileNav`, `MobileNavItem`, `BottomSheet`. The Settings family:
`SettingsDialog`, `SettingsSidebar`, `SettingsNavGroup`, `SettingsNavItem`,
`SettingsPanel`, `SettingsHeader`, `SettingsBody`, `SettingsContent`,
`SettingsRow`.

There is no `Card`. Compose a surface directly:
`bg-surface-base rounded-4 border border-outline-gray-1 p-4`.

Legacy, never in new code: `ItemListRow`. Use the List family instead.

**Helpers.** `dialog`, `toast`, `debounce`, `usePageMeta`,
`useKeyboardShortcut`, `vFocus`, `vOnOutsideClick`.

### `frappe-ui/list`

`List`, `ListRow`, `ListCell`, `ListHeader`, `ListHeaderCell`,
`ListHeaderCellSort`, `ListGroup`, `ListRows`, `useVirtualRows`.

Use it for every list. Feed mode has no columns. Table mode takes `:columns`
plus `ListHeader`. `ListGroup` makes a labelled bucket. Selection is
`selectable` plus `v-model:selection`. The active row is `v-model:active`. Row
height is `:row-height`. Sorting is your code: a header cell only draws the
`direction` you hand it.

### `frappe-ui/charts`

`BarChart`, `LineChart`, `AreaChart`, `DonutChart`, `FunnelChart`,
`HeatmapChart`, `ScatterChart`, `SankeyChart`, `NumberCard`, plus `ChartCard`,
`ChartContainer`, `ChartLegend`, `ChartTooltip`, `useChart`, `paletteColors`.

Props are flat and name the columns of your rows:

```vue
<BarChart title="Issues per month" :data="rows" x="month" y="count" />
```

`y` takes an array for several series. `series` groups long data. Give the
chart a parent with a height, such as `class="h-80"`, or it draws at zero
height.

### `frappe-ui/editor`

`Editor` is **renderless**: it owns the editor and renders no UI, so put
`EditorContent` in its slot or nothing appears and nothing errors.

```vue
<Editor v-model="content" :extensions="[RichTextKit]">
  <EditorFixedMenu :items="articleToolbar" />
  <EditorContent />
</Editor>
```

`EditorFixedMenu` needs `:items`. It is a required prop, and a bare menu draws
nothing and reports no error.

Kits: `RichTextKit` for a full editor, `InlineKit` for one line, `CommentKit`
for a comment box, `StarterKit` for the base. Chrome: `EditorFixedMenu`,
`EditorBubbleMenu`, `EditorFloatingMenu`, `EditorDropZone`. Toolbars:
`articleToolbar`, `commentToolbar`, `minimalToolbar`, `tableToolbar`.
`format` is `'html' | 'json' | 'markdown'`.

### `dayjs`

The instance frappe-ui already configured. These plugins are applied:
`relativeTime`, `localizedFormat`, `updateLocale`, `isToday`, `duration`,
`utc`, `timezone`, `advancedFormat`, `customParseFormat`. Never call `.extend`,
and never import `dayjs/plugin/...`.

```ts
import dayjs from 'dayjs'
dayjs().format('DD MMM YYYY')
dayjs(row.modified).fromNow()        // "3 days ago"
```

### Anything else

No other package resolves. `lodash`, `axios`, `date-fns`, `chart.js`, `zod` and
the rest all fail to compile.

Instead: write a small helper in `src/lib/`, and use the built-ins.
`Intl.NumberFormat` formats currency and numbers. `Intl.DateTimeFormat` and
`dayjs` cover dates. `structuredClone` copies. `crypto.randomUUID` makes ids.

## 5. Tokens

Semantic tokens flip with the theme. Raw palette classes do not.

**Ink, for text and icons.**
`text-ink-{base | gray-1..9 | red|green|amber|blue|cyan|pink|violet|orange|purple|teal|yellow-1..9 | blue-link}`

| Token | Role |
|---|---|
| `ink-gray-9` | page default, strongest values, unread titles, KPI figures |
| `ink-gray-8` | titles, headings, primary content |
| `ink-gray-7` | secondary values, table cells, descriptions |
| `ink-gray-6` | field labels, form icons |
| `ink-gray-5` | timestamps, counts, captions, meta |
| `ink-gray-4` | ids with `tabular-nums`, decorative glyphs |

`text-ink-blue-link` for links. `text-ink-red-5` for error and negative.
`text-ink-green-5` for success and positive.

**Surface, for backgrounds.**
`bg-surface-{base | gray-1..10 | <colour>-1..10 | sidebar | elevation-1..3}`.
`base` is the page. `gray-1` and `gray-2` are subtle and hover. `gray-3` is
pressed. `sidebar` is the sidebar. `elevation-2` is a dialog body.
`elevation-3` is a selected row. `red-2`, `green-2`, `amber-2` and `blue-2` are
tinted banners.

**Outline, for borders and rings.**
`border-outline-{base | gray-1..9 | <colour>-1..10 | elevation-1..2}`.
`gray-1` and `gray-2` are the default borders. Focus rings are global and
automatic: never add your own.

Ink and surface chromatic ramps do not share numeric steps. Do not swap the
number across categories.

**Type.** Two parallel scales, same pixel sizes, different line heights.
`text-*` is tight, for single-line labels: headings, button text, badges, table
cells, stat values, "2h ago". `text-p-*` is loose, for anything that wraps:
paragraphs, descriptions, helper text.

| Class | Size | Use |
|---|---|---|
| `text-2xs` / `text-p-2xs` | 11px | micro labels, tiny captions |
| `text-xs` / `text-p-xs` | 12px | captions, meta |
| `text-sm` / `text-p-sm` | 13px | secondary labels and paragraphs |
| `text-base` / `text-p-base` | 14px | body, the default |
| `text-md` / `text-p-md` | 15px | dense section labels |
| `text-lg` / `text-p-lg` | 16px | section subheads |
| `text-xl` / `text-p-xl` | 17px | card and panel titles |
| `text-2xl` | 18px | page titles |
| `text-3xl` | 20px | prominent page titles |

Composites such as `text-base-semibold` and `text-lg-semibold` read better than
a size plus a weight. Letter spacing is tuned: do not override it.

**Never uppercase a heading.** No `uppercase`, no faked all-caps with
`tracking-wider`. Frappe UIs use sentence case: "Recent activity", not "RECENT
ACTIVITY". Separate a quiet section label with size and colour, such as
`text-sm text-ink-gray-5`.

**Radius.** `rounded-1` 4px for tags. `rounded-4` 8px for inputs, buttons and
list items, the default. `rounded-5` 10px for cards. `rounded-6` 12px for
dialogs. `rounded-full` for avatars and status dots.

**Shadow.** `shadow-sm` cards. `shadow-md` popovers. `shadow-lg` dialogs.
`shadow-xl` floating panels.

## 6. Design language

**Principles.**

1. Gray first. Ink-gray on surface-base. Colour only where it carries meaning.
   The primary button is `solid` plus `gray`.
2. Hierarchy through ink, not boxes. Use the ink ladder, the type scale, and
   `divide-y divide-outline-gray-1`. A border must earn its place.
3. One primary action per screen, usually in the page header. Everything else
   is `subtle` or `ghost`.
4. Dense but breathable. 13 to 14px body, 40 to 60px rows, 48px header,
   generous padding at the bottom of a scroll area.
5. Alignment over flow. A repeating trailing element, such as a badge or a
   timestamp, gets a fixed-width column, not a ragged flex row.
6. Icons support a label, they do not replace it. Icon-only buttons are for
   universal actions only.
7. At most one accent per screen.

**Screen shapes.**

| Shape | Composition |
|---|---|
| Feed list | `List` in feed mode, rows `h-15`, title plus a meta line |
| Data table | `List` with `:columns` and `ListHeaderCellSort`, `:row-height="40"` to `60` |
| Two pane | Split panes under a `PageHeaderBase` |
| Board | `ScrollArea orientation="horizontal"`, columns on `bg-surface-gray-1`, cards on `bg-surface-elevation-1` |
| Compose | Focused page, no sidebar, `Editor` plus `EditorFixedMenu`, prose column `max-w-[770px]` |
| Detail plus meta | Content column, then a right panel `w-[20rem] shrink-0 border-l` of label and control rows |
| Settings | `SettingsDialog`, nav groups, then `space-y-11 pt-6` sections of `SettingsRow` |
| Dashboard | Centred `max-w-4xl space-y-6`, KPI strip as `divide-x divide-outline-gray-2` |

A list and its detail are two routes with the id as a parameter, not one
component with a toggle.

**Geometry.** Sidebar `14rem`. Page header `min-h-12`. Gutters `px-3 sm:px-5`,
the same pair on header and body. Reading pages `max-w-[940px]` centred, prose
`max-w-[770px]`, dashboards `max-w-4xl`. Stacks: sections `space-y-6`, form
fields `space-y-4`, sidebar nav `space-y-0.5`, inline actions `gap-2`. Page top
`pt-5`, scroll-area bottom `pb-10` or more.

**Colour with meaning.** Status and unread dots `bg-surface-{red,amber,blue,green}-7`.
Negative `text-ink-red-5`, positive `text-ink-green-5`. Map status badge themes
in one lookup: `({ open: 'blue', closed: 'gray', error: 'red', done: 'green' })[s] ?? 'gray'`.
Not encoding state, sign, severity or unread? Then it is gray.

**Icons.** `size-4` default, `size-3.5` inline meta, `size-5` a mobile row
leading icon, `size-2` a status dot.

**Empty, loading and hover states are part of the screen**, not a follow-up.
Every list gets an empty state. Every screen that "loads" gets a skeleton.

Loading, with no server: hold the fixture behind a short timer, so the skeleton
and the empty state are both real and both visible.

```ts
const rows = ref([])
const loading = ref(true)
onMounted(() => setTimeout(() => { rows.value = ISSUES; loading.value = false }, 600))
```

Empty state:

```vue
<div class="flex flex-col items-center justify-center gap-3 py-16 text-center">
  <div class="rounded-full bg-surface-gray-2 p-3 text-ink-gray-5">
    <span class="lucide-inbox size-6" aria-hidden="true" />
  </div>
  <p class="text-base text-ink-gray-7">No issues yet</p>
  <p class="text-sm text-ink-gray-5">Create one to get started.</p>
  <Button variant="solid" theme="gray" icon-left="lucide-plus" label="New issue" class="mt-2" />
</div>
```

## 7. Whole files

### `src/router.ts`

```ts
import Issues from './pages/Issues.vue'
import IssueDetail from './pages/IssueDetail.vue'

export default [
  { path: '/', component: Issues },
  { path: '/issues/:id', component: IssueDetail, props: true },
]
```

### `src/App.vue`

```vue
<script setup lang="ts">
import { RouterView } from 'vue-router'
import { DesktopShell, Sidebar, SidebarHeader, SidebarItem, ScrollArea } from 'frappe-ui'
</script>

<template>
  <div class="h-screen w-full bg-surface-base text-ink-gray-9">
    <DesktopShell>
      <template #sidebar>
        <Sidebar width="14rem" class="border-r">
          <SidebarHeader title="Tracker" subtitle="Acme" />
          <ScrollArea class="min-h-0 flex-1" viewport-class="px-2 pt-0.5 pb-10">
            <div class="space-y-0.5">
              <SidebarItem label="Issues" icon="lucide-circle-dot" to="/" />
            </div>
          </ScrollArea>
        </Sidebar>
      </template>
      <RouterView />
    </DesktopShell>
  </div>
</template>
```

### `src/pages/Issues.vue`: a list page with a form in a Dialog

```vue
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Badge, Button, Dialog, FormControl, PageHeader, toast } from 'frappe-ui'
import {
  List,
  ListHeader,
  ListHeaderCell,
  ListHeaderCellSort,
  ListRows,
  ListRow,
  ListCell,
} from 'frappe-ui/list'
import dayjs from 'dayjs'

type Issue = { name: string; title: string; status: string; modified: string }

const rows = ref<Issue[]>([])
const loading = ref(true)

// No server. Hold the fixture behind a short timer so the skeleton is real.
onMounted(() =>
  setTimeout(() => {
    rows.value = [
      { name: '1', title: 'Sidebar collapses on reload', status: 'open', modified: '2026-08-24' },
      { name: '2', title: 'Empty state is missing', status: 'done', modified: '2026-08-21' },
    ]
    loading.value = false
  }, 600),
)

// Sort state is app code. The header cell only draws the direction you pass.
const direction = ref<'asc' | 'desc'>('desc')
function toggleSort() {
  direction.value = direction.value === 'asc' ? 'desc' : 'asc'
  const factor = direction.value === 'desc' ? -1 : 1
  rows.value = [...rows.value].sort((a, b) => factor * a.modified.localeCompare(b.modified))
}

const themeFor = (s: string) =>
  ({ open: 'blue', done: 'green', error: 'red' })[s] ?? 'gray'

const showNew = ref(false)
const form = ref({ title: '', status: 'open' })

function create() {
  rows.value.unshift({
    name: String(rows.value.length + 1),
    ...form.value,
    modified: dayjs().format('YYYY-MM-DD'),
  })
  showNew.value = false
  form.value = { title: '', status: 'open' }
  toast.success('Issue created')
}
</script>

<template>
  <PageHeader>
    <h1 class="text-2xl text-ink-gray-9">Issues</h1>
    <Button
      variant="solid"
      theme="gray"
      icon-left="lucide-plus"
      label="New issue"
      class="ml-auto"
      @click="showNew = true"
    />
  </PageHeader>

  <div class="px-3 pt-5 pb-10 sm:px-5">
    <List :columns="['minmax(0,1fr)', '8rem', '8rem']" :row-height="44">
      <ListHeader>
        <ListHeaderCell>Title</ListHeaderCell>
        <ListHeaderCell>Status</ListHeaderCell>
        <ListHeaderCellSort :direction="direction" class="justify-end" @click="toggleSort">
          Updated
        </ListHeaderCellSort>
      </ListHeader>
      <ListRows :items="rows" v-slot="{ item }">
        <ListRow :to="`/issues/${item.name}`">
          <ListCell>
            <span class="truncate text-base text-ink-gray-8">{{ item.title }}</span>
          </ListCell>
          <ListCell>
            <Badge :label="item.status" :theme="themeFor(item.status)" variant="subtle" />
          </ListCell>
          <ListCell class="justify-end">
            <span class="text-sm text-ink-gray-5">{{ dayjs(item.modified).fromNow() }}</span>
          </ListCell>
        </ListRow>
      </ListRows>
    </List>

    <div v-if="!loading && !rows.length" class="flex flex-col items-center gap-3 py-16 text-center">
      <div class="rounded-full bg-surface-gray-2 p-3 text-ink-gray-5">
        <span class="lucide-inbox size-6" aria-hidden="true" />
      </div>
      <p class="text-base text-ink-gray-7">No issues yet</p>
      <p class="text-sm text-ink-gray-5">Create one to get started.</p>
    </div>
  </div>

  <Dialog v-model:open="showNew" title="New issue">
    <div class="space-y-4">
      <FormControl v-model="form.title" label="Title" required />
      <FormControl
        v-model="form.status"
        type="select"
        label="Status"
        :options="[
          { label: 'Open', value: 'open' },
          { label: 'Done', value: 'done' },
        ]"
      />
      <div class="flex justify-end gap-2 pt-2">
        <Button label="Cancel" @click="showNew = false" />
        <Button variant="solid" theme="gray" label="Create" @click="create" />
      </div>
    </div>
  </Dialog>
</template>
```

### `src/pages/IssueDetail.vue`

`props: true` in the route hands the URL parameter in as a prop.

```vue
<script setup lang="ts">
import { Badge, Breadcrumbs, PageHeader } from 'frappe-ui'

defineProps<{ id: string }>()
</script>

<template>
  <PageHeader>
    <Breadcrumbs :items="[{ label: 'Issues', route: { path: '/' } }, { label: `#${id}` }]" />
  </PageHeader>

  <div class="mx-auto max-w-[940px] px-3 pt-5 pb-10 sm:px-5">
    <div class="flex items-center gap-3">
      <h1 class="text-2xl text-ink-gray-9">Sidebar collapses on reload</h1>
      <Badge label="open" theme="blue" variant="subtle" />
    </div>
    <p class="mt-3 text-p-base text-ink-gray-7">
      Collapsing the sidebar and reloading brings it back expanded.
    </p>
  </div>
</template>
```

## 8. What does not exist

**There is no server and no backend.** Never import or call `useList`,
`useDoc`, `useCall`, `useDoctype`, `useNewDoc`, `createResource`,
`createListResource`, `createDocumentResource`, `frappeRequest` or `call`.
They are exported from `frappe-ui`, so they compile, and then they throw at
run time. Data lives in `ref`s.

Never use `fetch`, `XMLHttpRequest`, `axios`, or a WebSocket. There is nothing
to talk to.

**There is no build.** No Vite, no `vite.config`, no plugins, no
`package.json`, no `npm install`, no PostCSS, no `tailwind.config`, no CSS
files of your own. Tailwind is already configured with the frappe-ui preset.

**There is no entry file.** No `main.ts`, no `index.html`, no `createApp`.
See section 1.

**There is no type checking.** TypeScript annotations are stripped and thrown
away. A wrong type is silent. A syntax error is fatal.

**There is no `localStorage` you own,** and no theme control. Sketch sets
`data-theme`. See rule 10.

**There is no `frappe-ui/experimental`.** `Accordion`, `Calendar`,
`FloatingWindow`, `MultiEmailInput` and `CodeEditor` are not available.
