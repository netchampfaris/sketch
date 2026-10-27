// "Make default": ask the server to move a variant to the front of its set, so the first slot (the
// default) is the one the owner prefers. Internal, like `setKeepHandler`: the pill uses it, and so
// does the canvas tile. The Viewer is sandboxed with no cookie, so the write is authorised by the
// signature the payload carries (sketch.api.set_variant_default_signed). Only the owner's live page
// gets one, so a Guest, a `check` and a framed card never see the button.
import { shallowRef } from 'vue'
import { toast } from 'frappe-ui'
import { humanise, type Opt } from './state'

// The page reloads after a write, and a sandboxed page has no storage, so what the next page shows
// rides in `window.name`, which survives a reload. MARK is a result to announce. PENDING is an Undo
// toast that is on screen: a live reload (the agent wrote) must not drop it silently.
const MARK = 'sketch:variant-default:'
const PENDING = 'sketch:variant-undo:'
// How long the Undo toast stays. The page takes a moment to reload, and the owner then looks for
// the change before reaching for Undo.
const UNDO_MS = 10000
const GONE = "Can't undo anymore: the page changed since. Ask your agent instead."

type Credential = { name: string; exp: string; sig: string }
export const credential = shallowRef<Credential | null>(null)

// What a failed Make default tells the owner. A refused fetch is a TypeError with the browser's own words.
export const makeFailure = (e: Error) =>
  e instanceof TypeError ? "Couldn't make it the default. Check your connection and try again." : `Couldn't change the default. ${e.message}`

type Undo = { option: string; label: string; sequence: number }
type Note = {
  file: string
  set: string
  option: string
  label: string
  // Set when this is the Undo coming back, so the toast says it is not a new change.
  restored?: boolean
  // The change was Keep only this, not Make default: the toast and the Undo call differ.
  kept?: boolean
  // How many other options Keep only this removed.
  removed?: number
  undo?: Undo
  // The file as the page loaded it after the write, to tell a later change from none.
  hash?: string
  until?: number
}
type Flash = { error: string }

// Toasts sit above the pill stack and the annotate launcher in the corner, not over them. The
// stack publishes its height in --sketch-variants-h. While the canvas's side panel is open it
// publishes the room it takes from the right edge in --sketch-panel-w, and toasts stand left of it.
let placed = false
export function placeToasts() {
  if (placed) return
  placed = true
  const style = document.createElement('style')
  style.textContent =
    '[data-sonner-toaster]{--offset-bottom:calc(var(--sketch-variants-h,0px) + 72px)!important;--mobile-offset-bottom:calc(var(--sketch-variants-h,0px) + 72px)!important;--offset-right:max(24px,calc(var(--sketch-panel-w,0px) + 16px))!important;}'
  document.head.append(style)
}

const hashOf = (s: string | undefined) => {
  let h = 5381
  for (const c of s ?? '') h = (h * 33 + c.charCodeAt(0)) | 0
  return String(h)
}

// Called by the Viewer once the Prototype has mounted. Shows what a reload left behind.
export function enableMakeDefault(data: { name?: string; variant_exp?: string; variant_sig?: string; files?: Record<string, string> }) {
  if (!data.name || !data.variant_exp || !data.variant_sig) return
  credential.value = { name: data.name, exp: data.variant_exp, sig: data.variant_sig }
  placeToasts()
  const raw = window.name
  const pending = raw.startsWith(PENDING)
  if (!pending && !raw.startsWith(MARK)) return
  try {
    const note = JSON.parse(raw.slice((pending ? PENDING : MARK).length)) as Note | Flash
    window.name = ''
    if ('error' in note) return void toast.error(`Couldn't change the default. ${note.error}`)
    if (!pending) return announce(note, data.files)
    if (!note.until || note.until <= Date.now()) return
    // The reload came from a write while the toast was up. Undo is only safe if that write left the file alone.
    if (hashOf(data.files?.[note.file]) === note.hash) announce(note, data.files)
    else toast.error(GONE)
  } catch {
    // A page that set its own window.name never gets a toast.
    window.name = ''
  }
}

const others = (n = 0) => (n ? `, removed ${n} other${n === 1 ? '' : 's'}` : '')

