// What is new for this person: variants and comments others made since they last looked. The server works it out
// (sketch/badges.py) and hands the Viewer a snapshot at load; this keeps it for the visit and reports what the person
// looks at. The canvas, the Demo pill and the annotate toolbar are separate bundles that import this through
// `sketch:variants`, so all of them hold the same object.
//
// A badge stays on screen for the visit it was loaded in, so it never vanishes under the pointer. A dot clears as the
// person looks (`looked`). Saving "seen" is quiet: a failure shows nothing, is kept, and goes again on the next look.
import { reactive } from 'vue'

export type FreshThread = { id: string; route: string; unread: number; mention: boolean }
export type Fresh = { variants?: string[]; threads?: FreshThread[] } | null
type Payload = { name?: string; commenter?: string; seen_exp?: string; seen_sig?: string; badges?: Fresh }

const URL = '/api/method/sketch.api.seen_mark'

export const badges = reactive({
  // Options new to this person when the page loaded. Nothing removes one before the next visit.
  fresh: {} as Record<string, true>,
  // The ones whose set the person has opened since.
  looked: {} as Record<string, true>,
  // Threads with something unread, by id, with the page they sit on.
  threads: {} as Record<string, { route: string; mention: boolean }>,
  // Pages (by path) whose Demo card was opened this visit.
  opened: {} as Record<string, true>,
})

let cred: { name: string; user: string; exp: string; sig: string } | null = null
const pending = { variants: new Set<string>(), threads: new Set<string>() }
let flying = false
// Something was looked at while a save was in flight: send it when that one is done.
let again = false

export function initBadges(data: Payload) {
  if (!data.seen_sig || !data.seen_exp || !data.name || !data.commenter) return
  cred = { name: data.name, user: data.commenter, exp: data.seen_exp, sig: data.seen_sig }
  for (const o of data.badges?.variants ?? []) badges.fresh[o] = true
  for (const t of data.badges?.threads ?? []) badges.threads[t.id] = { route: t.route, mention: t.mention }
  void flush()
}

// New since the person last looked, as of this visit's start. The tile's "New" badge.
export const isNew = (option: string) => !!badges.fresh[option]
// New and not yet looked at. The dots.
export const isFresh = (option: string) => !!badges.fresh[option] && !badges.looked[option]
export const freshIn = (options: readonly string[]) => options.filter(isFresh).length

// The person has opened a set (or its row in the Demo card): every option of it counts as seen.
export function lookAt(options: readonly string[]) {
  const fresh = options.filter(isFresh)
  if (!fresh.length) return
  for (const o of fresh) {
    badges.looked[o] = true
    pending.variants.add(o)
  }
  void flush()
}

// The person has opened a thread.
export function readThread(id: string) {
  delete badges.threads[id]
  pending.threads.add(id)
  void flush()
}

// The toolbar read the threads and knows which are unread now: the list replaces what the page loaded with.
export function setUnread(list: { id: string; route: string; unread: number; mention: boolean }[]) {
  const next = Object.fromEntries(list.filter((t) => t.unread).map((t) => [t.id, { route: t.route, mention: t.mention }]))
  for (const id of Object.keys(badges.threads)) if (!next[id]) delete badges.threads[id]
  Object.assign(badges.threads, next)
}

// The Demo pill's dot: this page has an option nobody here has looked at. Unread threads are not counted: the pill leads
// to options, and a thread's dot sits on the Comment tool, which leads to the threads.
export const pageHasNew = (path: string, optionsOnPage: readonly string[]) => !badges.opened[path] && freshIn(optionsOnPage) > 0

// A thread on this page (or on any page, with no path) has something this person has not read.
export const hasUnreadThreads = (path?: string) => Object.values(badges.threads).some((t) => !path || t.route.split('?')[0] === path)

async function flush() {
  if (!cred || !(pending.variants.size || pending.threads.size)) return
  if (flying) {
    again = true
    return
  }
  flying = true
  const variants = [...pending.variants]
  const threads = [...pending.threads]
  try {
    const form = new URLSearchParams({
      name: cred.name,
      username: cred.user,
      exp: cred.exp,
      sig: cred.sig,
      variants: JSON.stringify(variants),
      threads: JSON.stringify(threads),
    })
    const res = await fetch(URL, { method: 'POST', body: form, credentials: 'omit', cache: 'no-store' })
    if (res.ok) {
      variants.forEach((o) => pending.variants.delete(o))
      threads.forEach((t) => pending.threads.delete(t))
    }
  } catch {
    // Quiet by design: what is kept here goes again on the next look.
  } finally {
    flying = false
  }
  if (again) {
    again = false
    void flush()
  }
}

if (typeof document !== 'undefined') {
  document.addEventListener('visibilitychange', () => !document.hidden && void flush())
  window.addEventListener('online', () => void flush())
}
