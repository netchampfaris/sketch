// What the shell's toolbar knows about the Prototype it sits over. Shell.vue fills it from the shell's boot
// JSON (sketch/viewer.py shell_payload) once, and the page names from what the frame reported: the shell never
// holds the tree.
import type { Router } from 'vue-router'
import { titleOfRoute } from './variants'

// The shape the server stores in `Sketch Prototype.annotations`. Lists are kept loose here:
// annotate.ts and tweaks.ts validate each row they read back, so one bad row never costs the rest.
export type Saved = {
  notes?: any[]
  tweaks?: any[]
  prompt?: string
  anchor?: string
  updated?: string
}

// owner: notes, tweaks and comments, and resolves or deletes any comment. editor: their own notes and tweaks, and
// comments. reader: comments only. guest: a "Sign in to comment" button.
export type Role = 'owner' | 'editor' | 'reader' | 'guest'

export const host = {
  name: '',
  title: '',
  role: 'owner' as Role,
  // The reader's username, which their comments are signed with.
  me: '',
  openCount: 0,
  // A memory router of the frame's pages, for their names (Shell.vue).
  router: null as Router | null,
}

export const isOwner = () => host.role === 'owner'
export const isGuest = () => host.role === 'guest'

// How the prompts name the Prototype.
export const subject = () => (host.title ? `the ${host.title} prototype` : 'the prototype')

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
