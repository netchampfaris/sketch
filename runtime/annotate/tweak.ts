// Tweak: change the design tokens of a live element in the browser, then copy the result as a
// prompt for a coding agent. Nothing here touches source files; DOM classes and component props
// are edited, remembered, and re-applied when Vue re-renders.
// The state, token lists, class maths and the prompt live here; TweakLayer.vue draws.
import { computed, ref, shallowRef } from 'vue'
import * as FUI from 'frappe-ui'
import * as FUI_LIST from 'frappe-ui/list'
import { UI_ATTR, active, generatedId, componentOf, elementLine, fileOfName, isOurs, isOursName, nameOfType, newId, readRows, resolve, selectorOf, summaryOf, textOf, vnodeOf } from './annotate'
import { host, isDataFile, pageNameOf, subject } from './host'


// One thing a row says changed: an icon (or a colour swatch) and a short value.
export type Change = { icon?: string; swatch?: { kind: 'ink' | 'bg' | 'border'; cls: string }; text: string }
// One row of the toolbar's tweak list: the element's own text, a count badge for a multi-select, the changes.
export type TweakItem = { id: string; route: string; page: string; title: string; badge: string; changes: Change[] }

// ---- Token candidates -----------------------------------------------------------------------
// Built from the frappe-ui skill. probeTokens() later drops any class the runtime does not style.
const COLORS = ['red', 'green', 'amber', 'blue', 'cyan', 'pink', 'violet', 'orange', 'purple', 'teal', 'yellow']
const range = (a: number, b: number) => Array.from({ length: b - a + 1 }, (_, i) => String(a + i))
const ramp = (pre: string, n: number) => COLORS.flatMap((c) => range(1, n).map((i) => `${pre}${c}-${i}`))
const SIZES = ['2xs', 'xs', 'sm', 'base', 'md', 'lg', 'xl', '2xl', '3xl']
const P_SIZES = SIZES.slice(0, 8)

export type Group = 'ink' | 'style' | 'weight' | 'bg' | 'border' | 'radius' | 'pad' | 'mar' | 'gap'
export type Tokens = Record<Group, string[]>

const SPACE = ['0', '0.5', '1', '1.5', '2', '2.5', '3', '3.5', '4', '5', '6', '7', '8', '10', '12', '16']
const NEG = ['-0.5', '-1', '-1.5', '-2', '-2.5', '-3', '-3.5', '-4']

const CANDIDATES: Tokens = {
  ink: ['text-ink-base', ...range(1, 9).map((i) => `text-ink-gray-${i}`), ...ramp('text-ink-', 9), 'text-ink-blue-link'],
  style: [
    ...SIZES.map((s) => `text-${s}`),
    ...P_SIZES.map((s) => `text-p-${s}`),
    // Composite pattern from the skill (text-base-semibold); the probe drops sizes without one.
    ...SIZES.flatMap((s) => ['medium', 'semibold'].map((w) => `text-${s}-${w}`)),
  ],
  weight: ['font-normal', 'font-medium', 'font-semibold', 'font-bold'],
  bg: ['bg-surface-base', ...range(1, 10).map((i) => `bg-surface-gray-${i}`), ...ramp('bg-surface-', 10), 'bg-surface-sidebar', ...range(1, 3).map((i) => `bg-surface-elevation-${i}`)],
  border: ['border-outline-base', ...range(1, 9).map((i) => `border-outline-gray-${i}`), ...ramp('border-outline-', 10), 'border-outline-elevation-1', 'border-outline-elevation-2'],
  radius: ['rounded-1', 'rounded-4', 'rounded-5', 'rounded-6', 'rounded-full'],
  pad: SPACE,
  mar: [...SPACE, ...NEG],
  gap: SPACE,
}
export const tokens = shallowRef<Tokens>(CANDIDATES)

// Spacing groups keep bare values ('4', '-2'); the others keep whole classes.
export function classOf(group: Group, key: string): string {
  if (group === 'pad') return `p-${key}`
  if (group === 'mar') return key.startsWith('-') ? `-m-${key.slice(1)}` : `m-${key}`
  if (group === 'gap') return `gap-${key}`
  return key
}

const SIG: Record<Group, (cs: CSSStyleDeclaration) => string> = {
  ink: (cs) => cs.color,
  style: (cs) => cs.fontSize + cs.fontWeight + cs.lineHeight,
  weight: (cs) => cs.fontWeight,
  bg: (cs) => cs.backgroundColor,
  border: (cs) => cs.borderTopColor,
  radius: (cs) => cs.borderTopLeftRadius,
  pad: (cs) => cs.paddingTop + cs.paddingLeft,
  mar: (cs) => cs.marginTop + cs.marginLeft,
  gap: (cs) => cs.columnGap,
}

let probed: Promise<void> | null = null
export function probeTokens(): Promise<void> {
  return (probed ??= doProbe().catch(() => {}))
}

async function doProbe() {
  // The sentinel rule has the specificity of one class and sits first in <head>, so any real
  // utility (same specificity, later) overrides it, and a class that sets nothing leaves it.
  const sheet = document.createElement('style')
  sheet.setAttribute(UI_ATTR, '')
  sheet.textContent =
    '.tweak-probe{display:flex;padding:7px;margin:7px;gap:7px;border:7px solid rgb(1,2,3);border-radius:7px;background-color:rgb(1,2,3);color:rgb(1,2,3);font-size:7px;font-weight:111;line-height:7px}'
  document.head.insertBefore(sheet, document.head.firstChild)
  const host = document.createElement('div')
  host.setAttribute(UI_ATTR, '')
  host.style.cssText = 'position:fixed;left:-9999px;top:0;visibility:hidden;pointer-events:none'
  document.body.appendChild(host)
  const mk = (cls: string) => {
    const d = document.createElement('div')
    d.className = `tweak-probe ${cls}`
    host.appendChild(d)
    return d
  }
  try {
    const base = getComputedStyle(mk(''))
    const entries: { g: Group; key: string; el: Element }[] = []
    for (const g of Object.keys(CANDIDATES) as Group[]) for (const key of CANDIDATES[g]) entries.push({ g, key, el: mk(classOf(g, key)) })
    // The runtime Tailwind generates CSS a beat after classes appear.
    await new Promise((r) => setTimeout(r, 250))
    const baseSig = {} as Record<Group, string>
    for (const g of Object.keys(SIG) as Group[]) baseSig[g] = SIG[g](base)
    const keep = {} as Tokens
    for (const g of Object.keys(CANDIDATES) as Group[]) keep[g] = []
    for (const e of entries) if (SIG[e.g](getComputedStyle(e.el)) !== baseSig[e.g]) keep[e.g].push(e.key)
    // If a known-good class did not register, the runtime was slow: keep every candidate.
    if (!keep.pad.includes('4') || !keep.ink.includes('text-ink-gray-7')) return
    tokens.value = keep
  } finally {
    host.remove()
    sheet.remove()
  }
}

