// State shared by Variants, useDemoState, the Demo pill and the canvas. It lives in its own module so none of
// them has to import another. A state called outside any RouterView (App.vue) is app-wide; inside one it
// belongs to that page.
import { inject, reactive, shallowReactive, shallowRef } from 'vue'
import type { InjectionKey } from 'vue'
import { matchedRouteKey } from 'vue-router'

// `author` is the username of the teammate who made the option, and absent for the owner's own.
// `isDefault` marks the set's default, wherever it sits.
export type Opt = { value: string; label: string; author?: string; isDefault?: boolean }
// The option a set shows when nothing is picked.
export const defaultOf = (o: readonly Opt[]) => (o.find((x) => x.isDefault) ?? o[0])?.value
export type VSet = {
  key: string
  label: string
  // The `name` the page wrote on <Variants name="…">. `label` can carry a " 2" for a repeated name.
  name: string
  // The source file the <Variants> tag is written in, as the Prototype's own path. Empty when unknown.
  file: string
  // The matched route record's path, and '' for a set outside any RouterView.
  path: string
  options: () => Opt[]
  // The slot's top-level elements, in document order: of the first copy in the page, when the tag is drawn many times.
  elements: () => Element[]
  // Each copy's own `elements`, while it is mounted.
  copies: (() => Element[])[]
  // True when the set is the page: the root of the routed page component. Its tile shows the whole window.
  page: () => boolean
}
// A heading over some of a state's options, when the caller grouped them.
export type DGroup = { title: string; options: string[] }
// `path` is the matched route record's path for a page state, and '' for an app-wide state. `options` is always the
// flat list, first one the default; `groups` is there only when the caller wrote them in groups. `of` is set on a
// component state ("Supplier card/Compact"): it is drawn on the canvas and never listed in the live registry.
export type DState = { key: string; label: string; path: string; options: string[]; count: number; groups?: DGroup[]; of?: string }

// What a frame (an offscreen or live render of a page) is told, and where it reports.
// `inDialogs`, only where a frame asks for it (Discover.vue): the sets with a copy inside a frappe-ui Dialog.
export type Reg = { states: DState[]; sets: VSet[]; inDialogs?: VSet[] }
export type Sandbox = {
  states: Record<string, string>
  variants: Record<string, string>
  reg: Reg
  live: boolean
}
export const sandboxKey: InjectionKey<Sandbox> = Symbol('sketch-sandbox')

// What `useDemoState` was given: a flat list, or an object of groups. The first option of the first group is the default.
export function readOptions<T extends string>(input: readonly T[] | Record<string, readonly T[]>): { options: T[]; groups?: DGroup[] } {
  if (Array.isArray(input)) return { options: [...input] }
  const groups = Object.entries(input).map(([title, options]) => ({ title, options: [...options] }))
  return { options: groups.flatMap((g) => g.options) as T[], groups }
}

export const slugOf = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
export const idOf = (path: string, key: string) => `${path}::${key}`
export const setId = (s: { path: string; key: string }) => idOf(s.path, s.key)

// A component state's `of`: a set's label and an option's label, "Supplier card/Compact".
export const ofOption = (setLabel: string, optLabel: string) => `${setLabel}/${optLabel}`
// A state's key. One declared with `of` ends in it: "state@supplier-card-compact".
export const stateKeyOf = (name: string, of?: string) => (of ? `${slugOf(name)}@${slugOf(of)}` : slugOf(name))
// True when `of` (as written, or as the slug in a key) names this option of this set.
export const belongsTo = (of: string, set: { label: string }, opt: { label: string }) =>
  !!of && slugOf(of) === slugOf(ofOption(set.label, opt.label))

// `scan-first` and `scanFirst` both read "Scan first"; a few acronyms keep their capitals.
export const humanise = (s: string) => {
  const t = s.replace(/([a-z])([A-Z])/g, '$1 $2').replace(/[-_]+/g, ' ').toLowerCase()
  return (t.charAt(0).toUpperCase() + t.slice(1)).replace(/\b(kpi|id|api|ui)\b/gi, (m) => m.toUpperCase())
}

// null from `matchedRouteKey` means: not inside any RouterView, so app-wide.
export function pageKeyOf(): string {
  const m = inject(matchedRouteKey, null) as { value?: { path?: string } } | null
  return m ? (m.value?.path ?? '/') : ''
}
// True when a state or set belongs on the page `route` shows: app-wide, or one of its matched records.
export const onPage = (route: any, path: string) => path === '' || route.matched.some((m: any) => m.path === path)

// A set with one option left (after Keep only this) keeps its wrapper, so editors can add again, but there is
// nothing to pick: the Demo card and Browse leave it out until it has two or more.
export const isChoice = (options: readonly unknown[]) => options.length >= 2

// Mounted sets, listed while mounted. Choices outlive the page: `path::key` -> option value.
export const sets = shallowReactive<VSet[]>([])
export const choices = reactive<Record<string, string>>({})
export const currentOf = (s: VSet) => {
  const o = s.options()
  const c = choices[setId(s)]
  return o.some((x) => x.value === c) ? c : defaultOf(o)
}
// Demo states, listed while a caller is mounted. Values are kept per page for the session.
export const states = reactive<Record<string, DState>>({})
export const stateValues = reactive<Record<string, string>>({})
export const stateOf = (s: DState) => {
  const v = stateValues[idOf(s.path, s.key)]
  return s.options.includes(v) ? v : s.options[0]
}

