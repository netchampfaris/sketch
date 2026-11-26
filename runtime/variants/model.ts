// The Demo pill's rows as plain data, for the Viewer shell, which draws the pill over this frame (runtime/shell/DemoPill.vue).
// The rows: the app-wide states (Role), this page's states, and this page's sets that have a choice,
// in page order (top to bottom, then left to right). The order is worked out when the shell asks (`measureDemo`, as the
// card opens) and when the page or its sets change, never as a person picks, so rows hold still under the pointer.
import { shallowRef } from 'vue'
import { hasItems } from './picker'
import { pagesModel } from './snapshot'
import {
  choices,
  currentOf,
  found,
  idOf,
  isChoice,
  mirrorSets,
  mirrorStates,
  onPage,
  setId,
  sets,
  slugOfRoute,
  stateOf,
  stateValues,
  states,
  type VSet,
} from './state'

type Rect = { x: number; y: number; w: number; h: number }

// The set's box on the page now: what the shell outlines while its row is hovered.
const rectOf = (s: VSet): Rect | null => {
  const rs = s.elements().map((e) => e.getBoundingClientRect()).filter((r) => r.width || r.height)
  if (!rs.length) return null
  const x = Math.min(...rs.map((r) => r.left)), y = Math.min(...rs.map((r) => r.top))
  return { x, y, w: Math.max(...rs.map((r) => r.right)) - x, h: Math.max(...rs.map((r) => r.bottom)) - y }
}

const order = shallowRef<string[]>([])
const boxes = shallowRef<Record<string, Rect | null>>({})
let sortedFor = ''

// One row of the pill: a set, or the copies of one set that are on this page under two page keys (a component used on
// the page and in an app-wide dialog over it). One pick drives every copy. The lead names the row: a copy of the page's
// own first, so the row keeps its id while the dialog opens and closes.
type Row = { lead: VSet; copies: VSet[] }
const here = (route: any): Row[] => {
  const mounted = sets.filter((s) => onPage(route, s.path) && isChoice(s.options()))
  // Behind a closed dialog: listed on every page the dialog opens from, after the sets on screen.
  const hidden = found.value.filter((s) => onPage(route, s.path) && isChoice(s.options()) && !mounted.some((m) => setId(m) === setId(s)))
  const rows = new Map<string, VSet[]>()
  for (const s of [...mounted, ...hidden]) {
    const k = s.file ? `${s.file}::${s.key}` : setId(s)
    rows.set(k, [...(rows.get(k) ?? []), s])
  }
  return [...rows.values()].map((copies) => ({ lead: copies.find((s) => s.path !== '') ?? copies[0], copies }))
}
const rowId = (r: Row) => setId(r.lead)
// Where a row's set sits on screen: its first copy that is drawn. Null for one behind a closed dialog.
const rectOfRow = (r: Row) => r.copies.map(rectOf).find(Boolean) ?? null

// Sort the rows by where their sets sit, and measure them for the outline. A row not on screen sorts last.
export function measureDemo(route: any) {
  const list = here(route)
  const rects = new Map(list.map((r) => [rowId(r), rectOfRow(r)]))
  const at = (r: Row) => rects.get(rowId(r)) ?? { x: 0, y: 1e9, w: 0, h: 0 }
  order.value = [...list].sort((a, b) => at(a).y - at(b).y || at(a).x - at(b).x).map(rowId)
  boxes.value = Object.fromEntries(rects)
  sortedFor = sortKey(route, list)
}
// The rows' make-up: a set that came or went, or a dialog that opened over the page, sorts them again.
const sortKey = (route: any, list: Row[]) => `${route.path}|${list.map((r) => r.copies.map((s) => `${setId(s)}${sets.includes(s) ? '' : '?'}`).join('+')).join(',')}`

// The canvas view that shows this set, as the Demo card's foot opens it: `set:<page slug>/<key>`.
function viewOf(router: any, s: VSet) {
  const record = (router.options.routes as any[]).find((r) => r.path === s.path)
  return `set:${record ? slugOfRoute(record) : ''}/${s.key}`
}

export function demoModel(router: any) {
  const route = router.currentRoute.value
  const list = here(route)
  // A new page, or a set that came or went: sort again once the page has drawn it.
  if (sortKey(route, list) !== sortedFor) queueMicrotask(() => requestAnimationFrame(() => measureDemo(router.currentRoute.value)))
  const o = order.value
  const rows = [...list].sort((a, b) => (o.indexOf(rowId(a)) + 1 || 999) - (o.indexOf(rowId(b)) + 1 || 999))
  const pageStates = Object.values(states).filter((s) => onPage(route, s.path))
  const canOpen = rows.some((r) => r.lead.path !== '') || pageStates.some((s) => s.path !== '') || !pagesModel.value || pagesModel.value.some(hasItems)
  return {
    sets: rows.map(({ lead: s }) => ({
      id: `set:${setId(s)}`,
      key: s.key,
      name: s.name,
      label: s.label,
      file: s.file,
      path: s.path,
      value: currentOf(s) ?? '',
      view: viewOf(router, s),
      rect: boxes.value[setId(s)] ?? null,
      options: s.options().map((x) => ({ value: x.value, label: x.label, author: x.author ?? '' })),
    })),
    states: pageStates.map((s) => ({
      id: `state:${idOf(s.path, s.key)}`,
      label: s.label,
      path: s.path,
      value: stateOf(s),
      options: [...s.options],
      ...(s.groups ? { groups: s.groups.map((g) => ({ title: g.title, options: [...g.options] })) } : {}),
    })),
    canOpen,
  }
}

// The shell picked an option of a row: the set or state shows it, and the URL follows. Anything it does not name is dropped.
export function setDemo(id: string, value: string, router: any) {
  const route = router.currentRoute.value
  if (id.startsWith('set:')) {
    const row = here(route).find((r) => r.copies.some((x) => setId(x) === id.slice(4)))
    if (!row || !row.lead.options().some((o) => o.value === value)) return
    for (const s of row.copies) choices[setId(s)] = value
    mirrorSets(router)
  } else if (id.startsWith('state:')) {
    const s = states[id.slice(6)]
    if (!s || !onPage(route, s.path) || !s.options.includes(value)) return
    stateValues[id.slice(6)] = value
    mirrorStates(router)
  }
}
