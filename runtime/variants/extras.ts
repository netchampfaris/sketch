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

// A set's options: the owner's slots in order, then the variants made for it. An adopted default leads.
export function mergeOptions(slotOptions: Opt[], set: { name: string; wrapper: boolean; file: string }): Opt[] {
  const mine = extras.filter((e) => (set.wrapper ? e.component === set.file : !e.component && slugOf(e.set) === slugOf(set.name)))
  if (!mine.length) return slotOptions
  const as = (e: Extra): Opt => ({ value: e.value, label: e.label, author: e.author })
  return [...mine.filter((e) => e.lead).map(as), ...slotOptions, ...mine.filter((e) => !e.lead).map(as)]
}

export const extraOf = (value: string) => extras.find((e) => e.value === value)

// "Arohi", from "Arohi Sharma": the label has little room, the full name rides in the tooltip.
export const shortName = (username: string) => personName(username).split(/\s+/)[0] || username
