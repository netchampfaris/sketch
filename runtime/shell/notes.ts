// Saving the notes and the toolbar's corner from the shell, with the session (sketch.viewer_api.save_annotations):
// the owner's own, or an invited editor's own (the server tells them apart by who is asking). The same shape
// and rules as runtime/annotate/store.ts, which the in-frame toolbar keeps using with its signature.
//
// Tweak is not in the shell yet (plan step 6), so the tweaks the server holds are kept as they came, and so is
// the tweak half of the prompt: a save of notes never drops them.
import { ref, watch } from 'vue'
import { toast } from 'frappe-ui'
import { anchorPref, buildPrompt, isAnchor, isNote, notes, readRows, type Note } from '../annotate/annotate'
import { call, HttpError } from './api'

const DEBOUNCE_MS = 800
// The server refuses a prompt over 64 KB; the rows are the source of truth, the prompt a convenience.
const PROMPT_MAX = 60000
// The tweak half of a saved prompt starts with these words (runtime/annotate/tweak.ts buildTweakPrompt).
const TWEAK_PROMPT = 'These are visual targets from a designer.'

export type SaveState = 'saved' | 'saving' | 'error'
export const saveState = ref<SaveState>('saved')

type Saved = { notes?: unknown; tweaks?: unknown[]; prompt?: string; anchor?: unknown }
let tweaks: unknown[] = []
let tweakPrompt = ''
let epoch = 0

const snapshot = () => ({ notes: notes.value, tweaks, anchor: anchorPref.value ?? undefined })

// Start from what the server holds.
let last = ''
export function restoreNotes(saved: unknown, savedEpoch: number) {
	const s = (saved && typeof saved === 'object' ? saved : {}) as Saved
	notes.value = readRows<Note>(s.notes, isNote)
	anchorPref.value = isAnchor(s.anchor) ? s.anchor : null
	tweaks = Array.isArray(s.tweaks) ? s.tweaks : []
	const at = typeof s.prompt === 'string' ? s.prompt.indexOf(TWEAK_PROMPT) : -1
	tweakPrompt = tweaks.length && at >= 0 ? s.prompt!.slice(at) : ''
	epoch = Number(savedEpoch) || 0
	last = JSON.stringify(snapshot())
}

// What the agent reads: the same text Copy prompt would put on the clipboard, then the tweaks as they were.
function promptOf(): string {
	try {
		return [notes.value.length ? buildPrompt(notes.value) : '', tweakPrompt].filter(Boolean).join('\n\n').slice(0, PROMPT_MAX)
	} catch {
		return ''
	}
}

let timer = 0
async function flush(keepalive = false) {
	clearTimeout(timer)
	timer = 0
	const key = JSON.stringify(snapshot())
	if (key === last) {
		saveState.value = 'saved'
		return
	}
	try {
		await call('save_annotations', { data: JSON.stringify({ ...snapshot(), prompt: promptOf() }), epoch: String(epoch) }, keepalive)
		last = key
		// A change made while this was in flight has its own save scheduled.
		if (!timer) saveState.value = 'saved'
	} catch (e) {
		// The agent cleared since this page loaded: start again from what the server holds.
		if (e instanceof HttpError && e.status === 409) return location.reload()
		if (saveState.value !== 'error') toast.error('Could not save your notes. They are kept on this page until you reload.')
		saveState.value = 'error'
	}
}

// Debounced after every change. A failed save is retried by the next change.
export function startSaving() {
	watch(
		() => JSON.stringify(snapshot()),
		(now) => {
			if (now === last) return
			saveState.value = 'saving'
			clearTimeout(timer)
			timer = window.setTimeout(flush, DEBOUNCE_MS)
		},
	)
	// A change made in the last moment before the tab goes away.
	window.addEventListener('pagehide', () => {
		if (timer) void flush(true)
	})
}