function announce(note: Note, files?: Record<string, string>) {
  const message = note.kept
    ? note.restored ? 'Options restored' : `Kept ${note.label}${others(note.removed)}`
    : note.restored ? 'Default restored' : `${note.label} is now the default for ${note.set}`
  const back = note.undo
  if (!back) return void toast.success(message)
  const until = note.until ?? Date.now() + UNDO_MS
  const done = () => {
    if (window.name.startsWith(PENDING)) window.name = ''
  }
  window.name = PENDING + JSON.stringify({ ...note, hash: hashOf(files?.[note.file]), until })
  toast.success(message, {
    duration: Math.max(until - Date.now(), 1000),
    onDismiss: done,
    onAutoClose: done,
    action: {
      label: 'Undo',
      onClick: () => {
        done()
        post(note.kept ? 'undo_keep_variant_signed' : 'undo_variant_default_signed', {
          file: note.file,
          sequence: String(back.sequence),
          set_name: note.set,
          option: note.option,
        })
          .then(() => reload({ file: note.file, set: note.set, option: back.option, label: back.label, restored: true, kept: note.kept }))
          .catch((e: Error) => toast.error(`Couldn't undo: ${e.message}`))
      },
    },
  })
}

function reload(note: Note | Flash) {
  window.name = MARK + JSON.stringify(note)
  location.reload()
}

// Frappe answers a refusal with `_server_messages`: a JSON list of JSON strings, each with a `message`.
function readError(body: any): string {
  try {
    const first = JSON.parse(JSON.parse(body._server_messages)[0])
    return String(first.message).replace(/<[^>]*>/g, '')
  } catch {
    return 'Reload the page and try again.'
  }
}

async function post(method: string, params: Record<string, string>) {
  const c = credential.value
  if (!c) throw new Error('Only the owner can change the default.')
  const form = new URLSearchParams({ name: c.name, exp: c.exp, sig: c.sig, ...params })
  const res = await fetch(`/api/method/sketch.api.${method}`, { method: 'POST', body: form, credentials: 'omit', cache: 'no-store' })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(readError(body))
  return body.message
}

// What Make default needs of a set: a live `<Variants>` set on the page, or one the canvas learned from a frame.
type Defaultable = { name: string; file: string; options: () => Opt[] }

// True when the owner can make an option the default of `set` from this page.
export const canMakeDefault = (set: Defaultable) => Boolean(credential.value && set.file && set.options()[0]?.value !== undefined)

// Moves `option` first in the source and saves a version. Resolves never on success, because the
// page reloads once it is written. Rejects with a message fit for a toast.
export async function makeDefault(set: Defaultable, option: string) {
  const opts = set.options()
  const previous = opts[0]
  const label = opts.find((o) => o.value === option)?.label ?? humanise(option)
  let done: any
  try {
    done = await post('set_variant_default_signed', { file: set.file, set_name: set.name, option })
  } catch (e) {
    // The source already has this default: this tab is stale. Reload so the row tells the truth.
    if (/already the default/.test((e as Error).message)) return reload({ error: (e as Error).message })
    throw e
  }
  reload({
    file: set.file,
    set: set.name,
    option,
    label,
    undo: previous && done?.sequence ? { option: previous.value, label: previous.label, sequence: done.sequence } : undefined,
  })
}

// True when the owner can keep one option of `set` and remove the rest: their page, and a set the source names.
export const canKeepOnly = (set: { file?: string }) => Boolean(credential.value && set.file)

// Cuts every other option of the set (a teammate's variants too) and saves a version. Resolves never on success, because
// the page reloads and shows "Kept …" with Undo. Rejects with a message fit for a toast. A teammate's option is
// adopted first: the server answers with the option's new name.
export async function keepOnly(set: { name: string; file: string }, option: string, label: string) {
  const done = await post('keep_variant_signed', { file: set.file, set_name: set.name, option })
  const kept = done?.option ?? option
  reload({
    file: set.file,
    set: set.name,
    option: kept,
    label,
    kept: true,
    removed: done?.removed,
    undo: done?.sequence ? { option: kept, label, sequence: done.sequence } : undefined,
  })
}

export const keepFailure = (e: Error) =>
  e instanceof TypeError ? "Couldn't keep it. Check your connection and try again." : `Couldn't keep only this. ${e.message}`
