// Unread threads for this person (sketch/badges.py): the server's snapshot from the boot JSON, kept for the
// visit, and what the person reads reported back with the session (sketch.viewer_api.seen_mark). The canvas panel's rows carry the dot for options new to this person; the
// frame is told which options are new (option values only) for the tiles' "New" badge. Opening a set from the shell
// (its panel, the Demo pill) is looking at its options; nothing the frame says marks anything seen. Saving "seen" is quiet: a failure is kept and goes with the next read.
import { reactive } from 'vue'
import { call } from './api'

type Snapshot = { variants?: string[]; threads?: { id: string; route: string; unread: number; mention: boolean }[] } | null

export const badges = reactive({
	// Options new to this person when the page loaded. Nothing removes one before the next visit.
	fresh: {} as Record<string, true>,
	// The ones whose set the person has opened since.
	looked: {} as Record<string, true>,
	threads: {} as Record<string, { route: string; mention: boolean }>,
	// Pages (by path) whose Demo card was opened this visit.
	opened: {} as Record<string, true>,
})

let on = false
const pending = new Set<string>()
const pendingVariants = new Set<string>()
let flying = false
let again = false

export function initBadges(snapshot: unknown, signedIn: boolean) {
	on = signedIn
	for (const o of (snapshot as Snapshot)?.variants ?? []) if (typeof o === 'string') badges.fresh[o] = true
	for (const t of (snapshot as Snapshot)?.threads ?? []) badges.threads[t.id] = { route: t.route, mention: t.mention }
}

// New and not yet looked at: the dots.
const isFresh = (option: string) => !!badges.fresh[option] && !badges.looked[option]
export const freshIn = (options: readonly string[]) => options.filter(isFresh).length
export const freshOptions = () => Object.keys(badges.fresh)

// The person has opened a set (or its row in the Demo card): every option of it counts as seen. Only options the server
// named new to this person are marked, whatever the frame reported the set holds.
export function lookAt(options: readonly string[]) {
	const fresh = options.filter(isFresh)
	if (!fresh.length) return
	for (const o of fresh) {
		badges.looked[o] = true
		pendingVariants.add(o)
	}
	void flush()
}

// The person has opened a thread.
export function readThread(id: string) {
	delete badges.threads[id]
	pending.add(id)
	void flush()
}

// The threads were read and the list says which are unread now: it replaces what the page loaded with.
export function setUnread(list: { id: string; route: string; unread: number; mention: boolean }[]) {
	const next = Object.fromEntries(list.filter((t) => t.unread).map((t) => [t.id, { route: t.route, mention: t.mention }]))
	for (const id of Object.keys(badges.threads)) if (!next[id]) delete badges.threads[id]
	Object.assign(badges.threads, next)
}

// The Demo pill's dot: this page has an option nobody here has looked at. Unread threads are not counted: the pill leads
// to options, and a thread's dot sits on the Comment tool (runtime/variants/badges.ts pageHasNew).
export const pageHasNew = (path: string, optionsOnPage: readonly string[]) => !badges.opened[path] && freshIn(optionsOnPage) > 0

// A thread on this page (or on any page, with no path) has something this person has not read.
export const hasUnreadThreads = (path?: string) => Object.values(badges.threads).some((t) => !path || t.route.split('?')[0] === path)

async function flush() {
	if (!on || !(pending.size || pendingVariants.size)) return
	if (flying) return void (again = true)
	flying = true
	const threads = [...pending]
	const variants = [...pendingVariants]
	try {
		await call('seen_mark', { variants: JSON.stringify(variants), threads: JSON.stringify(threads) })
		threads.forEach((t) => pending.delete(t))
		variants.forEach((o) => pendingVariants.delete(o))
	} catch {
		// Quiet by design: what is kept here goes again on the next read.
	} finally {
		flying = false
	}
	if (again) {
		again = false
		void flush()
	}
}
