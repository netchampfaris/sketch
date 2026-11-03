// The page's DOM, read for the annotate tools: which element an event is aimed at, a stable selector for it,
// which of the Prototype's components drew it, what a dragged box covers, and the distances between two boxes.
// It runs where the Prototype's document is, in the Viewer shell's frame (runtime/agent/pick.ts, tweakPick.ts). It
// never draws and holds no state but the source file names.
import type { BoxInfo, ElInfo, Rect } from '../shared/protocol'

export type { BoxInfo, ElInfo, Rect }

// The Prototype's source paths, by component name (componentOf, labelOf). Set once the tree is known.
let source: Record<string, string> = {}
export function setSourceFiles(files: Record<string, string>) {
  source = files
  fileMap = null
}

// The tree itself, for Tweak's hard-coded copy (tweakDom.ts copySource). Never sent on.
export const sourceFiles = () => source

export { clamp, typing } from '../shared/dom'
// Capture-phase document listeners, all removed by the returned function.
export function listen(handlers: [string, (e: any) => void][]): () => void {
  for (const [type, fn] of handlers) document.addEventListener(type, fn, true)
  return () => {
    for (const [type, fn] of handlers) document.removeEventListener(type, fn, true)
  }
}


// ---- Our own UI is never a target ------------------------------------------------------
export const UI_ATTR = 'data-annotate-ui'
// Tooltips and toasts (an Undo is pressed while picking) from the component library are portalled out of our markup;
// treat them as ours too. Menus are not: the page's own are commented on, and Sketch's open in hosts of ours.
const OURS = `[${UI_ATTR}],[data-sketch-ui],[data-slot^="tooltip"],[role="tooltip"],[data-sonner-toaster]`
export const isOurs = (el: Node | null | undefined) => {
  const e = el instanceof Element ? el : el?.parentElement
  return !!e?.closest(OURS)
}
// A page menu, popover, list or dialog is open (reka marks each with data-dismissable-layer): it takes
// Escape first. Tooltips come and go with the pointer, so they never hold Escape back.
export const pageLayerOpen = () =>
  [...document.querySelectorAll('[data-dismissable-layer]')].some((l) => !isOurs(l) && !l.querySelector('[role="tooltip"]'))
// One of our own menus is open, such as a comment's ⋯ menu or a tile's. Only menus: our non-modal popovers (the
// @mention list) leave the page's layers as they are.
export const ownMenuOpen = () => [...document.querySelectorAll('[role="menu"][data-state="open"]')].some(isOurs)
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
    for (const path of Object.keys(source)) {
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

// The route a note belongs to: the full path without the ?v= cache-buster, the open canvas (and any old ?annotate).
export function routeKey(route: { path: string; query: Record<string, any> }): string {
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(route.query)) {
    if (k === 'annotate' || k === 'v' || k === 'canvas') continue
    for (const x of Array.isArray(v) ? v : [v]) if (x != null) q.append(k, String(x))
  }
  const s = q.toString()
  return s ? `${route.path}?${s}` : route.path
}

// ---- Geometry --------------------------------------------------------------------------

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

