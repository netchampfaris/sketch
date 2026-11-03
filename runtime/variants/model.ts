// The Demo pill's rows as plain data, for the Viewer shell, which draws the pill over this frame (runtime/shell/DemoPill.vue).
// The same rows Pills.vue shows: the app-wide states (Role), this page's states, and this page's sets that have a choice,
// in page order (top to bottom, then left to right). The order is worked out when the shell asks (`measureDemo`, as the
// card opens) and when the page or its sets change, never as a person picks, so rows hold still under the pointer.
import { shallowRef } from 'vue'
import { hasItems } from './picker'
import { pagesModel } from './snapshot'
import {
  choices,
  currentOf,
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

const here = (route: any) => sets.filter((s) => onPage(route, s.path) && isChoice(s.options()))

// Sort the rows by where their sets sit, and measure them for the outline.
export function measureDemo(route: any) {
  const list = here(route)
  const at = (s: VSet) => rectOf(s) ?? { x: 0, y: 1e9, w: 0, h: 0 }
  order.value = [...list].sort((a, b) => at(a).y - at(b).y || at(a).x - at(b).x).map(setId)
  boxes.value = Object.fromEntries(list.map((s) => [setId(s), rectOf(s)]))
  sortedFor = `${route.path}|${list.length}`
}

// The canvas view that shows this set, as the Demo card's foot opens it: `set:<page slug>/<key>`.
function viewOf(router: any, s: VSet) {
  const record = (router.options.routes as any[]).find((r) => r.path === s.path)
  return `set:${record ? slugOfRoute(record) : ''}/${s.key}`
}

export function demoModel(router: any) {
  const route = router.currentRoute.value
  const list = here(route)
  // A new page, or a set that came or went: sort again once the page has drawn it (Pills.vue did the same).
  if (`${route.path}|${list.length}` !== sortedFor) queueMicrotask(() => requestAnimationFrame(() => measureDemo(router.currentRoute.value)))
  const o = order.value
  const rows = [...list].sort((a, b) => (o.indexOf(setId(a)) + 1 || 99) - (o.indexOf(setId(b)) + 1 || 99))
  const pageStates = Object.values(states).filter((s) => onPage(route, s.path))
  const canOpen = rows.some((s) => s.path !== '') || pageStates.some((s) => s.path !== '') || !pagesModel.value || pagesModel.value.some(hasItems)
  return {
    sets: rows.map((s) => ({
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
    states: pageStates.map((s) => ({ id: `state:${idOf(s.path, s.key)}`, label: s.label, path: s.path, value: stateOf(s), options: [...s.options] })),
    canOpen,
  }
}

// The shell picked an option of a row: the set or state shows it, and the URL follows. Anything it does not name is dropped.
export function setDemo(id: string, value: string, router: any) {
  const route = router.currentRoute.value
  if (id.startsWith('set:')) {
    const s = here(route).find((x) => setId(x) === id.slice(4))
    if (!s || !s.options().some((o) => o.value === value)) return
    choices[setId(s)] = value
    mirrorSets(router)
  } else if (id.startsWith('state:')) {
    const s = states[id.slice(6)]
    if (!s || !onPage(route, s.path) || !s.options.includes(value)) return
    stateValues[id.slice(6)] = value
    mirrorStates(router)
  }
}