const fromQueryRaw = (route: any, param: string) => String([route.query[param]].flat()[0] ?? '')
// The option a link names for this key, as in #/inbox?v=leave-card.timeline.
export const fromQuery = (route: any, param: 'v' | 's', key: string) =>
  fromQueryRaw(route, param)
    .split(',')
    .find((p) => p.startsWith(key + '.'))
    ?.slice(key.length + 1)

// Mirror non-default picks into one query param as `<key>.<option>`, comma separated, with no new
// history entry. Keys this module has ever seen are replaced; anything else (another `v`, such as a
// cache-buster) is left alone.
function mirrorParam(router: any, param: 'v' | 's', known: Set<string>, chosen: string[]) {
  const route = router.currentRoute.value
  const was = fromQueryRaw(route, param)
  const foreign = was.split(',').filter((p) => p && !known.has(p.split('.')[0]))
  const next = [...foreign, ...chosen].join(',')
  if (next === was) return
  const query = { ...route.query }
  if (next) query[param] = next
  else delete query[param]
  router.replace({ query })
}
const knownS = new Set<string>()
const knownV = new Set<string>()

export function mirrorStates(router: any) {
  const route = router.currentRoute.value
  const mine = Object.values(states).filter((s) => onPage(route, s.path))
  mine.forEach((s) => knownS.add(s.key))
  const chosen = mine.filter((s) => stateOf(s) !== s.options[0]).map((s) => `${s.key}.${slugOf(stateOf(s))}`)
  mirrorParam(router, 's', knownS, chosen)
}
export function mirrorSets(router: any) {
  // A set behind a closed dialog is mirrored too, so a link opens the dialog on the option picked for it.
  const mine = setsOn(router.currentRoute.value)
  mine.forEach((s) => knownV.add(s.key))
  const chosen = mine.filter((s) => currentOf(s) !== defaultOf(s.options())).map((s) => `${s.key}.${currentOf(s)}`)
  // One set mounted twice (on the page and in a dialog over it) is one pick: once in the link.
  mirrorParam(router, 'v', knownV, [...new Set(chosen)])
}

// The sets on this page behind a closed dialog, as Discover.vue last found them. They are not drawn: no elements, so
// the Demo pill outlines nothing for them. A link that names an option for one is its pick, as it is for a mounted set.
export const found = shallowRef<VSet[]>([])
// One set drawn under two page keys (a component used on a page and in an app-wide dialog over it) is one row of the Demo
// pill, with one pick.
export const rowOf = (s: { path: string; key: string; file?: string }) => (s.file ? `${s.file}::${s.key}` : setId(s))
// Pick an option of a set on the page `route` shows. Every copy of its row follows, on screen or behind a closed dialog.
// `set` needs its `file` only while it is not on the page yet (Open page, from a canvas tile).
export function pickSet(route: any, set: { path: string; key: string; file?: string }, value: string) {
  const all = setsOn(route)
  const row = rowOf(all.find((s) => setId(s) === setId(set)) ?? set)
  choices[setId(set)] = value
  for (const s of all) if (rowOf(s) === row) choices[setId(s)] = value
}
// The sets of the page `route` shows: those on screen, then those behind a closed dialog, on every page it opens from.
export function setsOn(route: any): VSet[] {
  const mounted = sets.filter((s) => onPage(route, s.path))
  return [...mounted, ...found.value.filter((s) => onPage(route, s.path) && !mounted.some((m) => setId(m) === setId(s)))]
}
export function setFound(list: VSet[], router: any) {
  const route = router.currentRoute.value
  found.value = list.map((s) => {
    const o = s.options()
    return { key: s.key, label: s.label, name: s.name, file: s.file, path: s.path, options: () => o, elements: () => [], copies: [], page: () => false }
  })
  for (const s of found.value) {
    const opt = fromQuery(route, 'v', s.key)
    if (opt && !choices[setId(s)] && s.options().some((o) => o.value === opt)) choices[setId(s)] = opt
  }
  mirrorSets(router)
}

// Opening a link like #/requests?s=requests.loading: the name's slug picks the state, the option's slug
// picks the option.
export function applyStateLink(route: any, id: string, key: string, options: readonly string[]) {
  const named = fromQuery(route, 's', key)
  const opt = options.find((o) => slugOf(o) === named)
  if (opt) stateValues[id] = opt
}

// Opening and closing the canvas. Opening pushes `?canvas=` so Back closes it.
export const nav = { opener: null as HTMLElement | null, pushed: false }
export function openCanvas(router: any, id: string) {
  nav.opener = document.activeElement as HTMLElement | null
  nav.pushed = true
  router.push({ query: { ...router.currentRoute.value.query, canvas: id } })
}
export function closeCanvas(router: any) {
  if (nav.pushed) {
    nav.pushed = false
    router.back()
    return
  }
  const query = { ...router.currentRoute.value.query }
  delete query.canvas
  router.replace({ query })
}

// The page name: route meta.title, else the humanised component name.
export const titleOfRoute = (r: any): string =>
  r.meta?.title ?? humanise(r.component?.__name ?? r.components?.default?.__name ?? r.name?.toString() ?? (r.path.slice(1) || 'Home'))
export const slugOfRoute = (r: any) => slugOf(titleOfRoute(r))

let hooked = false
export function hookRouter(router: any) {
  if (hooked) return
  hooked = true
  // A navigation without the query puts it back, and drops the page we left.
  router.afterEach(() => setTimeout(() => { mirrorStates(router); mirrorSets(router) }, 0))
}
