// What the canvas can show, and how a pick is written in the URL: `set:<page>/<key>`, `state:<name>`,
// `page:<path>`. Everything here is plain data in, plain data out.
import type { PageModel } from './layout'
import { slugOf } from './state'

export const FIXED = ['First use', 'No results', 'Loading', 'Error', 'Long text', 'Many items', 'Limited permissions']

export type Pick =
  | { kind: 'set'; page: PageModel; key: string }
  | { kind: 'state'; name: string }
  | { kind: 'page'; page: PageModel }
// `options` on a set row: the values of its options, for the dot that says some of them are new.
export type PickItem = { value: string; label: string; sub?: string; short: string; complete?: boolean; group: 'sets' | 'states' | 'pages'; options?: string[] }

const count = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`
// A state exists on a page when one of its non-default options carries the name.
const namesOf = (p: PageModel) => new Set(p.states.flatMap((s) => s.options.slice(1)))
export const hasItems = (p: PageModel) => p.states.length > 0 || p.sets.length > 0
const stateCount = (p: PageModel) => p.states.reduce((n, s) => n + s.options.length - 1, 0)

export function stateNames(pages: PageModel[]): string[] {
  const all = new Set(pages.flatMap((p) => [...namesOf(p)]))
  const fixed = FIXED.filter((n) => all.has(n))
  const rest = [...all].filter((n) => !FIXED.includes(n)).sort((a, b) => a.localeCompare(b))
  return [...fixed, ...rest]
}

export const valueOfPick = (p: Pick) =>
  p.kind === 'set' ? `set:${p.page.slug}/${p.key}` : p.kind === 'state' ? `state:${slugOf(p.name)}` : `page:${p.page.path}`

export function pickItems(pages: PageModel[]): PickItem[] {
  const withStates = pages.filter((p) => p.states.length)
  const sets = pages.flatMap((p) =>
    p.sets.map((s) => ({ value: `set:${p.slug}/${s.key}`, label: s.label, sub: p.title, short: String(s.options.length), group: 'sets' as const, options: s.options.map((o) => o.value) })),
  )
  const states = stateNames(pages).map((n) => {
    const k = pages.filter((p) => namesOf(p).has(n)).length
    return { value: `state:${slugOf(n)}`, label: n, short: `${k}/${withStates.length}`, complete: k === withStates.length, group: 'states' as const }
  })
  const pg = withStates.map((p) => ({ value: `page:${p.path}`, label: p.title, short: count(stateCount(p), 'state'), group: 'pages' as const }))
  return [...sets, ...states, ...pg]
}

const pageSummary = (p: PageModel) => count(stateCount(p), 'state')

export function parsePick(raw: string, pages: PageModel[]): Pick | null {
  const i = raw.indexOf(':')
  if (i < 0) return null
  const kind = raw.slice(0, i), rest = raw.slice(i + 1)
  if (kind === 'set') {
    const [slug, key] = rest.split('/')
    const page = pages.find((p) => p.slug === slug)
    return page?.sets.some((s) => s.key === key) ? { kind: 'set', page, key } : null
  }
  if (kind === 'state') {
    const name = stateNames(pages).find((n) => slugOf(n) === slugOf(rest))
    return name ? { kind: 'state', name } : null
  }
  if (kind === 'page') {
    const page = pages.find((p) => p.path === rest)
    return page?.states.length ? { kind: 'page', page } : null
  }
  return null
}

// First open with nothing remembered: the current page's first set, else the current page, else the first item.
export function fallbackPick(pages: PageModel[], path: string): string | null {
  const here = pages.find((p) => p.path === path)
  if (here?.sets.length) return `set:${here.slug}/${here.sets[0].key}`
  if (here?.states.length) return `page:${here.path}`
  return pickItems(pages)[0]?.value ?? null
}

export function pickLabel(p: Pick) {
  return p.kind === 'set' ? (p.page.sets.find((s) => s.key === p.key)?.label ?? p.key) : p.kind === 'state' ? p.name : p.page.title
}

export function pickSummary(p: Pick, pages: PageModel[]) {
  if (p.kind === 'set') return `${p.page.title} · ${count(p.page.sets.find((s) => s.key === p.key)?.options.length ?? 0, 'option')}`
  if (p.kind === 'state') {
    const withStates = pages.filter((x) => x.states.length)
    return `${withStates.filter((x) => namesOf(x).has(p.name)).length} of ${withStates.length} pages`
  }
  return pageSummary(p.page)
}
