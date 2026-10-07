// Annotate: pick elements or drag a box, leave a note, copy the lot as a prompt for a coding agent.
// The state, the element helpers and the prompt builder live here; the .vue files draw.
// Saved state is restored by store.ts once the Prototype's payload is known; nothing here reads
// the Prototype's files or storage directly.
import { ref, shallowRef, type Ref } from 'vue'
import { host, subject } from './host'
import type { TweakItem } from './tweak'


// One element of a note: enough to find it again and to describe it to an agent.
export type ElInfo = { selector: string; component: string; element: string; text: string; state: string }

// A dragged box, kept as fractions of the note's container so it can be redrawn after layout moves.
export type BoxInfo = {
  kind: 'content' | 'empty'
  fx: number
  fy: number
  fw: number
  fh: number
  covers?: string[]
  coversMore?: number
  before?: string
  after?: string
  gap?: number
  axis?: 'vertical' | 'horizontal'
}

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
  createdAt: number
}

// The server's copy of a list may come from an older build or a hand edit, or be written by the
// Prototype's own code: drop what is unusable instead of breaking the page.
export function readRows<T>(rows: unknown, ok: (x: any) => boolean): T[] {
  return Array.isArray(rows) ? rows.filter((x) => x && typeof x === 'object' && ok(x)) : []
}
export const newId = () => `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`
export const clamp = (n: number, lo: number, hi: number) => Math.max(lo, Math.min(n, hi))
export const typing = (t: EventTarget | null) => {
  const el = t as HTMLElement | null
  return !!el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT' || el.isContentEditable)
}
// Capture-phase document listeners, all removed by the returned function.
export function listen(handlers: [string, (e: any) => void][]): () => void {
  for (const [type, fn] of handlers) document.addEventListener(type, fn, true)
  return () => {
    for (const [type, fn] of handlers) document.removeEventListener(type, fn, true)
  }
}

// ---- State ----------------------------------------------------------------------------
// `enabled` shows the toolbar (else only the faint trigger); `active` is a tool picking inside it (comment or tweak).
// Session state: closed on every load, the faint trigger opens it.
export const toolbarOpen = ref(false)
export const enabled = toolbarOpen
export const active = ref(false)

// The toolbar has two tools. The other one (tweak) lives in its own files and registers its
// count, copy and reset here, so the toolbar can drive it without importing it.
export type Mode = 'comment' | 'tweak'
export const mode = ref<Mode>('comment')
export type TweakApi = {
  count: Ref<number>
  items: Ref<TweakItem[]>
  copy: () => string
  reset: () => void
  remove: (id: string) => void
  reveal: (id: string) => Promise<void>
  highlight: (id: string | null) => void
}
export const tweakApi = shallowRef<TweakApi | null>(null)
export const notes = ref<Note[]>([])
export const isNote = (n: any) => typeof n.id === 'string' && typeof n.route === 'string' && typeof n.note === 'string' && !!n.offset && !!n.rect
// Element outlined right now (hovered in comment mode, or the element of a hovered pin).
export const hoverEl = shallowRef<Element | null>(null)
export const hoverLabel = ref('')
// Set with hoverEl when the hovered pin belongs to a dragged box, so the box is redrawn too.
export const hoverFrac = shallowRef<BoxInfo | null>(null)
// Outlined for a second after a jump from the notes list.
export const flashEl = shallowRef<Element | null>(null)

export function setEnabled(on: boolean) {
  toolbarOpen.value = on
  if (!on) active.value = false
}

