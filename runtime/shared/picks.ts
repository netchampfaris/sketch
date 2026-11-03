// The Demo picks a live-page comment was made on, and the words for them: the pure half of
// runtime/variants/picks.ts. The Viewer shell reads them from the frame's `demo` report (the sets and
// states mounted now, with the option each shows) and works out the same answers the page would.

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

// One mounted set or registered state: what it shows now, and what it may show.
export type DemoEntry = { kind: 'set' | 'state'; path: string; key: string; value: string; options: string[] }

const entryOf = (entries: DemoEntry[], p: DemoPick) => entries.find((e) => e.kind === p.kind && e.path === p.path && e.key === p.key)

// Whether the pick's set or state is on the page now, with that option to choose.
export const reachableIn = (entries: DemoEntry[], p: DemoPick) => !!entryOf(entries, p)?.options.includes(p.option)

// True when every pick that can still be shown is showing, so a comment with none is always "shown".
export const picksShownIn = (entries: DemoEntry[], picks: DemoPick[] | undefined) =>
  (picks ?? []).every((p) => !reachableIn(entries, p) || entryOf(entries, p)!.value === p.option)

// "Donut", "Donut · Error": the picks that are not the defaults, in words. Empty when the comment was made on the defaults.
export function picksWords(picks: DemoPick[] | undefined): string {
  return (picks ?? [])
    .filter((p) => !p.default)
    .map((p) => p.optionLabel || p.option)
    .join(' · ')
}
