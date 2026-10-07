// What the toolbar knows about the Prototype it sits on. It lives in the Viewer document, so
// there are no Prototype imports: boot.js hands over the payload, the router comes from the
// Prototype's own app, and everything else (files, title, saved notes) is read from the payload.
import type { Router } from 'vue-router'

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
}

export const host = {
  name: '',
  title: '',
  files: {} as Record<string, string>,
  saved: null as Saved | null,
  epoch: 0,
  exp: '',
  sig: '',
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
  host.router = router
}

// How the prompts name the Prototype.
export const subject = () => (host.title ? `the ${host.title} prototype` : 'the prototype')

// A file is data (not copy) when any folder is data, fixtures or mocks, or its name says so.
// Hard-coded text found only in these files is a value the page shows, not wording to edit.
export function isDataFile(path: string): boolean {
  const parts = path.split('/')
  const base = parts[parts.length - 1]
  return parts.slice(0, -1).some((p) => /^(data|fixtures|mocks)$/i.test(p)) || /^(data|fixtures|mock[^.]*)\./i.test(base)
}

// "TimeOff" reads as "Time off"; "time-off" the same.
export function humanise(name: string): string {
  const words = name
    .replace(/([a-z\d])([A-Z])/g, '$1 $2')
    .replace(/[-_]+/g, ' ')
    .trim()
    .toLowerCase()
  return words ? words[0].toUpperCase() + words.slice(1) : ''
}

// The page a route belongs to: the matched route's component name, humanised. A route with no
// named component falls back to its first path segment, and the root to "Home".
export function pageNameOf(route: string): string {
  const path = route.split(/[?#]/)[0] || '/'
  try {
    const matched = host.router?.resolve(path).matched ?? []
    const comp: any = matched[matched.length - 1]?.components?.default
    const name = comp && typeof comp === 'object' ? comp.__name || comp.name : ''
    if (name) return humanise(name)
  } catch {}
  const seg = path.split('/').filter(Boolean)[0]
  return seg ? seg[0].toUpperCase() + seg.slice(1) : 'Home'
}
