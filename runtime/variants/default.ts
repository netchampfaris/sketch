// "Make default": ask the server to move a variant to the front of its set, so the first slot (the
// default) is the one the owner prefers. Internal, like `setKeepHandler`: the pill uses it, and so
// will the canvas tile. The Viewer is sandboxed with no cookie, so the write is authorised by the
// signature the payload carries (sketch.api.set_variant_default_signed). Only the owner's live page
// gets one, so a Guest, a `check` and a framed card never see the button.
import { shallowRef } from 'vue'
import { toast } from 'frappe-ui'
import { humanise, type VSet } from './state'

// The page reloads after a write, and a sandboxed page has no storage, so the toast that follows
// rides in `window.name`, which survives a reload.
const MARK = 'sketch:variant-default:'

type Credential = { name: string; exp: string; sig: string }
export const credential = shallowRef<Credential | null>(null)

type Note = { file: string; set: string; option: string; label: string; undo?: { option: string; label: string; sequence: number } }

// Called by the Viewer once the Prototype has mounted. Shows the toast a reload left behind.
export function enableMakeDefault(data: { name?: string; variant_exp?: string; variant_sig?: string }) {
  if (!data.name || !data.variant_exp || !data.variant_sig) return
  credential.value = { name: data.name, exp: data.variant_exp, sig: data.variant_sig }
  if (!window.name.startsWith(MARK)) return
  try {
    const note = JSON.parse(window.name.slice(MARK.length)) as Note
    announce(note)
  } catch {
    // A page that set its own window.name never gets a toast.
  } finally {
    window.name = ''
  }
}

function announce(note: Note) {
  const message = `${note.label} is now the default for ${note.set}`
  if (!note.undo) return void toast.success(message)
  const back = note.undo
  toast.success(message, {
    action: {
      label: 'Undo',
      onClick: () => {
        post('undo_variant_default_signed', { file: note.file, sequence: String(back.sequence), set_name: note.set, option: note.option })
          .then(() => reload({ file: note.file, set: note.set, option: back.option, label: back.label }))
          .catch((e: Error) => toast.error(`Couldn't undo: ${e.message}`))
      },
    },
  })
}

// The reload comes with its toast in `window.name`.
function reload(note: Note) {
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

// True when the owner can make `option` the default of `set` from this page.
export const canMakeDefault = (set: VSet) => Boolean(credential.value && set.file && set.options()[0]?.value !== undefined)

// Moves `option` first in the source and saves a version. Resolves once the server has written it,
// and the page reloads on its own after. Rejects with a message fit for a toast.
export async function makeDefault(set: VSet, option: string) {
  const opts = set.options()
  const previous = opts[0]
  const label = opts.find((o) => o.value === option)?.label ?? humanise(option)
  const done = await post('set_variant_default_signed', { file: set.file, set_name: set.name, option })
  reload({
    file: set.file,
    set: set.name,
    option,
    label,
    undo: previous && done?.sequence ? { option: previous.value, label: previous.label, sequence: done.sequence } : undefined,
  })
}