// Live elements of notes made this page session: pins trust these before any selector.
const live = new Map<string, WeakRef<Element>>()
export function addNote(n: Omit<Note, 'id' | 'createdAt'>, els: Element[] = []) {
  const id = newId()
  els.forEach((el, i) => live.set(`${id}:${i}`, new WeakRef(el)))
  notes.value = [...notes.value, { ...n, id, createdAt: Date.now() }]
}
// The note's i-th element (0 is the main one, then the extras): the live reference, else the selector.
export function resolveNote(n: Note, i = 0): Element | null {
  const el = live.get(`${n.id}:${i}`)?.deref()
  if (el?.isConnected) return el
  return resolve(i === 0 ? n.selector : (n.extras?.[i - 1]?.selector ?? ''))
}
export function updateNote(id: string, note: string) {
  notes.value = notes.value.map((x) => (x.id === id ? { ...x, note } : x))
}
// A note that is gone no longer needs its live elements.
function forget(ids: string[]) {
  for (const k of [...live.keys()]) if (ids.includes(k.slice(0, k.lastIndexOf(':')))) live.delete(k)
}
export function removeNote(id: string) {
  forget([id])
  notes.value = notes.value.filter((x) => x.id !== id)
}
export function clearNotes() {
  live.clear()
  notes.value = []
}
export function markSent(ids: string[]) {
  notes.value = notes.value.map((x) => (ids.includes(x.id) ? { ...x, sent: true } : x))
}
export function clearSent() {
  forget(notes.value.filter((x) => x.sent).map((x) => x.id))
  notes.value = notes.value.filter((x) => !x.sent)
}

// ---- Toolbar anchor --------------------------------------------------------------------
export const ANCHORS = ['top-left', 'top-center', 'top-right', 'bottom-left', 'bottom-center', 'bottom-right'] as const
export type Anchor = (typeof ANCHORS)[number]
// null until the toolbar has been moved once. store.ts restores and saves it with the notes.
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

// ---- Our own UI is never a target ------------------------------------------------------
export const UI_ATTR = 'data-annotate-ui'
// Tooltips from the component library are portalled out of our markup; treat them as ours too.
const OURS = `[${UI_ATTR}],[data-sketch-ui],[data-slot^="tooltip"],[role="tooltip"]`
export const isOurs = (el: Node | null | undefined) => {
  const e = el instanceof Element ? el : el?.parentElement
  return !!e?.closest(OURS)
}
// The page element an event is aimed at; never one of ours.
export const targetOf = (e: Event) => {
  const t = e.target
  return t instanceof Element && !isOurs(t) ? t : null
}

// ---- Element info ----------------------------------------------------------------------
// Attributes that change with state, not identity: never a stable handle.
const UNSTABLE = /^data-(v-|state|orientation|highlighted|disabled|selected|side|align|reka|radix|annotate|motion|active|open|slot$)/

// Ids a library makes up on each load (reka-popover-trigger-v-3, :r1:, headlessui-menu-2): not handles.
export const generatedId = (id: string) => /^(reka-|radix-|v-|headlessui-)|-v-\d+$|:r\w+:|\d{3,}|-\d+$/.test(id)

function segmentOf(el: Element, byChild: boolean, stable = false): string {
  if (el.id && !(stable && generatedId(el.id))) return `#${CSS.escape(el.id)}`
  const tag = el.tagName.toLowerCase()
  const sibs = el.parentElement ? Array.from(el.parentElement.children) : [el]
  if (byChild) return `${tag}:nth-child(${sibs.indexOf(el) + 1})`
  for (const a of Array.from(el.attributes)) {
    if (a.name.startsWith('data-') && !UNSTABLE.test(a.name) && a.value && a.value.length < 40) {
      return `${tag}[${a.name}="${CSS.escape(a.value)}"]`
    }
  }
  const same = sibs.filter((c) => c.tagName === el.tagName)
  return same.length > 1 ? `${tag}:nth-of-type(${same.indexOf(el) + 1})` : tag
}

// Climb until the path matches exactly one element. Attribute and nth-of-type segments first;
// if that never gets unique, nth-child all the way up, which always does.
function climb(el: Element, byChild: boolean, stable = false): string | null {
  const parts: string[] = []
  for (let cur: Element | null = el; cur && cur !== document.documentElement; cur = cur.parentElement) {
    if (cur === document.body) continue
    const seg = segmentOf(cur, byChild, stable)
    parts.unshift(seg)
    const path = parts.join(' > ')
    try {
      if (document.querySelectorAll(path).length === 1) return path
    } catch {}
    if (seg.startsWith('#')) break
  }
  return null
}

export function selectorOf(el: Element, stable = false): string {
  return climb(el, false, stable) ?? climb(el, true, stable) ?? el.tagName.toLowerCase()
}

