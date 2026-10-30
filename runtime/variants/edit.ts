// Deleting a variant a teammate added: the owner may delete any, an invited editor their own. The Viewer is sandboxed
// with no cookie, so the write is authorised by the credential the payload carries, which names the person
// (sketch.api.delete_variant_signed). The page reloads after the write and the Undo toast comes back with it, the way
// Make default does (default.ts).
import { toast } from 'frappe-ui'
import { editing } from './extras'
import { placeToasts } from './default'

const MARK = 'sketch:variant-deleted:'
const UNDO_MS = 10000

type Note = { option: string; label: string; sequence?: number; restored?: boolean; until?: number }

// True when the person looking can delete this option: every one for the owner, their own for an editor.
// Adopted variants are the owner's files now, so an editor never gets the menu on one.
export const canDelete = (option: string) => {
  const who = editing.value
  return Boolean(who && (who.owner ? true : option.startsWith(`@${who.user}/`)))
}

export function enableVariantEdit(data: { name?: string; editor?: string; is_owner?: boolean; edit_exp?: string; edit_sig?: string }) {
  if (!data.name || !data.editor || !data.edit_exp || !data.edit_sig) return
  editing.value = { name: data.name, user: data.editor, owner: Boolean(data.is_owner), exp: data.edit_exp, sig: data.edit_sig }
  if (!window.name.startsWith(MARK)) return
  placeToasts()
  try {
    const note = JSON.parse(window.name.slice(MARK.length)) as Note
    window.name = ''
    announce(note)
  } catch {
    window.name = ''
  }
}

function announce(note: Note) {
  if (note.restored) return void toast.success(`Restored ${note.label}`)
  if (!note.sequence) return void toast.success(`Deleted ${note.label}`)
  const sequence = note.sequence
  toast.success(`Deleted ${note.label}`, {
    duration: UNDO_MS,
    action: {
      label: 'Undo',
      onClick: () => {
        post('undo_delete_variant_signed', { option: note.option, sequence: String(sequence) })
          .then(() => reload({ option: note.option, label: note.label, restored: true }))
          .catch((e: Error) => toast.error(`Couldn't undo. ${e.message}`))
      },
    },
  })
}

function reload(note: Note) {
  window.name = MARK + JSON.stringify(note)
  location.reload()
}

function readError(body: any): string {
  try {
    const first = JSON.parse(JSON.parse(body._server_messages)[0])
    return String(first.message).replace(/<[^>]*>/g, '')
  } catch {
    return 'Reload the page and try again.'
  }
}

async function post(method: string, params: Record<string, string>) {
  const c = editing.value
  if (!c) throw new Error('Only the owner and invited editors can delete variants.')
  const form = new URLSearchParams({ name: c.name, username: c.user, exp: c.exp, sig: c.sig, ...params })
  const res = await fetch(`/api/method/sketch.api.${method}`, { method: 'POST', body: form, credentials: 'omit', cache: 'no-store' })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(readError(body))
  return body.message
}

export const deleteFailure = (e: Error) =>
  e instanceof TypeError ? "Couldn't delete the variant. Check your connection and try again." : `Couldn't delete the variant. ${e.message}`

// Resolves never on success: the page reloads once the file is gone. Rejects with an error fit for a toast.
export async function deleteVariant(option: string, label: string) {
  const done = await post('delete_variant_signed', { option })
  reload({ option, label, sequence: done?.sequence })
}
