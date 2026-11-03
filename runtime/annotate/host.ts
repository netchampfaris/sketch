// What the toolbar knows about the Prototype it sits on. It lives in the Viewer document, so
// there are no Prototype imports: boot.js hands over the payload, the router comes from the
// Prototype's own app, and everything else (files, title, saved notes) is read from the payload.
import type { Router } from 'vue-router'
import { titleOfRoute } from 'sketch:variants'

// The shape the server stores in `Sketch Prototype.annotations`. Lists are kept loose here:
// annotate.ts and tweak.ts validate each row they read back, so one bad row never costs the rest.
export type Saved = {
  notes?: any[]
  tweaks?: any[]
  prompt?: string
  anchor?: string
  updated?: string
}

export type Payload = {
  name?: string
  title?: string
  files?: Record<string, string>
  annotations?: Saved | null
  annotations_epoch?: number
  annotate_exp?: string
  annotate_sig?: string
  // A person who may comment: their username, and the right to ask for a pass (comments.ts).
  commenter?: string
  comment_exp?: string
  comment_sig?: string
  comments_open?: number
  // A signed-out visitor to a public Prototype.
  sign_in?: boolean
  // owner, editor, viewer or guest (sketch/viewer.py `role`).
  role?: string
}

// owner: notes, tweaks and comments, and resolves or deletes any comment. editor: their own notes and tweaks, and
// comments. reader: comments only. guest: a "Sign in to comment" button.
export type Role = 'owner' | 'editor' | 'reader' | 'guest'

export const host = {
  name: '',
  title: '',
  files: {} as Record<string, string>,
  saved: null as Saved | null,
  epoch: 0,
  exp: '',
  sig: '',
  // An editor's notes are saved under their own name (sketch/annotations.py).
  editor: '',
  role: 'owner' as Role,
  me: '',
  ticketExp: '',
  ticketSig: '',
  openCount: 0,
  router: null as Router | null,
}

export function initHost(data: Payload, router: Router) {
  host.name = data.name ?? ''
  host.title = (data.title ?? '').trim()
  host.files = data.files ?? {}
  host.saved = data.annotations && typeof data.annotations === 'object' ? data.annotations : null
  host.epoch = Number(data.annotations_epoch) || 0
  host.exp = data.annotate_exp ?? ''
  host.sig = data.annotate_sig ?? ''
  host.editor = data.role === 'editor' ? (data.commenter ?? '') : ''
  // Notes and tweaks come with their signature: the owner's page has one, and so does an invited editor's, for their own.
  host.role = data.role === 'editor' && data.commenter ? 'editor' : data.annotate_sig ? 'owner' : data.commenter ? 'reader' : 'guest'
  host.me = data.commenter ?? ''
  host.ticketExp = data.comment_exp ?? ''
  host.ticketSig = data.comment_sig ?? ''
  host.openCount = Number(data.comments_open) || 0
  host.router = router
}

export const isOwner = () => host.role === 'owner'
// Who has Note and Tweak: the owner, and an invited editor (their notes are their own).
export const canNote = () => !!host.sig && (host.role === 'owner' || host.role === 'editor')
export const isGuest = () => host.role === 'guest'

// How the prompts name the Prototype.
export const subject = () => (host.title ? `the ${host.title} prototype` : 'the prototype')

// A file is data (not copy) when a folder or its name says so: runtime/shared/tweak.ts, shared with the frame agent.
export { isDataFile } from '../shared/tweak'

// The page a route belongs to, named the way the canvas names it (titleOfRoute: meta.title, else the humanised
// component name). A route that matches nothing falls back to its first path segment, and the root to "Home".
export function pageNameOf(route: string): string {
  const path = route.split(/[?#]/)[0] || '/'
  try {
    const matched = host.router?.resolve(path).matched ?? []
    if (matched.length) return titleOfRoute(matched[matched.length - 1])
  } catch {}
  const seg = path.split('/').filter(Boolean)[0]
  return seg ? seg[0].toUpperCase() + seg.slice(1) : 'Home'
}