// ---- Class categories -----------------------------------------------------------------------
const SIDES = '(?:-(?:t|b|l|r|s|e|tl|tr|bl|br|ss|se|es|ee)(?:-|$))'
export const CAT = {
  pad: /^p[xytrbl]?-/,
  mar: /^-?m[xytrbl]?-/,
  gap: /^gap(?:-[xy])?-/,
  ink: /^text-ink-/,
  style: /^text-(?:p-)?(?:2xs|xs|sm|base|md|lg|xl|2xl|3xl)(?:-(?:normal|medium|semibold|bold))?$/,
  weight: /^font-(?:normal|medium|semibold|bold)$/,
  bg: /^bg-surface-/,
  border: /^border-outline-/,
  radius: new RegExp(`^rounded(?!${SIDES})(?:-\\[.*\\]|-[a-z0-9]+)?$`),
}
export type Cat = keyof typeof CAT
export const catOf = (c: string): Cat | null => ((Object.keys(CAT) as Cat[]).find((k) => CAT[k].test(c)) ?? null)
export const isComposite = (c: string) => /-(?:medium|semibold|bold)$/.test(c)

export const baseClasses = (el: Element): string[] => Array.from(el.classList).filter((c) => !c.includes(':'))

// Responsive and state variants are never edited, but the designer should know they exist.
export function variantNote(el: Element, cat: Cat): string | null {
  const hits = Array.from(el.classList).filter((c) => c.includes(':') && catOf(c.slice(c.lastIndexOf(':') + 1)) === cat)
  if (!hits.length) return null
  const wide = hits.every((c) => /^(?:sm|md|lg|xl|2xl):/.test(c))
  return `Also ${hits.join(', ')}${wide ? ' on wider screens' : ''}`
}

// ---- Spacing maths --------------------------------------------------------------------------
export type Sides = { t: string | null; r: string | null; b: string | null; l: string | null }

// CSS precedence: a side beats its axis, an axis beats the shorthand.
export function readSides(classes: string[], pre: 'p' | 'm'): Sides {
  const v: Record<string, string> = {}
  for (const c of classes) {
    const m = c.match(/^(-)?(p|m)([xytrbl])?-(.+)$/)
    if (m && m[2] === pre) v[m[3] ?? 'a'] = (m[1] ?? '') + m[4]
  }
  return { t: v.t ?? v.y ?? v.a ?? null, r: v.r ?? v.x ?? v.a ?? null, b: v.b ?? v.y ?? v.a ?? null, l: v.l ?? v.x ?? v.a ?? null }
}

const mk = (pre: string, side: string, v: string) => (v.startsWith('-') ? `-${pre}${side}-${v.slice(1)}` : `${pre}${side}-${v}`)

// The smallest class set for four sides: all equal, then equal pairs, then single sides.
export function emitSides(pre: 'p' | 'm', s: Sides): string[] {
  const { t, r, b, l } = s
  if (t != null && t === r && r === b && b === l) return [mk(pre, '', t)]
  const out: string[] = []
  if (l != null && l === r) out.push(mk(pre, 'x', l))
  else {
    if (l != null) out.push(mk(pre, 'l', l))
    if (r != null) out.push(mk(pre, 'r', r))
  }
  if (t != null && t === b) out.push(mk(pre, 'y', t))
  else {
    if (t != null) out.push(mk(pre, 't', t))
    if (b != null) out.push(mk(pre, 'b', b))
  }
  return out
}

// ---- Component instances (the vnode walk is vnodeOf in annotate.ts) -------------------------
// The enum props of frappe-ui components, as far as the skill documents them. A component only
// shows the ones its instance actually declares.
const VARIANTS = ['solid', 'subtle', 'outline', 'ghost']
const FIELD_VARIANTS = ['subtle', 'outline', 'ghost']
const SM_MD_LG = ['sm', 'md', 'lg']
export const KNOWN: Record<string, Record<string, string[]>> = {
  Button: { variant: VARIANTS, theme: ['gray', 'blue', 'green', 'red'], size: ['xs', 'sm', 'md', 'lg'] },
  Badge: { variant: VARIANTS, theme: ['gray', 'blue', 'green', 'red', 'amber', 'violet'], size: SM_MD_LG },
  Avatar: { size: ['xs', 'sm', 'md', 'lg', 'xl', '2xl', '3xl'], shape: ['circle', 'square'] },
  TextInput: { variant: FIELD_VARIANTS, size: SM_MD_LG },
  Select: { variant: FIELD_VARIANTS, size: SM_MD_LG },
  Checkbox: { size: ['sm', 'md'] },
  Switch: { size: ['sm', 'md'] },
}

export type FrappeInfo = { name: string; inst: any; rootEl: Element | null }
export const knownProps = (f: FrappeInfo) => Object.keys(KNOWN[f.name] ?? {}).filter((k) => k in f.inst.props)

// Set when the element was rendered by a frappe-ui component, so it is that component's internals
// (its root included). Slot content our files pass in is rendered by our component: not frappe-ui.
// vnode.ctx is the instance whose template created the vnode.
// What frappe-ui really exports decides, not our own list of files.
const FUI_NAMES = new Map<any, string>()
for (const m of [FUI, FUI_LIST] as Record<string, any>[])
  for (const [k, v] of Object.entries(m)) if (v && (typeof v === 'object' || typeof v === 'function') && !FUI_NAMES.has(v)) FUI_NAMES.set(v, k)
const isFui = (i: any) => !!i && FUI_NAMES.has(i.type)
// The instance whose template created this one, else the one it renders inside.
const up = (i: any) => i?.vnode?.ctx ?? i?.parent
const isOursInst = (i: any) => !isFui(i) && isOursName(nameOfType(i.type))
// Instance name, else the name frappe-ui exports the component under.
const libName = (i: any) => nameOfType(i.type) || FUI_NAMES.get(i.type) || 'frappe-ui'

