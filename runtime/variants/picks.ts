// The Demo picks a live-page comment was made on: which option each variant set showed and which value each page state
// held. A comment saves them so that, later, a person can see what it was about, and the page can be put back the same way.
// Plain data in the anchor (sketch/comments.py `clean_picks`); a set or state that has since gone is simply skipped.
import { choices, currentOf, idOf, isChoice, mirrorSets, mirrorStates, onPage, sets, stateOf, stateValues, states } from './state'

export type DemoPick = {
  kind: 'set' | 'state'
  // The matched route record's path the set or state belongs to, and '' for an app-wide state.
  path: string
  key: string
  label: string
  // The option's value, and its words.
  option: string
  optionLabel: string
  // The option is the first one, the one the page opens on.
  default: boolean
}

// What the Demo shows now on the page `route` shows.
export function currentPicks(route: any): DemoPick[] {
  const out: DemoPick[] = []
  for (const s of sets) {
    const options = s.options()
    if (!onPage(route, s.path) || !isChoice(options)) continue
    const v = currentOf(s) ?? ''
    out.push({ kind: 'set', path: s.path, key: s.key, label: s.label, option: v, optionLabel: options.find((o) => o.value === v)?.label ?? v, default: v === options[0]?.value })
  }
  for (const s of Object.values(states)) {
    if (!onPage(route, s.path)) continue
    const v = stateOf(s)
    out.push({ kind: 'state', path: s.path, key: s.key, label: s.label, option: v, optionLabel: v, default: v === s.options[0] })
  }
  return out
}

const setOf = (p: DemoPick) => sets.find((s) => s.path === p.path && s.key === p.key)
const stateOfPick = (p: DemoPick) => states[idOf(p.path, p.key)]

// Whether the pick's set or state is on the page now, with that option to choose.
const reachable = (p: DemoPick) =>
  p.kind === 'set' ? !!setOf(p)?.options().some((o) => o.value === p.option) : !!stateOfPick(p)?.options.includes(p.option)

// True when every pick that can still be shown is showing, so a comment with none is always "shown".
export function picksShown(picks: DemoPick[] | undefined): boolean {
  return (picks ?? []).every((p) => {
    if (!reachable(p)) return true
    return p.kind === 'set' ? currentOf(setOf(p)!) === p.option : stateOf(stateOfPick(p)!) === p.option
  })
}

// True once the page has registered every set and state a comment names (it is still mounting before that).
export const picksAvailable = (picks: DemoPick[] | undefined) => (picks ?? []).every(reachable)

// Put the Demo on these picks. The URL follows.
export function applyPicks(picks: DemoPick[] | undefined, router: any) {
  for (const p of picks ?? []) {
    if (!reachable(p)) continue
    const id = idOf(p.path, p.key)
    if (p.kind === 'set') choices[id] = p.option
    else stateValues[id] = p.option
  }
  mirrorSets(router)
  mirrorStates(router)
}

// "Donut", "Donut · Error": the picks that are not the defaults, in words. Empty when the comment was made on the defaults.
export function picksWords(picks: DemoPick[] | undefined): string {
  return (picks ?? [])
    .filter((p) => !p.default)
    .map((p) => p.optionLabel || p.option)
    .join(' · ')
}
