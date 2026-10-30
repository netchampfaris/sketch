// Variants a teammate's agent added (src/variants/@name/*.vue) and variants the owner adopted (src/variants/adopted/*.vue).
// The Viewer finds them, compiles them in isolation and registers them here. A `<Variants>` set merges the ones that
// target it into its options. They never touch the owner's slots: one that fails to load fails in its own option.
import { reactive, shallowReactive } from 'vue'
import { slugOf, type Opt } from './state'

export type Extra = {
  // The file under src/variants/ without .vue: `@arohi/compact` or `adopted/compact`.
  value: string
  label: string
  // The username the folder (or the adopted registry) names. Never read from the file's own text.
  author: string
  // Exactly one of these two says where the option goes: a set's name, or a component's file.
  set: string
  component: string
  // An adopted variant the owner made the default of its set.
  lead: boolean
  // Evaluates the module (once) and returns the Vue component. Throws when the file's own code fails.
  load: () => unknown
}
export type Person = { name: string; image: string }
export type Editing = { name: string; user: string; owner: boolean; exp: string; sig: string }

export const extras = shallowReactive<Extra[]>([])
export const people = reactive<Record<string, Person>>({})
// What deleting a variant needs: set for the owner and for an invited editor, absent for everyone else.
export const editing = shallowReactive<{ value: Editing | null }>({ value: null })
// The Viewer's report hook, so a variant that failed shows in `check` as a warning.
export const failed = { report: (_e: Extra, _err: unknown) => {} }

export function registerExtras(list: Extra[], who: Record<string, Person>, report?: (e: Extra, err: unknown) => void) {
  extras.splice(0, extras.length, ...list)
  for (const k of Object.keys(people)) delete people[k]
  Object.assign(people, who)
  if (report) failed.report = report
}

export const personName = (username: string) => people[username]?.name || username

// When each option first appeared, as a version number (sketch/variant_order.py). Absent for a page with no history.
export type Seen = { slots?: Record<string, Record<string, Record<string, number>>>; extras?: Record<string, number>; files?: Record<string, number> }
export const seen = shallowReactive<{ value: Seen | null }>({ value: null })
export function registerSeen(data: Seen | null | undefined) {
  seen.value = data && typeof data === 'object' ? data : null
}

// A set's options in the order they first appeared, oldest first, whoever made them. Making one the default never
// moves it: exactly one option carries `isDefault`. That is an adopted variant that leads the set, else the slot the
// tag's `default` prop names, else the owner's first slot. What no version holds yet goes last; ties keep the owner's
// slots in source order, then the variants by file name (so adopting one, which moves its file, never reorders them).
export function mergeOptions(slotOptions: Opt[], set: { name: string; wrapper: boolean; file: string; default?: string }): Opt[] {
  const mine = extras.filter((e) => (set.wrapper ? e.component === set.file : !e.component && slugOf(e.set) === slugOf(set.name)))
  const as = (e: Extra): Opt => ({ value: e.value, label: e.label, author: e.author })
  const lead = mine.find((e) => e.lead)?.value
  const named = slotOptions.some((o) => o.value === set.default) ? set.default : slotOptions[0]?.value
  const pick = lead ?? named
  const s = seen.value
  const own = set.wrapper ? { original: s?.files?.[set.file] } : s?.slots?.[set.file]?.[set.name] ?? {}
  const stem = (e: Extra) => e.value.slice(e.value.lastIndexOf('/') + 1)
  const theirs = [...mine].sort((a, b) => (stem(a) < stem(b) ? -1 : stem(a) > stem(b) ? 1 : 0)).map(as)
  const when = (o: Opt) => (theirs.includes(o) ? s?.extras?.[o.value] : (own as Record<string, number | undefined>)[o.value]) ?? Infinity
  return [...slotOptions, ...theirs]
    .map((o, i) => ({ o: o.value === pick ? { ...o, isDefault: true } : o, i, t: when(o) }))
    .sort((a, b) => a.t - b.t || a.i - b.i)
    .map((x) => x.o)
}

export const extraOf = (value: string) => extras.find((e) => e.value === value)

// "Arohi", from "Arohi Sharma": the label has little room, the full name rides in the tooltip.
export const shortName = (username: string) => personName(username).split(/\s+/)[0] || username