export function frappeOf(el: Element): FrappeInfo | null {
  const hit = vnodeOf(el)
  const owner = hit?.vn.ctx
  if (!hit || !owner) return null
  let start: any = owner
  if (!isFui(owner)) {
    if (isOursInst(owner)) return null
    // Not exported, not one of our files. A frappe-ui sub-component (SidebarItem) has a frappe-ui
    // component above it before any of ours; another library's wrapper (RouterLink) carrying our
    // classes does not, and stays ours.
    // Climb by whose template created each instance (vnode.ctx), not where it is slotted.
    let p = up(owner)
    while (p && !isOursInst(p) && !isFui(p)) p = up(p)
    if (!p || !isFui(p)) return null
    start = p
  }
  // Climb to the frappe-ui component whose template created this one (Dropdown makes its Button),
  // never to one it is only slotted into (an Avatar inside a HoverCard trigger stays an Avatar).
  let j = hit.stack.indexOf(start)
  while (j > 0) {
    const maker = up(hit.stack[j])
    const k = isFui(maker) ? hit.stack.indexOf(maker) : -1
    if (k < 0 || k >= j) break
    j = k
  }
  const inst = j >= 0 ? hit.stack[j] : start
  const sub = inst.subTree
  const first = Array.isArray(sub?.children) ? sub.children.find((c: any) => c?.el instanceof Element) : null
  const rootEl: Element | null = sub?.el instanceof Element ? sub.el : (first?.el ?? null)
  return { name: libName(inst), inst, rootEl }
}

// What the tag and the header call the element: the component, never a selector.
// The rendering component is named, even when it is a page nobody listed.
function ownerName(el: Element): string {
  let o = vnodeOf(el)?.vn.ctx
  if (!o || isFui(o)) return ''
  // A library wrapper (RouterLink) is named after our component that uses it.
  let p = o
  while (p && !isOursInst(p)) p = up(p)
  if (p) o = p
  return nameOfType(o.type) || ''
}
export const nameOf = (el: Element): string => frappeOf(el)?.name || ownerName(el) || componentOf(el).component || el.tagName.toLowerCase()

// ---- Alike elements -------------------------------------------------------------------------
// One walk of the vnode tree: every element and the component type whose template made it.
// Shift-hover asks on every pointer move: the walk is kept until the DOM gains or loses an element.
let typesCache: Map<Element, any> | null = null
let typesWatch: MutationObserver | null = null
function ctxTypes(): Map<Element, any> {
  if (typesCache) return typesCache
  if (!typesWatch) {
    typesWatch = new MutationObserver(() => (typesCache = null))
    typesWatch.observe(document.body, { childList: true, subtree: true })
  }
  return (typesCache = buildTypes())
}
function buildTypes(): Map<Element, any> {
  const m = new Map<Element, any>()
  const walk = (vn: any) => {
    if (!vn || typeof vn !== 'object') return
    if (vn.component) return walk(vn.component.subTree)
    if (vn.el instanceof Element && typeof vn.type === 'string') m.set(vn.el, vn.ctx?.type ?? null)
    if (vn.suspense) walk(vn.suspense.activeBranch)
    if (Array.isArray(vn.children)) vn.children.forEach(walk)
  }
  walk((document.querySelector('#app') as any)?._vnode)
  return m
}
function jaccard(a: string[], b: string[]): number {
  if (!a.length && !b.length) return 1
  const sb = new Set(b)
  let n = 0
  for (const c of a) if (sb.has(c)) n++
  return n / (a.length + b.length - n)
}
// Same maker, same tag, mostly the same classes: a calendar cell and the other cells.
// Tweaked elements are compared by the classes they started with, so an edit never makes them stray.
function originals(): Map<Element, string[]> {
  const m = new Map<Element, string[]>()
  for (const t of tweaks.value) {
    const e = t.route === currentRoute ? elOf(t) : null
    if (e) m.set(e, t.original.classes)
  }
  return m
}
export function alikeOf(el: Element, types: Map<Element, any> = ctxTypes(), orig: Map<Element, string[]> = originals()): Element[] {
  if (!types.has(el)) return []
  const type = types.get(el)
  const looks = (e: Element) => orig.get(e) ?? baseClasses(e)
  const base = looks(el)
  const out: Element[] = []
  for (const c of document.body.querySelectorAll(el.tagName)) {
    if (out.length >= 300) break
    if (c === el || !types.has(c) || types.get(c) !== type || isOurs(c) || jaccard(base, looks(c)) < 0.75) continue
    out.push(c)
  }
  return out
}
// The copies of a whole selection (not the picks themselves), and the alike count of the page when
// every pick is a copy of the first one; 0 when the picks were not alike.
export function alikeSet(list: Element[]): { copies: Element[]; total: number } {
  if (!list.length) return { copies: [], total: 0 }
  const types = ctxTypes()
  const orig = originals()
  const picked = new Set(list)
  // Copies of the first pick only: alike is not transitive, and a union would keep growing
  // "Select all" after every click on it.
  const first = alikeOf(list[0], types, orig)
  const same = list.every((e, i) => i === 0 || first.includes(e))
  return { copies: first.filter((x) => !picked.has(x)), total: same ? new Set([list[0], ...first]).size : 0 }
}

