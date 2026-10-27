// Saving and restoring the toolbar's state. The notes, the tweaks and the toolbar's corner live on
// the server (`Sketch Prototype.annotations`) so the owner's agent can read them over MCP and a
// reload loses nothing. The Viewer is sandboxed with no cookie and no storage, so the write is
// authorised by the signature the payload carries, not by a session (sketch.api.save_annotations).
import { ref, watch } from 'vue'
import { toast } from 'frappe-ui'
import { anchorPref, buildPrompt, isAnchor, isNote, notes, readRows, type Note } from './annotate'
import { host, type Saved } from './host'
import { buildTweakPrompt, isChanged, restoreTweaks, tweaks } from './tweak'

const SAVE_URL = '/api/method/sketch.api.save_annotations'
const DEBOUNCE_MS = 800
// The server refuses a prompt over 64 KB; the rows are the source of truth, the prompt a convenience.
const PROMPT_MAX = 60000

export type SaveState = 'saved' | 'saving' | 'error'
export const saveState = ref<SaveState>('saved')

function snapshot(): Saved {
  return { notes: notes.value, tweaks: tweaks.value.filter(isChanged), anchor: anchorPref.value ?? undefined }
}

// Start from what the server holds. Called once, before the toolbar mounts.
let last = ''
export function restore() {
  const s = host.saved
  notes.value = readRows<Note>(s?.notes, isNote)
  tweaks.value = restoreTweaks(s?.tweaks)
  anchorPref.value = isAnchor(s?.anchor) ? s.anchor : null
  last = JSON.stringify(snapshot())
}

// What the agent reads: the same text Copy prompt would put on the clipboard.
function promptOf(): string {
  try {
    const parts = [notes.value.length ? buildPrompt(notes.value) : '', tweaks.value.some(isChanged) ? buildTweakPrompt() : '']
    return parts.filter(Boolean).join('\n\n').slice(0, PROMPT_MAX)
  } catch {
    return ''
  }
}

let timer = 0
function post(body: string, keepalive = false) {
  // A form body is a "simple" request, so the sandboxed page needs no CORS preflight.
  const form = new URLSearchParams({ name: host.name, exp: host.exp, sig: host.sig, data: body, epoch: String(host.epoch) })
  return fetch(SAVE_URL, { method: 'POST', body: form, credentials: 'omit', cache: 'no-store', keepalive })
}

async function flush(keepalive = false) {
  clearTimeout(timer)
  timer = 0
  const snap = snapshot()
  const key = JSON.stringify(snap)
  if (key === last) {
    saveState.value = 'saved'
    return
  }
  try {
    const res = await post(JSON.stringify({ ...snap, prompt: promptOf() }), keepalive)
    // The agent cleared since this page loaded: start again from what the server holds.
    if (res.status === 409) return location.reload()
    if (!res.ok) throw new Error(String(res.status))
    last = key
    // A change made while this was in flight has its own save scheduled.
    if (!timer) saveState.value = 'saved'
  } catch {
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
