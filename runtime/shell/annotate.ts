// Annotate: pick elements or drag a box, leave a note, copy the lot as a prompt for a coding agent.
// The toolbar's state and the prompt builder live here; the .vue files draw. The elements are in the
// frame, which picks them (runtime/agent/pick.ts); a note holds what the frame reported about them.
// Saved state is restored by notes.ts from the shell's boot JSON.
import { ref } from 'vue'
import { whereOf, type TileRef } from '../shared/tiles'
import { subject } from './host'
import { elementLine } from '../shared/tweak'
import type { BoxInfo, ElInfo, Mode } from '../shared/protocol'

export type Note = {
  id: string
  route: string
  viewport: string
  selector: string
  component: string
  componentChain: string[]
  file?: string
  element: string
  text: string
  state?: string
  extras?: ElInfo[]
  box?: BoxInfo
  note: string
  sent?: boolean
  offset: { x: number; y: number }
  rect: { x: number; y: number; w: number; h: number }
  // A note or comment on a canvas tile: `route` is its page, and the element fields are empty. `offset` is
  // where on the tile, as a fraction of its width and height.
  tile?: TileRef
  createdAt: number
}

// The server's copy of a list may come from an older build or a hand edit, or be written by the
// Prototype's own code: drop what is unusable instead of breaking the page.
export function readRows<T>(rows: unknown, ok: (x: any) => boolean): T[] {
  return Array.isArray(rows) ? rows.filter((x) => x && typeof x === 'object' && ok(x)) : []
}
export const newId = () => `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`
// ---- State ----------------------------------------------------------------------------
// `enabled` shows the toolbar (else only the faint trigger); `active` is a tool picking inside it (note, comment or tweak).
// Session state: closed on every load, the faint trigger opens it.
export const enabled = ref(false)
export const active = ref(false)

// The toolbar has three tools. Note is the owner's instructions for their agent; Comment is a
// conversation with people (comments.ts); Tweak lives in its own files (tweaks.ts, TweakLayer.vue).
export const mode = ref<Mode>('note')
export const notes = ref<Note[]>([])
export const isNote = (n: any) => typeof n.id === 'string' && typeof n.route === 'string' && typeof n.note === 'string' && !!n.offset && !!n.rect

export function setEnabled(on: boolean) {
  enabled.value = on
  if (!on) active.value = false
}

// A note's number on its pin, in the list and in the prompt: its place among the notes of its page, or among
// the notes on tiles. Never stored: deleting a note renumbers the rest.
export const noteNumber = (n: Note) => notes.value.filter((x) => (n.tile ? !!x.tile : !x.tile && x.route === n.route)).findIndex((x) => x.id === n.id) + 1
export function addNote(n: Omit<Note, 'id' | 'createdAt'>) {
  notes.value = [...notes.value, { ...n, id: newId(), createdAt: Date.now() }]
}
export function updateNote(id: string, note: string) {
  notes.value = notes.value.map((x) => (x.id === id ? { ...x, note } : x))
}
export function removeNote(id: string) {
  notes.value = notes.value.filter((x) => x.id !== id)
}
export function clearNotes() {
  notes.value = []
}
export function markSent(ids: string[]) {
  notes.value = notes.value.map((x) => (ids.includes(x.id) ? { ...x, sent: true } : x))
}
export function clearSent() {
  notes.value = notes.value.filter((x) => !x.sent)
}

// ---- Toolbar anchor --------------------------------------------------------------------
export const ANCHORS = ['top-left', 'top-center', 'top-right', 'bottom-left', 'bottom-center', 'bottom-right'] as const
export type Anchor = (typeof ANCHORS)[number]
// null until the toolbar has been moved once. notes.ts restores and saves it with the notes.
export const anchorPref = ref<Anchor | null>(null)
export const isAnchor = (v: unknown): v is Anchor => typeof v === 'string' && (ANCHORS as readonly string[]).includes(v)
export function storedAnchor(): Anchor | null {
  return anchorPref.value
}
export function readAnchor(): Anchor {
  return anchorPref.value ?? 'bottom-center'
}
export function writeAnchor(a: Anchor) {
  anchorPref.value = a
}

// ---- Prompt ----------------------------------------------------------------------------
// Text beats classes: `h2 "Hand over work"` finds the element faster than `h2.text-lg`.