export function resolve(selector: string): Element | null {
  try {
    const el = document.querySelector(selector)
    return el && !isOurs(el) ? el : null
  } catch {
    return null
  }
}

// The Prototype's own components, by name: the runtime compiler names a <script setup> component
// after its file, so the name leads back to the path. Frappe-ui internals are not in this map.
let fileMap: Map<string, string> | null = null
function files(): Map<string, string> {
  if (!fileMap) {
    fileMap = new Map()
    for (const path of Object.keys(host.files)) {
      if (!path.startsWith('src/') || !path.endsWith('.vue')) continue
      const name = path.slice(path.lastIndexOf('/') + 1, -4)
      if (!fileMap.has(name)) fileMap.set(name, path)
    }
  }
  return fileMap
}
const FILE_OF = { has: (n: string) => files().has(n), get: (n: string) => files().get(n) }
export const isOursName = (n: string | undefined) => !!n && FILE_OF.has(n)
export const fileOfName = (n: string | undefined) => (n ? FILE_OF.get(n) : undefined)

// Production Vue drops __vueParentComponent from elements, so walk the vnode tree from the
// app root down to the element instead, collecting component instances on the way.
export type Hit = { vn: any; stack: any[] }
function trail(vn: any, target: Element, stack: any[]): Hit | null {
  if (!vn || typeof vn !== 'object') return null
  if (vn.component) return trail(vn.component.subTree, target, [...stack, vn.component])
  if (vn.el === target && typeof vn.type === 'string') return { vn, stack }
  if (vn.suspense) {
    const r = trail(vn.suspense.activeBranch, target, stack)
    if (r) return r
  }
  if (Array.isArray(vn.children)) {
    for (const ch of vn.children) {
      const r = trail(ch, target, stack)
      if (r) return r
    }
  }
  return null
}

// The vnode of the element and the instances around it, outermost first. Not every element has its
// own vnode (v-html, frappe-ui internals): climb until one does.
export function vnodeOf(el: Element): Hit | null {
  const root = (document.querySelector('#app') as any)?._vnode
  let found: Hit | null = null
  for (let e: Element | null = el; e && !found; e = e.parentElement) found = trail(root, e, [])
  return found
}
const instancesOf = (el: Element): any[] => vnodeOf(el)?.stack ?? []
export const nameOfType = (t: any): string | undefined => t?.__name || t?.name

export type ComponentInfo = { component: string; chain: string[]; file?: string }

export function componentOf(el: Element): ComponentInfo {
  const names: string[] = []
  for (const inst of instancesOf(el).reverse()) {
    const name = nameOfType(inst.type)
    // Frappe-ui internals have no file of ours, so they drop out here.
    if (name && FILE_OF.has(name) && !names.includes(name)) names.push(name)
  }
  const component = names[0] ?? ''
  return { component, chain: names.slice(0, 3).reverse(), file: FILE_OF.get(component) }
}

// Primitive props of the nearest component of ours: what the element was showing when it was picked.
export function stateOf(el: Element): string {
  const inst = instancesOf(el)
    .reverse()
    .find((i) => FILE_OF.has(nameOfType(i.type) ?? ''))
  const parts: string[] = []
  for (const [k, v] of Object.entries(inst?.props ?? {})) {
    if (parts.length >= 6) break
    if (typeof v === 'string') {
      if (v.length <= 40) parts.push(`${k}: ${JSON.stringify(v)}`)
    } else if ((typeof v === 'number' && Number.isFinite(v)) || typeof v === 'boolean') parts.push(`${k}: ${v}`)
  }
  return parts.join(', ')
}

export function summaryOf(el: Element): string {
  const classes = Array.from(el.classList).filter((c) => !c.includes(':') && !c.includes('[')).slice(0, 2)
  let s = el.tagName.toLowerCase() + classes.map((c) => `.${c}`).join('')
  const role = el.getAttribute('role')
  const label = el.getAttribute('aria-label')
  if (role) s += ` role=${role}`
  if (label) s += ` aria-label="${label}"`
  return s
}