// ---- Hard-coded copy ------------------------------------------------------------------------
// The page embeds the prototype's files. A text is copy when a file other than the data files and
// our own tooling contains it as a literal; text that appears nowhere is computed or from data.
let sources: { copy: [string, string][]; data: [string, string][] } | null = null
const squash = (s: string) => s.replace(/\s+/g, ' ')
function loadSources() {
  if (sources) return sources
  sources = { copy: [], data: [] }
  try {
    for (const [path, body] of Object.entries(host.files)) {
      if (!path.startsWith('src/') || typeof body !== 'string') continue
      // Comments quote text too (\"Joined 12 days ago\" in a doc comment) and are not copy.
      const code = body.replace(/\/\*[\s\S]*?\*\//g, '').replace(/<!--[\s\S]*?-->/g, '').replace(/(^|[^:\w"'`\\])\/\/.*$/gm, '$1')
      ;(isDataFile(path) ? sources.data : sources.copy).push([path, squash(code)])
    }
  } catch {}
  return sources
}
const copyCache = new Map<string, { copy: string[]; data: boolean }>()
// The files of the components that rendered this element, page included.
function chainFiles(el: Element): string[] {
  const names = (vnodeOf(el)?.stack ?? []).map((i: any) => nameOfType(i.type)).filter((n): n is string => !!n && isOursName(n))
  const own = ownerName(el)
  if (own) names.push(own)
  return [...new Set(names.map((n) => fileOfName(n)).filter((f): f is string => !!f))]
}
// Where this text is hard-coded, or null when it is data or computed. A file of a component the
// element sits in wins, then data wins over an incidental literal (a name in a fallback), then any
// other copy file (nav.ts, lib).
export function copySource(text: string, el: Element): { files: string[] } | null {
  const norm = squash(text.trim())
  // Numbers and times are never headings: skip them ("19" is in every file as part of something).
  if (norm.length < 2 || /^[\d\s.,:%+\-/hmsdk]*$/.test(norm)) return null
  let h = copyCache.get(norm)
  if (!h) {
    h = findText(norm)
    copyCache.set(norm, h)
  }
  // App config (nav.ts, lib, router) is copy wherever it renders; a .vue file only for its own chain.
  const chain = chainFiles(el)
  const mine = h.copy.filter((f) => !f.endsWith('.vue') || chain.includes(f))
  if (mine.length) return { files: mine.slice(0, 3) }
  if (h.data || !h.copy.length) return null
  return { files: h.copy.slice(0, 3) }
}
function findText(norm: string): { copy: string[]; data: boolean } {
  const variants = [norm, norm.replace(/'/g, "\\'"), norm.replace(/'/g, '&apos;'), norm.replace(/'/g, '&#39;'), norm.replace(/&/g, '&amp;')]
  // The literal stands alone: between quotes, or between tags, not inside a longer sentence.
  const re = new RegExp(`[>'"\`] ?(?:${variants.map((v) => v.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')}) ?[<'"\`]`)
  const src = loadSources()
  return { copy: src.copy.filter(([, body]) => re.test(body)).map(([p]) => p), data: src.data.some(([, body]) => re.test(body)) }
}

// The text nodes an element is made of, in document order: the places a Copy index points at.
// A node we once saw as text stays a place after it is emptied (or typed into a number).
const seen = new WeakSet<Text>()
function copyNodes(el: Element): Text[] {
  const nodes: Text[] = []
  const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT)
  for (let n = w.nextNode() as Text | null; n; n = w.nextNode() as Text | null) {
    const v = n.nodeValue?.trim() ?? ''
    // A count beside the label (the Inbox badge) is a number, not copy.
    if (seen.has(n) || (v && !/^\d+\+?$/.test(v))) {
      seen.add(n)
      nodes.push(n)
    }
  }
  return nodes
}
const COUNT = /^(.*\S)(\s+\d+\+?)$/
function writeCopy(node: Text, to: string, stem = false) {
  const v = node.nodeValue ?? ''
  const core = v.trim()
  const lead = core ? (v.match(/^\s*/)?.[0] ?? '') : v
  const trail = core ? (v.match(/\s*$/)?.[0] ?? '') : ''
  // A stem keeps the count after it exactly as the page wrote it, read from the live text so a
  // changing count still works. With the label emptied the count is all that is left.
  const count = stem ? (core.match(COUNT)?.[2] ?? (/^\d+\+?$/.test(core) ? ` ${core}` : '')) : ''
  const next = lead + to + count + trail
  if (v !== next) node.nodeValue = next
}
// What the Copy fields need: for each hard-coded text, the original, the current text, and where
// the literal lives. A frappe-ui root offers each of its texts (up to 6, each text once); any
// other element only when it is made of exactly one.
const MAX_COPY = 6
export function copyInfos(el: Element): Copy[] {
  const t = tweakFor(el)
  const nodes = copyNodes(el)
  const root = frappeOf(el)?.rootEl === el
  if (!root && nodes.length !== 1) return []
  const out: Copy[] = []
  nodes.forEach((n, i) => {
    const kept = t?.copies?.find((c) => c.i === i)
    let c: Copy | null = null
    if (kept) c = { ...kept, files: kept.files ?? [] }
    else {
      const text = n.nodeValue!.trim()
      let s = text ? copySource(text, el) : null
      let from = text
      let stem = false
      if (!s) {
        // "Needs you  14" is built in a template: the label before the count may be the literal.
        const m = text.match(COUNT)
        s = m ? copySource(m[1], el) : null
        if (m && s) [from, stem] = [m[1], true]
      }
      if (s) c = { i, from, to: from, files: s.files, stem }
    }
    if (c && !out.some((o) => o.from === c!.from) && out.length < MAX_COPY) out.push(c)
  })
  return out
}
export function setCopy(el: Element, i: number, to: string) {
  const info = copyInfos(el).find((c) => c.i === i)
  if (!info) return
  const t = ensureTweak(el)
  t.copies ??= []
  let c = t.copies.find((x) => x.i === i)
  if (!c) t.copies.push((c = { i, from: info.from, to: info.from, files: info.files, stem: info.stem }))
  c.to = to
  const node = copyNodes(el)[i]
  if (node) writeCopy(node, to, c.stem)
  settle()
  touch()
}

// A hand-made look-alike of a frappe-ui component: the name of the component it should be.
export function handRolledOf(el: Element): string | null {
  const tag = el.tagName
  const role = el.getAttribute('role')
  const cls = baseClasses(el)
  const has = (re: RegExp) => cls.some((c) => re.test(c))
  if (role === 'switch') return 'Switch'
  if (role === 'tablist') return 'Tabs'
  if (tag === 'INPUT') {
    const type = (el as HTMLInputElement).type
    if (type === 'checkbox') return 'Checkbox'
    return ['text', 'email', 'search', 'tel', 'url', 'password', 'number'].includes(type) ? 'TextInput' : null
  }
  if (tag === 'TEXTAREA') return 'TextInput'
  const text = (el.textContent ?? '').trim()
  const r = el.getBoundingClientRect()
  // A clickable <button> is only a Button look-alike when it is button-shaped: one short line,
  // button height. Calendar days, list rows and cards are native buttons for access, and rightly so.
  if (tag === 'BUTTON' || role === 'button')
    return r.height <= 40 && text.length <= 30 && !/\n/.test((el as HTMLElement).innerText ?? '') && !el.querySelector('div,p,img,ul,table') ? 'Button' : null
  const round = has(/^rounded-full$/)
  const only = el.children.length === 1 ? (el.children[0] as HTMLElement) : null
  if (round && has(/^h-(?:1|1\.5|2)$/) && only && /%$/.test(only.style.width)) return 'Progress'
  if (round && Math.abs(r.width - r.height) <= 1 && r.width >= 16 && r.width <= 48 && (tag === 'IMG' || (text.length > 0 && text.length <= 3))) return 'Avatar'
  if (/^inline/.test(getComputedStyle(el).display) && has(/^rounded/) && has(CAT.bg) && has(/^px-/) && has(/^text-(?:p-)?(?:xs|sm)$/) && text && text.length <= 20) return 'Badge'
  return null
}

// ---- Tweaks state ---------------------------------------------------------------------------
// i is the place of the text among the element's text nodes, in document order.
// stem: the text is a label followed by a live count ("Needs you  14"); only the label is the copy.
export type Copy = { i: number; from: string; to: string; files?: string[]; stem?: boolean }
export type Tweak = {
  id: string
  route: string
  selector: string
  component: string
  file: string
  path: string[]
  kind: string // frappe-ui component name when the element is its root
  element: string
  text: string
  viewport: string
  original: { classes: string[]; props: Record<string, any> }
  classes: string[] // current base classes
  props: Record<string, any>
  opener?: string // selector of what opens the floating layer this element lives in
  label?: string // the first of several texts: what the list calls the element
  items?: number // children of a vertical stack, for "List of n" while the element is not on the page
  swap?: string // a hand-rolled element that should become this frappe-ui component
  copies?: Copy[] // hard-coded texts, edited in place
  copy?: { from: string; to: string } // an older session's single copy: moved into copies on load
  copyFiles?: string[]
  group?: string // tweaks committed together in one multi-select edit share this
  alike?: number // alike elements on the page then, picks included; 0 when the picks were not alike
}

export const tweaks = ref<Tweak[]>([])
// The server's rows, checked and brought up to date: an older session's single `copy` becomes `copies`.
export function restoreTweaks(rows: unknown): Tweak[] {
  return readRows<Tweak>(rows, (t) => Array.isArray(t.classes) && Array.isArray(t.original?.classes) && !!t.props && !!t.original.props).map((t) => {
    if (t.copy && !t.copies) t.copies = [{ i: 0, from: t.copy.from, to: t.copy.to, files: t.copyFiles }]
    delete t.copy
    delete t.copyFiles
    return t
  })
}
// Live elements stay out of the stored state: WeakRefs do not serialise.
const refs = new Map<string, WeakRef<Element>>()
// Bumped after every commit so the panel re-reads the DOM.
export const rev = ref(0)
export const touch = () => void rev.value++

let currentRoute = ''
export const setRoute = (k: string) => void (currentRoute = k)

// Fields are compared against the original; a tweak whose fields all match is not a tweak.
const diffOf = (t: Tweak) => ({
  removed: t.original.classes.filter((c) => !t.classes.includes(c)),
  added: t.classes.filter((c) => !t.original.classes.includes(c)),
})
const propKeys = (t: Tweak) => Object.keys(t.props).filter((k) => t.props[k] !== t.original.props[k])
// What a class list amounts to for one category, so a rewrite that changes nothing
// (px-2.5 py-2.5 to p-2.5, equal sides collapsed) is not a change.
function effectOf(classes: string[], cat: Cat): string {
  if (cat === 'pad') return JSON.stringify(readSides(classes, 'p'))
  if (cat === 'mar') return JSON.stringify(readSides(classes, 'm'))
  return [...classes].reverse().find((c) => CAT[cat].test(c)) ?? ''
}
function catsChanged(t: Tweak): Cat[] {
  return (Object.keys(CAT) as Cat[]).filter((c) => effectOf(t.original.classes, c) !== effectOf(t.classes, c))
}
// Classes outside every category are compared as they are.
// A block container whose children sit one under another, like a Figma auto layout without the
// layout: it can have a gap once it is made a flex column.
export const STACK_CLASSES = ['flex', 'flex-col']
const visibleKids = (el: Element) =>
  Array.from(el.children).filter((c) => {
    if (isOurs(c)) return false
    const cs = getComputedStyle(c)
    return cs.display !== 'none' && cs.position !== 'absolute' && cs.position !== 'fixed'
  })
export function isVStack(el: Element): boolean {
  const d = getComputedStyle(el).display
  if (d !== 'block' && d !== 'flow-root') return false
  for (const n of Array.from(el.childNodes)) if (n.nodeType === 3 && n.nodeValue?.trim()) return false
  const kids = visibleKids(el)
  if (kids.length < 2) return false
  let bottom = -Infinity
  for (const c of kids) {
    if (getComputedStyle(c).display.startsWith('inline')) return false
    const r = c.getBoundingClientRect()
    if (r.top < bottom - 1) return false
    bottom = r.bottom
  }
  return true
}
// A stack this tweak turned into a flex column: still a stack after the edit.
export const madeStack = (t: Tweak | undefined) => !!t && STACK_CLASSES.every((c) => t.classes.includes(c) && !t.original.classes.includes(c))

const copiesChanged = (t: Tweak) => (t.copies ?? []).filter((c) => c.to !== c.from)
function otherChanged(t: Tweak): boolean {
  const d = diffOf(t)
  // The flex column a stack's gap needs is part of that gap, not a change of its own.
  const gap = catsChanged(t).includes('gap')
  return [...d.removed, ...d.added].some((c) => !catOf(c) && !(gap && STACK_CLASSES.includes(c)))
}
export const isChanged = (t: Tweak) => !!(catsChanged(t).length || otherChanged(t) || propKeys(t).length || t.swap || copiesChanged(t).length)
// One multi-select edit counts once, as the list shows it.
export const tweakCount = computed(() => rows.value.length)

export function elOf(t: Tweak): Element | null {
  const r = refs.get(t.id)?.deref()
  if (r?.isConnected) return r
  if (t.route !== currentRoute) return null
  const el = resolve(t.selector)
  if (el) refs.set(t.id, new WeakRef(el))
  return el
}
export const tweakFor = (el: Element): Tweak | undefined => tweaks.value.find((t) => t.route === currentRoute && elOf(t) === el)

// What last opened something (a popover, a menu): the trigger inside the app with aria-expanded,
// aria-haspopup or aria-controls. A tweak made inside that layer keeps it, to open it again.
let lastOpener: string | null = null
function recordOpener(e: Event) {
  // While a tool is picking, clicks pick; they open nothing.
  if (active.value) return
  const t = e.target
  const app = document.querySelector('#app')
  if (!(t instanceof Element) || !app?.contains(t) || isOurs(t)) return
  const o = t.closest('[aria-expanded],[aria-haspopup],[aria-controls]')
  if (o && app.contains(o)) lastOpener = openerSelector(o)
}
// A handle that survives a reload: the aria-label (under the nearest stable id, when it has one),
// else the structural path with generated ids skipped. Each is kept only if it finds this element.
function openerSelector(o: Element): string {
  const label = o.getAttribute('aria-label')
  if (label) {
    const q = `[aria-label="${CSS.escape(label)}"]`
    let scope = ''
    for (let p = o.parentElement; p && p !== document.body; p = p.parentElement) if (p.id && !generatedId(p.id)) { scope = `#${CSS.escape(p.id)} `; break }
    for (const s of [scope + q, q]) if (resolve(s) === o) return s
  }
  return selectorOf(o, true)
}
export const openerOfRow = (id: string): string | undefined => rows.value.find((x) => x.id === id)?.ts.find((t) => t.opener)?.opener
// The first of an element's texts, only when it has several.
function firstOfMany(el: Element): string {
  const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT)
  const texts: string[] = []
  for (let n = w.nextNode(); n; n = w.nextNode()) if (n.nodeValue?.trim()) texts.push(squash(n.nodeValue.trim()))
  return texts.length > 1 ? texts[0].slice(0, 60) : ''
}

// Created on the first preview, before any write, so `original` is the page as it was.
export function ensureTweak(el: Element): Tweak {
  const ex = tweakFor(el)
  if (ex) return ex
  const info = componentOf(el)
  const own = ownerName(el)
  if (isOursName(own)) Object.assign(info, { component: own, file: fileOfName(own) })
  const f = frappeOf(el)
  const base = baseClasses(el)
  const props: Record<string, any> = {}
  if (f) for (const k of knownProps(f)) props[k] = f.inst.props[k]
  const t: Tweak = {
    id: newId(),
    route: currentRoute,
    selector: selectorOf(el),
    component: info.component,
    file: info.file ?? '',
    path: info.chain,
    kind: f ? f.name : '',
    element: summaryOf(el),
    text: textOf(el),
    label: firstOfMany(el) || undefined,
    items: isVStack(el) ? visibleKids(el).length : undefined,
    opener: !document.querySelector('#app')?.contains(el) && !isOurs(el) ? (lastOpener ?? undefined) : undefined,
    viewport: `${window.innerWidth}×${window.innerHeight}`,
    original: { classes: base, props: { ...props } },
    classes: [...base],
    props,
  }
  tweaks.value = [...tweaks.value, t]
  refs.set(t.id, new WeakRef(el))
  return tweaks.value[tweaks.value.length - 1]
}

// Drop tweaks that match the page again.
export function settle() {
  const keep = tweaks.value.filter(isChanged)
  if (keep.length !== tweaks.value.length) {
    // A dropped tweak no longer needs its live element.
    for (const t of tweaks.value) if (!keep.includes(t)) refs.delete(t.id)
    tweaks.value = keep
  }
}

// ---- Writing --------------------------------------------------------------------------------
function writeDom(el: Element, next: string[]) {
  const cur = baseClasses(el)
  const rm = cur.filter((c) => !next.includes(c))
  const add = next.filter((c) => !cur.includes(c))
  if (rm.length) el.classList.remove(...rm)
  if (add.length) el.classList.add(...add)
}

// While a dropdown is previewing, the observer must not undo the preview.
let previewing = false
export function setPreviewing(v: boolean) {
  previewing = v
  if (!v) syncSoon()
}

// Every edit takes a list: one element, or the whole selection, each with its own next value.
export type GroupMeta = { id: string; alike: number }
export type ClassEdit = [Element, string[]]
export type PropEdit = [Element, any]

// A multi-element commit is one group; a later edit of an element alone leaves it.
function tagGroup(els: Element[], g?: GroupMeta) {
  for (const e of els) {
    const t = tweakFor(e)
    if (!t) continue
    if (g && els.length > 1) {
      t.group = g.id
      t.alike = g.alike
    } else {
      delete t.group
      delete t.alike
    }
  }
}

export function previewClasses(list: ClassEdit[]) {
  list.forEach(([e]) => ensureTweak(e))
  setPreviewing(true)
  list.forEach(([e, n]) => writeDom(e, n))
}
export function commitClasses(list: ClassEdit[], g?: GroupMeta) {
  for (const [e, n] of list) {
    const t = ensureTweak(e)
    t.classes = Array.from(new Set(n))
    writeDom(e, t.classes)
  }
  setPreviewing(false)
  tagGroup(list.map(([e]) => e), g)
  settle()
  touch()
}
export function cancelPreview(list: ClassEdit[]) {
  for (const [e, c] of list) writeDom(e, c)
  setPreviewing(false)
  settle()
}

export function setProps(list: PropEdit[], key: string, commit: boolean, g?: GroupMeta) {
  list.forEach(([e]) => ensureTweak(e))
  setPreviewing(!commit)
  for (const [e, v] of list) {
    const f = frappeOf(e)
    if (!f) continue
    f.inst.props[key] = v
    f.inst.update()
    if (commit) {
      const t = tweakFor(e)
      if (t) t.props[key] = v
    }
  }
  if (commit) {
    tagGroup(list.map(([e]) => e), g)
    settle()
    touch()
  }
}
export function cancelProps(list: PropEdit[], key: string) {
  for (const [e, v] of list) {
    const f = frappeOf(e)
    if (!f) continue
    f.inst.props[key] = v
    f.inst.update()
  }
  setPreviewing(false)
  settle()
}

// ---- Keeping tweaks applied -----------------------------------------------------------------
// Vue rewrites class and props on re-render. Re-apply only the difference from the original,
// so classes Vue changes for its own reasons (an active state) are left alone.
function syncOne(t: Tweak) {
  const el = elOf(t)
  if (!el) return
  // A re-render resets the text: write it again (only when it differs, so the observer settles).
  for (const c of copiesChanged(t)) {
    const node = copyNodes(el)[c.i]
    if (node) writeCopy(node, c.to, c.stem)
  }
  const d = diffOf(t)
  // frappe-ui components take props only: a class change stored against one (an older session) is dropped.
  if ((d.added.length || d.removed.length) && frappeOf(el)) {
    t.classes = [...t.original.classes]
    settle()
    return
  }
  const cur = baseClasses(el)
  const rm = d.removed.filter((c) => cur.includes(c))
  const add = d.added.filter((c) => !cur.includes(c))
  if (rm.length) el.classList.remove(...rm)
  if (add.length) el.classList.add(...add)
  const keys = propKeys(t)
  if (!keys.length) return
  const f = frappeOf(el)
  if (!f) return
  let dirty = false
  for (const k of keys)
    if (f.inst.props[k] !== t.props[k]) {
      f.inst.props[k] = t.props[k]
      dirty = true
    }
  if (dirty) f.inst.update()
}

let mo: MutationObserver | null = null
let timer = 0
let syncing = false
let started = false

// Tweaked elements (class changes) and their ancestors (the element being replaced).
function watchTargets() {
  if (!mo) return
  mo.disconnect()
  const top = document.querySelector('#app')?.parentElement
  // One observe call per node: a second would replace the first one's options (a tweaked element
  // that is also another tweak's ancestor would lose its class watch), so merge them first.
  const opts = new Map<Element, MutationObserverInit>()
  const want = (n: Element, o: MutationObserverInit) => opts.set(n, { ...opts.get(n), ...o })
  // Watch <body> too when a tweak is missing or lives in a floating layer: the layer itself is a
  // child of <body>, so its removal (the close) is seen there and the next open can be re-applied.
  let missing = false
  const app = document.querySelector('#app')
  for (const t of tweaks.value) {
    if (t.route !== currentRoute) continue
    const el = elOf(t)
    if (!el) {
      missing = true
      continue
    }
    if (app && !app.contains(el)) missing = true
    want(el, t.copies?.length ? { attributes: true, attributeFilter: ['class'], characterData: true, childList: true, subtree: true } : { attributes: true, attributeFilter: ['class'] })
    for (let p = el.parentElement; p && p !== top && p !== document.body; p = p.parentElement) want(p, { childList: true })
  }
  // A tweak whose element is not on the page (a popover that is closed) waits for new layers under <body>.
  if (missing) want(document.body, { childList: true })
  for (const [n, o] of opts) mo.observe(n, o)
}

// The guard plus idempotence break the loop: our own write re-fires the observer, finds nothing
// to change, and stops.
function run() {
  timer = 0
  if (syncing || previewing || !started) return
  syncing = true
  try {
    for (const t of tweaks.value) if (t.route === currentRoute) syncOne(t)
    watchTargets()
  } finally {
    syncing = false
  }
}
export function syncSoon() {
  if (started && !timer) timer = window.setTimeout(run, 100)
}

let retries: number[] = []
// The page may still be mounting after a route change: try again a few times.
export function reapply() {
  retries.forEach(clearTimeout)
  retries = [0, 250, 700].map((ms) => window.setTimeout(() => (started ? run() : undefined), ms))
}

export function startSync() {
  started = true
  mo = new MutationObserver((rs) => {
    syncSoon()
    // A popover opening adds its layer under <body>; its content may fill in a moment later.
    if (rs.some((r) => r.target === document.body && Array.from(r.addedNodes).some((n) => n instanceof Element && !isOurs(n)))) reapply()
  })
  for (const t of ['pointerdown', 'click']) document.addEventListener(t, recordOpener, true)
  reapply()
}
export function stopSync() {
  started = false
  for (const t of ['pointerdown', 'click']) document.removeEventListener(t, recordOpener, true)
  typesWatch?.disconnect()
  typesWatch = null
  typesCache = null
  mo?.disconnect()
  mo = null
  clearTimeout(timer)
  timer = 0
  retries.forEach(clearTimeout)
  retries = []
}

// Put one element back as the page had it.
function revert(t: Tweak) {
  const el = elOf(t)
  if (!el) return
  for (const c of t.copies ?? []) {
    const node = copyNodes(el)[c.i]
    if (node) writeCopy(node, c.from, c.stem)
  }
  const d = diffOf(t)
  el.classList.remove(...d.added)
  el.classList.add(...d.removed)
  const f = propKeys(t).length ? frappeOf(el) : null
  if (f) {
    for (const k of propKeys(t)) f.inst.props[k] = t.original.props[k]
    f.inst.update()
  }
}

export function resetAll() {
  tweaks.value.forEach(revert)
  tweaks.value = []
  touch()
}

// A row of the list or the prompt: one tweak, or the tweaks of a multi-select edit that read the same.
type Row = { id: string; ts: Tweak[] }
// Only the grouping key of a multi-select edit: two picks read the same when this does.
function changesOf(t: Tweak): string[] {
  return displayChanges(t).map((c) => `${c.icon ?? ''}|${c.swatch?.cls ?? ''}|${c.text}`)
}
function rowsOf(list: Tweak[]): Row[] {
  const rows: Row[] = []
  const byKey = new Map<string, Row>()
  for (const t of list) {
    if (!t.group) {
      rows.push({ id: t.id, ts: [t] })
      continue
    }
    const key = `${t.group}|${t.route}|${t.kind || t.component}|${changesOf(t).join('|')}`
    let r = byKey.get(key)
    if (!r) {
      // The first cluster of a group keeps the group id; a second one (picks edited apart) gets a suffix.
      const n = [...byKey.keys()].filter((k) => k.startsWith(`${t.group}|`)).length
      r = { id: n ? `${t.group}~${n}` : t.group, ts: [] }
      byKey.set(key, r)
      rows.push(r)
    }
    r.ts.push(t)
  }
  return rows
}
const rows = computed(() => rowsOf(tweaks.value.filter(isChanged)))

// The live elements behind a row, for selecting them again.
export function elsOfRow(id: string): Element[] {
  const r = rows.value.find((x) => x.id === id)
  return (r?.ts.map(elOf).filter(Boolean) ?? []) as Element[]
}

export function removeTweak(id: string) {
  const r = rows.value.find((x) => x.id === id)
  if (!r) return
  for (const t of r.ts) {
    revert(t)
    refs.delete(t.id)
  }
  const gone = new Set(r.ts.map((t) => t.id))
  tweaks.value = tweaks.value.filter((x) => !gone.has(x.id))
  touch()
}

// "Add to prompt" on a hand-rolled element: a change that is only a note for the agent.
export function toggleSwap(el: Element, name: string) {
  const t = ensureTweak(el)
  t.swap = t.swap ? '' : name
  settle()
  touch()
}

const roleOf = (t: Tweak) => t.element.split(/[.\s]/)[0]

// "4 → 3", "H 4 → 3", or one part per side when the sides moved differently.
const SIDE_KEYS = ['t', 'r', 'b', 'l'] as const
function spaceText(from: Sides, to: Sides): string {
  const ch = SIDE_KEYS.filter((k) => from[k] !== to[k])
  const v = (x: string | null) => x ?? '0'
  if (!ch.length) return ''
  if (ch.every((k) => from[k] === from[ch[0]] && to[k] === to[ch[0]])) {
    const has = (...ks: string[]) => ch.length === ks.length && ks.every((k) => (ch as string[]).includes(k))
    const label = ch.length === 4 ? '' : has('l', 'r') ? 'H ' : has('t', 'b') ? 'V ' : `${ch.map((k) => k.toUpperCase()).join('')} `
    return `${label}${v(from[ch[0]])} → ${v(to[ch[0]])}`
  }
  return ch.map((k) => `${k.toUpperCase()} ${v(from[k])} → ${v(to[k])}`).join(', ')
}
const gapOf = (c: string) => c.replace(/^gap(?:-[xy])?-/, '') || '0'

// What the list shows for a tweak: icon plus value, only for changes that change the page.
function displayChanges(t: Tweak): Change[] {
  const out: Change[] = []
  // The new wording itself, so the row says what the copy became, not just that it changed.
  const copies = copiesChanged(t)
  if (copies.length) {
    const to = copies[0].to.trim()
    const shown = to.length > 32 ? `${to.slice(0, 31)}…` : to
    const more = copies.length > 1 ? ` +${copies.length - 1}` : ''
    out.push({ icon: 'lucide-text-cursor', text: `${shown ? `“${shown}”` : 'No text'}${more}` })
  }
  const from = t.original.classes
  const to = t.classes
  for (const c of catsChanged(t)) {
    const f = effectOf(from, c)
    const n = effectOf(to, c)
    if (c === 'pad') out.push({ icon: 'lucide-square-dashed', text: spaceText(readSides(from, 'p'), readSides(to, 'p')) })
    else if (c === 'mar') out.push({ icon: 'lucide-move-vertical', text: spaceText(readSides(from, 'm'), readSides(to, 'm')) })
    else if (c === 'gap') out.push({ icon: 'lucide-between-horizontal-start', text: `${f ? gapOf(f) : '0'} → ${n ? gapOf(n) : '0'}` })
    else if (c === 'style') out.push({ icon: 'lucide-type', text: n ? n.replace(/^text-/, '') : 'None' })
    else if (c === 'radius') out.push({ icon: 'lucide-square-round-corner', text: n ? n.replace(/^rounded-?/, '') || 'default' : 'None' })
    else if (c === 'weight') out.push({ text: `weight ${n ? n.replace('font-', '') : 'None'}` })
    else out.push(n ? { swatch: { kind: c, cls: n }, text: n.replace(/^(?:text-ink-|bg-surface-|border-outline-)/, '') } : { text: `${c === 'ink' ? 'colour' : c} None` })
  }
  for (const k of propKeys(t)) out.push({ text: `${k} ${t.props[k]}` })
  if (t.swap) out.push({ text: `Use ${t.swap}` })
  if (otherChanged(t)) out.push({ text: 'classes' })
  return out
}

// How many things a vertical stack holds: counted live, else as it was when the tweak was made.
function stackCount(t: Tweak): number {
  const el = elOf(t)
  return el && (isVStack(el) || madeStack(t)) ? visibleKids(el).length : (t.items ?? 0)
}
const textsOf = (r: Row) => {
  const ts = r.ts.map((t) => t.text).filter(Boolean)
  return ts.length ? `${ts.slice(0, 3).map((x) => x.slice(0, 20)).join(', ')}${ts.length > 3 ? '…' : ''}` : ''
}
export const tweakItems = computed<TweakItem[]>(() =>
  rows.value.map((r) => {
    const t = r.ts[0]
    const many = r.ts.length > 1
    const fallback = t.kind || t.component || roleOf(t)
    const a = t.alike ?? 0
    return {
      id: r.id,
      route: t.route,
      page: pageNameOf(t.route),
      title: (many ? textsOf(r) : stackCount(t) ? `List of ${stackCount(t)}` : t.label || t.text.trim()) || fallback,
      badge: many ? (a ? `${r.ts.length} of ${a}` : `${r.ts.length} items`) : '',
      changes: displayChanges(t),
    }
  }),
)

// ---- Prompt ---------------------------------------------------------------------------------
// Replacements pair up by category: `pl-2 → pl-3`; the rest read `add X` / `remove X`.
function classChanges(t: Tweak): string[] {
  const d = diffOf(t)
  const groups = new Map<string, { rm: string[]; ad: string[] }>()
  const g = (c: string) => {
    const k = catOf(c) ?? (STACK_CLASSES.includes(c) ? 'gap' : `other:${c}`)
    if (!groups.has(k)) groups.set(k, { rm: [], ad: [] })
    return groups.get(k)!
  }
  d.removed.forEach((c) => g(c).rm.push(c))
  d.added.forEach((c) => g(c).ad.push(c))
  const real = catsChanged(t)
  return [...groups.entries()].filter(([k]) => !(k in CAT) || real.includes(k as Cat)).map(([, x]) => (x.rm.length && x.ad.length ? `${x.rm.join(' ')} → ${x.ad.join(' ')}` : x.ad.length ? `add ${x.ad.join(' ')}` : `remove ${x.rm.join(' ')}`))
}

function changeLines(t: Tweak): string[] {
  const out: string[] = []
  const cl = classChanges(t).join(', ')
  if (cl) out.push(`   Classes: ${cl}`)
  const pk = propKeys(t)
  if (pk.length) out.push(`   Props: ${pk.map((k) => `${k} ${t.original.props[k]} → ${t.props[k]}`).join(', ')}`)
  return out
}

export function buildTweakPrompt(): string {
  const all = rows.value
  const n = all.length
  const out = [
    "These are visual targets from a designer. Match the rendered result; the class edits show one way to get there. If it's cleaner to fix it in the shared component, a token, or the parent layout, do that instead, and say what you did.",
    '',
    `Tweaks on ${subject()} (${n} ${n === 1 ? 'tweak' : 'tweaks'})`,
  ]
  const routes: string[] = []
  for (const r of all) if (!routes.includes(r.ts[0].route)) routes.push(r.ts[0].route)
  for (const route of routes) {
    const group = all.filter((r) => r.ts[0].route === route)
    out.push('', `## ${route} (${group[0].ts[0].viewport})`, '')
    group.forEach((r, i) => {
      const t = r.ts[0]
      const where = t.component ? `${t.component}${t.file ? ` (${t.file})` : ''}` : ''
      if (r.ts.length > 1) {
        // One line for the whole multi-select edit.
        const quoted = r.ts.map((x) => x.text).filter(Boolean)
        const shown = quoted.slice(0, 3).map((x) => `"${x.slice(0, 20)}"`).join(', ') + (quoted.length > 3 ? '…' : '')
        const what = t.kind || elementLine(t.element, t.text).split(' ')[0]
        out.push(`${i + 1}. ${where || t.kind || 'Unknown component'}, ${what}${shown ? ` ${shown}` : ''}`)
        const a = t.alike ?? 0
        out.push(`   Scope: ${a && r.ts.length >= a ? `all ${a} alike elements` : a ? `${r.ts.length} of ${a} alike elements` : `${r.ts.length} separate elements`}`)
        out.push(...changeLines(t))
        if (t.path.length > 1) out.push(`   Path: ${t.path.join(' > ')}`)
        return
      }
      if (t.kind) out.push(`${i + 1}. ${t.kind}${t.text ? ` "${t.text}"` : ''}${where ? ` in ${where}` : ''}`)
      else out.push(`${i + 1}. ${where || 'Unknown component'}`)
      if (!t.kind) out.push(`   Element: ${elementLine(t.element, t.text)}`)
      out.push('   Scope: this element only')
      out.push(...changeLines(t))
      for (const c of copiesChanged(t)) out.push(`   Copy: "${c.from}" → "${c.to}"${c.files?.length ? ` (literal in ${c.files.join(', ')})` : ''}`)
      if (t.swap) out.push(`   Replace with frappe-ui ${t.swap} (hand-rolled now)`)
      if (t.path.length > 1) out.push(`   Path: ${t.path.join(' > ')}`)
    })
  }
  return out.join('\n')
}
