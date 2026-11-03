// Saving the notes, the tweaks and the toolbar's corner from the shell, with the session
// (sketch.viewer_api.save_annotations): the owner's own, or an invited editor's own (the server tells them apart by who
// is asking). Only the shell's own panel and lists change what is saved; nothing the frame says does.
import { ref, watch } from 'vue'
import { toast } from 'frappe-ui'
import { anchorPref, buildPrompt, isAnchor, isNote, notes, readRows, type Note } from './annotate'
import { isChanged } from '../shared/tweak'
import { call, HttpError } from './api'
import { buildTweakPrompt, hasTweaks, restoreTweakRows, tweaks } from './tweaks'

const DEBOUNCE_MS = 800
// The server refuses a prompt over 64 KB; the rows are the source of truth, the prompt a convenience.
const PROMPT_MAX = 60000

export type SaveState = 'saved' | 'saving' | 'error'
export const saveState = ref<SaveState>('saved')

type Saved = { notes?: unknown; tweaks?: unknown; anchor?: unknown }
let epoch = 0

const snapshot = () => ({ notes: notes.value, tweaks: tweaks.value.filter(isChanged), anchor: anchorPref.value ?? undefined })

// Start from what the server holds.
let last = ''
export function restoreNotes(saved: unknown, savedEpoch: number) {
	const s = (saved && typeof saved === 'object' ? saved : {}) as Saved
	notes.value = readRows<Note>(s.notes, isNote)
	anchorPref.value = isAnchor(s.anchor) ? s.anchor : null
	restoreTweakRows(s.tweaks)
	epoch = Number(savedEpoch) || 0
	last = JSON.stringify(snapshot())
}

// What the agent reads: the same text Copy prompt would put on the clipboard, notes then tweaks, each built from its rows.
function promptOf(): string {
	try {
		return [notes.value.length ? buildPrompt(notes.value) : '', hasTweaks() ? buildTweakPrompt() : ''].filter(Boolean).join('\n\n').slice(0, PROMPT_MAX)
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
