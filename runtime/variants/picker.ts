// What the canvas can show, and how a pick is written in the URL: `set:<page>/<key>`, `page:<path>`, and
// `opt:<page>/<set>/<option>` for one option's component states. Everything here is plain data in, plain data out.
import type { PageModel } from './layout'

export type Pick =
  | { kind: 'set'; page: PageModel; key: string }
  | { kind: 'page'; page: PageModel }
  | { kind: 'opt'; page: PageModel; key: string; value: string }
// `options` on a set row: the values of its options, for the dot that says some of them are new.
export type PickItem = { value: string; label: string; sub?: string; short: string; group: 'sets' | 'pages'; options?: string[] }

const count = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`
export const hasItems = (p: PageModel) => p.states.length > 0 || p.sets.length > 0
const stateCount = (p: PageModel) => p.states.reduce((n, s) => n + s.options.length - 1, 0)

export const valueOfPick = (p: Pick) =>
  p.kind === 'set' ? `set:${p.page.slug}/${p.key}` : p.kind === 'opt' ? `opt:${p.page.slug}/${p.key}/${p.value}` : `page:${p.page.path}`

export function pickItems(pages: PageModel[]): PickItem[] {
  const sets = pages.flatMap((p) =>
    p.sets.map((s) => ({ value: `set:${p.slug}/${s.key}`, label: s.label, sub: p.title, short: String(s.options.length), group: 'sets' as const, options: s.options.map((o) => o.value) })),
  )
  const pg = pages.filter((p) => p.states.length).map((p) => ({ value: `page:${p.path}`, label: p.title, short: count(stateCount(p), 'state'), group: 'pages' as const }))
  return [...sets, ...pg]
}

// A value that names nothing the canvas has (an old `state:` link) is no pick, and the canvas shows its default view.
export function parsePick(raw: string, pages: PageModel[]): Pick | null {
  const i = raw.indexOf(':')
  if (i < 0) return null
  const kind = raw.slice(0, i), rest = raw.slice(i + 1)
  if (kind === 'set') {
    const [slug, key] = rest.split('/')
    const page = pages.find((p) => p.slug === slug)
    return page?.sets.some((s) => s.key === key) ? { kind: 'set', page, key } : null
  }
  if (kind === 'opt') {
    const [slug, key, ...value] = rest.split('/')
    const page = pages.find((p) => p.slug === slug)
    const v = value.join('/')
    return page?.sets.find((s) => s.key === key)?.options.some((o) => o.value === v) ? { kind: 'opt', page, key, value: v } : null
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
  return p.kind === 'page' ? p.page.title : (p.page.sets.find((s) => s.key === p.key)?.label ?? p.key)
}

export function pickSummary(p: Pick) {
  if (p.kind === 'set') return `${p.page.title} · ${count(p.page.sets.find((s) => s.key === p.key)?.options.length ?? 0, 'option')}`
  if (p.kind === 'page') return count(stateCount(p.page), 'state')
  return ''
}
