// State shared by the component, the pill and annotate. It lives in its own module so the two
// components can import it without importing each other.
import { reactive, shallowReactive, shallowRef } from 'vue'

export type VSet = {
  key: string
  label: string
  path: string
  options: () => { value: string; label: string }[]
  // The slot's top-level elements, in document order.
  elements: () => Element[]
}

// Mounted sets: a set is listed while it is mounted, so the pill shows the current page's sets.
export const sets = shallowReactive<VSet[]>([])
// Choices outlive the page: `route.path + key` -> option. Going away and back keeps them.
export const choices = reactive<Record<string, string>>({})
// Sets the owner has pressed Keep on, until reload.
export const kept = reactive<Record<string, string>>({})

export const idOf = (s: { path: string; key: string }) => `${s.path}::${s.key}`
export const currentOf = (s: VSet) => {
  const o = s.options()
  const c = choices[idOf(s)]
  return o.some((x) => x.value === c) ? c : o[0]?.value
}

// Annotate registers this; without it (a Guest, or annotate failed to load) Keep never renders.
export const keepHandler = shallowRef<((el: Element, text: string) => void) | null>(null)
export const setKeepHandler = (fn: ((el: Element, text: string) => void) | null) => {
  keepHandler.value = fn
}

// Mirror non-default picks into one query param as `<key>.<option>`, comma separated, with no new
// history entry. Entries for keys not handled here (another `v`, such as a cache-buster) are left alone.
function mirrorParam(router: any, route: any, param: 'v' | 's', own: Set<string>, chosen: string[]) {
  const was = fromQueryRaw(route, param)
  const foreign = was.split(',').filter((p) => p && !own.has(p.split('.')[0]))
  const next = [...foreign, ...chosen].join(',')
  if (next === was) return
  const query = { ...route.query }
  if (next) query[param] = next
  else delete query[param]
  router.replace({ query })
}
const fromQueryRaw = (route: any, param: string) => String([route.query[param]].flat()[0] ?? '')
// The option a link names for this key, as in #/inbox?v=leave-card.timeline.
export const fromQuery = (route: any, param: 'v' | 's', key: string) =>
  fromQueryRaw(route, param).split(',').find((p) => p.startsWith(key + '.'))?.slice(key.length + 1)

export function mirror(router: any, route: any) {
  const mine = sets.filter((s) => s.path === route.path)
  const chosen = mine.filter((s) => currentOf(s) !== s.options()[0]?.value).map((s) => `${s.key}.${currentOf(s)}`)
  mirrorParam(router, route, 'v', new Set(mine.map((s) => s.key)), chosen)
}

// Demo states (personas, phases): global, keyed by the name's slug. Listed while any caller is mounted.
export type DState = { key: string; label: string; options: string[]; count: number }
export const states = reactive<Record<string, DState>>({})
// The chosen label per key. Absent means the first option.
export const stateValues = reactive<Record<string, string>>({})
export const stateOf = (s: DState) => (s.options.includes(stateValues[s.key]) ? stateValues[s.key] : s.options[0])

export const slugOf = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
export function mirrorStates(router: any, route: any) {
  const live = Object.values(states)
  const chosen = live.filter((s) => stateOf(s) !== s.options[0]).map((s) => `${s.key}.${slugOf(stateOf(s))}`)
  mirrorParam(router, route, 's', new Set(live.map((s) => s.key)), chosen)
}