export function buildPrompt(list: Note[]): string {
  const out = [`Feedback on ${subject()} (${list.length} ${list.length === 1 ? 'note' : 'notes'})`]
  const live = list.filter((n) => !n.tile)
  const routes: string[] = []
  for (const n of live) if (!routes.includes(n.route)) routes.push(n.route)
  for (const r of routes) {
    const group = live.filter((n) => n.route === r)
    out.push('', `## ${r} (${group[0].viewport.replace('x', '×')})`, '')
    // Same numbers as the pins and the list: position among all notes of this page, sent or not.
    const onPage = notes.value.filter((x) => x.route === r && !x.tile)
    group.forEach((n) => {
      const i = Math.max(0, onPage.findIndex((x) => x.id === n.id))
      const extras = n.extras ?? []
      const line = elementLine(n.element, n.text)
      out.push(`${i + 1}. ${n.component || 'Unknown component'}${n.file ? ` (${n.file})` : ''}${extras.length ? ` +${extras.length} more` : ''}`)
      if (n.box) {
        // The container's own words would repeat what Covers says: name it by tag and classes.
        const where = `${n.component || 'page'} ${n.element}`
        if (n.box.kind === 'content') {
          out.push(`   Area: inside ${where}`)
          const c = (n.box.covers ?? []).map((s) => `"${s}"`).join(', ')
          if (c) out.push(`   Covers: ${c}${n.box.coversMore ? ` +${n.box.coversMore} more` : ''}`)
        } else {
          out.push(`   Area: empty space in ${where}`)
          const { before: a, after: b, gap, axis } = n.box
          const between = a && b ? `between "${a}" and "${b}"` : a ? `after "${a}"` : b ? `before "${b}"` : 'with nothing around it'
          out.push(`   Gap: ${gap != null ? `${gap}px ` : ''}${between} (${axis ?? 'vertical'})`)
        }
        if (n.state) out.push(`   State: ${n.state}`)
      } else if (extras.length) {
        out.push('   Elements:')
        const all: ElInfo[] = [{ selector: n.selector, component: n.component, element: n.element, text: n.text, state: n.state ?? '' }, ...extras]
        all.forEach((e, j) => {
          const st = e.state && (j === 0 || e.state !== all[0].state) ? ` (State: ${e.state})` : ''
          out.push(`   ${String.fromCharCode(97 + j)}. ${e.component || 'Unknown'}: ${elementLine(e.element, e.text)}${st}`)
        })
      } else {
        out.push(`   Element: ${line}`)
        if (n.state) out.push(`   State: ${n.state}`)
      }
      if (n.componentChain.length > 1) out.push(`   Path: ${n.componentChain.join(' > ')}`)
      out.push(`   Note: ${n.note.trim().replace(/\n/g, '\n         ')}`)
    })
  }

  // Canvas notes: each names its tile in words, so the agent knows which page, state or option it is about.
  const tiles = list.filter((n) => n.tile)
  if (tiles.length) {
    out.push('', 'Canvas notes are about one tile of the canvas: a page, one option of a Variants set, or one state of a page. Change that option or state.')
    const wheres: string[] = []
    const whereFor = (n: Note) => whereOf({ route: n.route, tile: n.tile! })
    for (const n of tiles) if (!wheres.includes(whereFor(n))) wheres.push(whereFor(n))
    const all = notes.value.filter((x) => x.tile)
    for (const w of wheres) {
      const group = tiles.filter((n) => whereFor(n) === w)
      out.push('', `## ${w}${group[0].viewport ? ` (${group[0].viewport.replace('x', '×')})` : ''}`, '')
      group.forEach((n) => {
        const i = Math.max(0, all.findIndex((x) => x.id === n.id))
        out.push(`${i + 1}. Pinned ${Math.round(n.offset.x * 100)}% across, ${Math.round(n.offset.y * 100)}% down the tile`)
        out.push(`   Note: ${n.note.trim().replace(/\n/g, '\n         ')}`)
      })
    }
  }
  return out.join('\n')
}

export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    // Clipboard API is blocked in some frames; the old route still works on a user gesture.
    try {
      const ta = document.createElement('textarea')
      ta.value = text
      ta.style.cssText = 'position:fixed;opacity:0'
      document.body.appendChild(ta)
      ta.select()
      const ok = document.execCommand('copy')
      ta.remove()
      return ok
    } catch {
      return false
    }
  }
}