// frappe-ui components we name when no component of ours is closer to the element.
const LIB = new Set('Button Badge Avatar Dialog Dropdown Tabs TabButtons FormControl TextInput Textarea Select MultiSelect Combobox Checkbox Switch Radio RadioGroup Slider Progress Alert Popover Breadcrumbs DatePicker TimePicker DateTimePicker DateRangePicker Sidebar SidebarItem PageHeader ListRow ListCell ListHeader Tree Rating Password FileUploader Skeleton Spinner KeyboardShortcut'.split(' '))

// What an element is called in the UI: our component, else a frappe-ui one, else its tag. Never a selector.
export function labelOf(el: Element): string {
  // The nearest one wins, so a Button inside an InboxRow is a Button.
  for (const inst of instancesOf(el).reverse()) {
    const name = nameOfType(inst.type)
    if (name && (FILE_OF.has(name) || LIB.has(name))) return name
  }
  return el.tagName.toLowerCase()
}

// The tag over the hover outline: the component name only.
export function tagOf(el: Element): string {
  return labelOf(el)
}

export function textOf(el: Element, max = 80): string {
  return ((el as HTMLElement).innerText || el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, max)
}

export function infoOf(el: Element): ElInfo {
  return { selector: selectorOf(el), component: componentOf(el).component, element: summaryOf(el), text: textOf(el), state: stateOf(el) }
}

// The route a note belongs to: the full path without the ?v= cache-buster (and any old ?annotate).
export function routeKey(route: { path: string; query: Record<string, any> }): string {
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(route.query)) {
    if (k === 'annotate' || k === 'v') continue
    for (const x of Array.isArray(v) ? v : [v]) if (x != null) q.append(k, String(x))
  }
  const s = q.toString()
  return s ? `${route.path}?${s}` : route.path
}

// ---- Geometry --------------------------------------------------------------------------
export type Rect = { x: number; y: number; w: number; h: number }

const SKIP_TAGS = new Set(['SCRIPT', 'STYLE', 'LINK', 'META', 'NOSCRIPT', 'TEMPLATE', 'HEAD', 'BR'])
const nonZero = (r: DOMRect) => r.width > 0 && r.height > 0
const sameRect = (a: DOMRect, b: DOMRect) => a.left === b.left && a.top === b.top && a.width === b.width && a.height === b.height
const usable = (el: Element) => !isOurs(el) && !SKIP_TAGS.has(el.tagName) && nonZero(el.getBoundingClientRect())

// Climb past ancestors that look identical, never above the app's first child.
export function parentOf(el: Element): Element | null {
  const first = document.querySelector('#app')?.firstElementChild
  const r = el.getBoundingClientRect()
  for (let cur: Element = el; cur !== first; ) {
    const p: Element | null = cur.parentElement
    if (!p || p === document.body || p === document.documentElement) return null
    if (!sameRect(p.getBoundingClientRect(), r)) return p
    cur = p
  }
  return null
}

export function childOf(el: Element): Element | null {
  return Array.from(el.children).find(usable) ?? null
}

// Where a note's pin sits right now (or where it was made, when its element is gone).
export function pinPoint(n: Note): { x: number; y: number } {
  const el = resolveNote(n)
  const r = el ? el.getBoundingClientRect() : null
  return r ? { x: r.left + n.offset.x * r.width, y: r.top + n.offset.y * r.height } : { x: n.rect.x + n.offset.x * n.rect.w, y: n.rect.y + n.offset.y * n.rect.h }
}

export function fracRect(c: DOMRect, f: { fx: number; fy: number; fw: number; fh: number }): Rect {
  return { x: c.left + f.fx * c.width, y: c.top + f.fy * c.height, w: f.fw * c.width, h: f.fh * c.height }
}

// ---- Box analysis ----------------------------------------------------------------------
export type BoxAnalysis = Omit<BoxInfo, 'fx' | 'fy' | 'fw' | 'fh'> & { container: Element }

