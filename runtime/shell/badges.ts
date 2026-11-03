// Unread threads for this person (sketch/badges.py): the server's snapshot from the boot JSON, kept for the
// visit, and what the person reads reported back with the session (sketch.viewer_api.seen_mark). The same
// rules as runtime/variants/badges.ts, whose thread half this is; new options stay in the frame until the
// Demo pill moves here (plan step 5). Saving "seen" is quiet: a failure is kept and goes with the next read.
import { reactive } from 'vue'
import { call } from './api'

type Snapshot = { threads?: { id: string; route: string; unread: number; mention: boolean }[] } | null

export const badges = reactive({ threads: {} as Record<string, { route: string; mention: boolean }> })

let on = false
const pending = new Set<string>()
let flying = false
let again = false

export function initBadges(snapshot: unknown, signedIn: boolean) {
	on = signedIn
	for (const t of (snapshot as Snapshot)?.threads ?? []) badges.threads[t.id] = { route: t.route, mention: t.mention }
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

// A thread on this page (or on any page, with no path) has something this person has not read.
export const hasUnreadThreads = (path?: string) => Object.values(badges.threads).some((t) => !path || t.route.split('?')[0] === path)

async function flush() {
	if (!on || !pending.size) return
	if (flying) return void (again = true)
	flying = true
	const threads = [...pending]
	try {
		await call('seen_mark', { variants: '[]', threads: JSON.stringify(threads) })
		threads.forEach((t) => pending.delete(t))
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
