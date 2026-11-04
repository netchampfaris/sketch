// The Demo picks a live-page comment was made on: which option each variant set showed and which value each page state
// held. A comment saves them so that, later, a person can see what it was about, and the page can be put back the same way.
// Plain data in the anchor (sketch/comments.py `clean_picks`); a set or state that has since gone is simply skipped.
// The shell reads them from what the frame agent reports and asks for them back (`picks:apply`); the frame does the rest here.
import { choices, currentOf, defaultOf, idOf, isChoice, mirrorSets, mirrorStates, onPage, sets, stateOf, stateValues, states } from './state'
import type { DemoEntry, DemoPick } from '../shared/picks'

export type { DemoPick }

// What the Demo shows now on the page `route` shows.
export function currentPicks(route: any): DemoPick[] {
  const out: DemoPick[] = []
  for (const s of sets) {
    const options = s.options()
    if (!onPage(route, s.path) || !isChoice(options)) continue
    const v = currentOf(s) ?? ''
    out.push({ kind: 'set', path: s.path, key: s.key, label: s.label, option: v, optionLabel: options.find((o) => o.value === v)?.label ?? v, default: v === defaultOf(options) })
  }
  for (const s of Object.values(states)) {
    if (!onPage(route, s.path)) continue
    const v = stateOf(s)
    out.push({ kind: 'state', path: s.path, key: s.key, label: s.label, option: v, optionLabel: v, default: v === s.options[0] })
  }
  return out
}

// What a pick needs to be put back: which set or state, and the option (the shell's `picks:apply` sends no more).
type PickRef = Pick<DemoPick, 'kind' | 'path' | 'key' | 'option'>

const setOf = (p: PickRef) => sets.find((s) => s.path === p.path && s.key === p.key)
const stateOfPick = (p: PickRef) => states[idOf(p.path, p.key)]

// Whether the pick's set or state is on the page now, with that option to choose.
const reachable = (p: PickRef) =>
  p.kind === 'set' ? !!setOf(p)?.options().some((o) => o.value === p.option) : !!stateOfPick(p)?.options.includes(p.option)

// Put the Demo on these picks. The URL follows.
export function applyPicks(picks: PickRef[] | undefined, router: any) {
  for (const p of picks ?? []) {
    if (!reachable(p)) continue
    const id = idOf(p.path, p.key)
    if (p.kind === 'set') choices[id] = p.option
    else stateValues[id] = p.option
  }
  mirrorSets(router)
  mirrorStates(router)
}

// Every mounted set and registered state, with what it shows now: the Viewer shell's frame agent reports this,
// so the shell can tell whether a comment's picks are on show (runtime/shared/picks.ts).
export function demoEntries(): DemoEntry[] {
  return [
    ...sets.map((s) => ({ kind: 'set' as const, path: s.path, key: s.key, value: currentOf(s) ?? '', options: s.options().map((o) => o.value) })),
    ...Object.values(states).map((s) => ({ kind: 'state' as const, path: s.path, key: s.key, value: stateOf(s), options: [...s.options] })),
  ]
}