// The first piece of text inside an element, not all of it: "Write a handover note", not the whole row.
function firstText(el: Element, max = 40): string {
  const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT)
  for (let n = w.nextNode(); n; n = w.nextNode()) {
    const p = n.parentElement
    if (!p || SKIP_TAGS.has(p.tagName)) continue
    const t = (n.textContent ?? '').replace(/\s+/g, ' ').trim()
    if (t) return t.slice(0, max)
  }
  return ''
}

function pageEls(): { el: Element; r: DOMRect }[] {
  const out: { el: Element; r: DOMRect }[] = []
  for (const el of Array.from(document.body.querySelectorAll('*'))) {
    if (SKIP_TAGS.has(el.tagName) || isOurs(el)) continue
    const r = el.getBoundingClientRect()
    if (nonZero(r)) out.push({ el, r })
  }
  return out
}

export function analyzeBox(b: Rect): BoxAnalysis {
  const T = 1
  const within = (r: DOMRect) => r.left >= b.x - T && r.top >= b.y - T && r.right <= b.x + b.w + T && r.bottom <= b.y + b.h + T
  const holds = (r: DOMRect) => r.left <= b.x + T && r.top <= b.y + T && r.right >= b.x + b.w - T && r.bottom >= b.y + b.h - T
  const all = pageEls()
  const fallback = (document.querySelector('#app') as Element | null) ?? document.body

  // Top-level elements inside the box: inside it while their parent is not.
  const inside = all.filter(({ el, r }) => {
    if (!within(r)) return false
    const p = el.parentElement
    if (!p || p === document.body || p === document.documentElement) return true
    const pr = p.getBoundingClientRect()
    return !(nonZero(pr) && within(pr))
  })

  if (inside.length) {
    const els = inside.map((x) => x.el)
    let c: Element | null = els[0]
    while (c && !els.every((e) => c!.contains(e))) c = c.parentElement
    if (!c || c === document.body || c === document.documentElement) c = fallback
    // Name what the box covers one level down: the container's children it mostly overlaps.
    const kids = Array.from(c.children)
      .filter(usable)
      .map((el) => ({ el, r: el.getBoundingClientRect() }))
    const spread = (f: (r: DOMRect) => number) => (kids.length ? Math.max(...kids.map((k) => f(k.r))) - Math.min(...kids.map((k) => f(k.r))) : 0)
    const vertical = spread((r) => r.top) >= spread((r) => r.left)
    const hit = kids.filter(({ r }) => {
      const ox = Math.min(r.right, b.x + b.w) - Math.max(r.left, b.x)
      const oy = Math.min(r.bottom, b.y + b.h) - Math.max(r.top, b.y)
      return ox > 0 && oy > 0 && (vertical ? oy / r.height : ox / r.width) >= 0.5
    })
    let labels = hit.map((k) => firstText(k.el)).filter(Boolean)
    if (!labels.length) labels = els.map((e) => textOf(e, 40)).filter(Boolean)
    return { container: c, kind: 'content', covers: labels.slice(0, 6), coversMore: Math.max(0, labels.length - 6) }
  }

  // Empty space: the smallest element that holds the whole box, then its neighbours.
  let best: { el: Element; area: number } | null = null
  for (const { el, r } of all) {
    if (!holds(r)) continue
    const area = r.width * r.height
    if (!best || area < best.area) best = { el, area }
  }
  const container = best?.el ?? fallback
  const kids = Array.from(container.children)
    .filter(usable)
    .map((el) => ({ el, r: el.getBoundingClientRect() }))
  const cx = b.x + b.w / 2
  const cy = b.y + b.h / 2
  const pick = (before: (r: DOMRect) => boolean, after: (r: DOMRect) => boolean, edgeB: (r: DOMRect) => number, edgeA: (r: DOMRect) => number) => ({
    b: kids.filter((k) => before(k.r)).sort((x, y) => edgeB(y.r) - edgeB(x.r))[0],
    a: kids.filter((k) => after(k.r)).sort((x, y) => edgeA(x.r) - edgeA(y.r))[0],
  })
  const v = pick((r) => r.bottom <= cy, (r) => r.top >= cy, (r) => r.bottom, (r) => r.top)
  const h = pick((r) => r.right <= cx, (r) => r.left >= cx, (r) => r.right, (r) => r.left)
  // Vertical first: horizontal wins only when it has a full pair and vertical does not.
  let axis: 'vertical' | 'horizontal' = 'vertical'
  if (!(v.b && v.a) && ((h.b && h.a) || (!(v.b || v.a) && (h.b || h.a)))) axis = 'horizontal'
  const p = axis === 'vertical' ? v : h
  const label = (k?: { el: Element }) => (k ? textOf(k.el, 40) || summaryOf(k.el) : undefined)
  const gap = p.b && p.a ? Math.round(Math.max(0, axis === 'vertical' ? p.a.r.top - p.b.r.bottom : p.a.r.left - p.b.r.right)) : undefined
  return { container, kind: 'empty', before: label(p.b), after: label(p.a), gap, axis }
}

// ---- Measuring (hold Alt) --------------------------------------------------------------
export type Redline = { x: number; y: number; w: number; h: number; label: string; lx: number; ly: number }

// Figma-style redlines: facing-edge distances when apart, the four inner distances when nested.
export function redlines(a: DOMRect, b: DOMRect): Redline[] {
  const out: Redline[] = []
  const line = (x1: number, y1: number, x2: number, y2: number) => {
    const horiz = y1 === y2
    const len = horiz ? Math.abs(x2 - x1) : Math.abs(y2 - y1)
    if (len < 0.5) return
    out.push({ x: Math.min(x1, x2), y: Math.min(y1, y2), w: horiz ? len : 1, h: horiz ? 1 : len, label: String(Math.round(len)), lx: (x1 + x2) / 2, ly: (y1 + y2) / 2 })
  }
  const holds = (o: DOMRect, i: DOMRect) => i.left >= o.left - 0.5 && i.top >= o.top - 0.5 && i.right <= o.right + 0.5 && i.bottom <= o.bottom + 0.5
  if (holds(a, b) || holds(b, a)) {
    const [o, i] = holds(a, b) ? [a, b] : [b, a]
    const cx = (i.left + i.right) / 2
    const cy = (i.top + i.bottom) / 2
    line(cx, o.top, cx, i.top)
    line(i.right, cy, o.right, cy)
    line(cx, i.bottom, cx, o.bottom)
    line(o.left, cy, i.left, cy)
    return out
  }
  const xo = Math.min(a.right, b.right) - Math.max(a.left, b.left) > 0
  const yo = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 0
  // When the rects are diagonal the two lines meet in an L: horizontal at a's nearest edge, vertical at b's.
  const bx = b.left >= a.right ? b.left : b.right
  const ay = b.top >= a.bottom ? a.bottom : a.top
  if (!xo) {
    const y = yo ? (Math.max(a.top, b.top) + Math.min(a.bottom, b.bottom)) / 2 : ay
    if (a.right <= b.left) line(a.right, y, b.left, y)
    else line(b.right, y, a.left, y)
  }
  if (!yo) {
    const x = xo ? (Math.max(a.left, b.left) + Math.min(a.right, b.right)) / 2 : bx
    if (a.bottom <= b.top) line(x, a.bottom, x, b.top)
    else line(x, b.bottom, x, a.top)
  }
  return out
}

// ---- Prompt ----------------------------------------------------------------------------
// Text beats classes: `h2 "Hand over work"` finds the element faster than `h2.text-lg`.
export function elementLine(element: string, text: string): string {
  const tag = element.split(/[.\s]/)[0]
  return text ? `${tag} "${text}"` : element
}

export function buildPrompt(list: Note[]): string {
  const out = [`Feedback on ${subject()} (${list.length} ${list.length === 1 ? 'note' : 'notes'})`]
  const routes: string[] = []
  for (const n of list) if (!routes.includes(n.route)) routes.push(n.route)
  for (const r of routes) {
    const group = list.filter((n) => n.route === r)
    out.push('', `## ${r} (${group[0].viewport.replace('x', '×')})`, '')
    // Same numbers as the pins and the list: position among all notes of this page, sent or not.
    const onPage = notes.value.filter((x) => x.route === r)
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
      ta.setAttribute(UI_ATTR, '')
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
