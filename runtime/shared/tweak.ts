// Tweak's pure half: the token lists, the class maths, what a tweak changed, the list's rows and the prompt.
// No DOM here. The Viewer shell (runtime/shell/tweaks.ts) builds its rows and its prompt from these, and the frame
// agent (runtime/agent/tweakDom.ts) its class writes, so the two agree on every class. What reads or writes the page
// lives with the page, in runtime/agent/tweakDom.ts.

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
export const GROUPS: Group[] = ['ink', 'style', 'weight', 'bg', 'border', 'radius', 'pad', 'mar', 'gap']

const SPACE = ['0', '0.5', '1', '1.5', '2', '2.5', '3', '3.5', '4', '5', '6', '7', '8', '10', '12', '16']
const NEG = ['-0.5', '-1', '-1.5', '-2', '-2.5', '-3', '-3.5', '-4']

export const CANDIDATES: Tokens = {
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

// Spacing groups keep bare values ('4', '-2'); the others keep whole classes.
export function classOf(group: Group, key: string): string {
  if (group === 'pad') return `p-${key}`
  if (group === 'mar') return key.startsWith('-') ? `-m-${key.slice(1)}` : `m-${key}`
  if (group === 'gap') return `gap-${key}`
  return key
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
export const CATS = Object.keys(CAT) as Cat[]
export const catOf = (c: string): Cat | null => CATS.find((k) => CAT[k].test(c)) ?? null
export const isComposite = (c: string) => /-(?:medium|semibold|bold)$/.test(c)

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

// ---- Component props ------------------------------------------------------------------------
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

// ---- A tweak --------------------------------------------------------------------------------
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
// Every edit of a multi-select is one group.
export type GroupMeta = { id: string; alike: number }

// The server's copy may come from an older build or a hand edit: drop what is unusable instead of breaking the page.
const readRows = <T>(rows: unknown, ok: (x: any) => boolean): T[] => (Array.isArray(rows) ? rows.filter((x) => x && typeof x === 'object' && ok(x)) : [])
// The server's rows, checked and brought up to date: an older session's single `copy` becomes `copies`.
export function restoreTweaks(rows: unknown): Tweak[] {
  return readRows<Tweak>(rows, (t) => Array.isArray(t.classes) && Array.isArray(t.original?.classes) && !!t.props && !!t.original.props).map((t) => {
    if (t.copy && !t.copies) t.copies = [{ i: 0, from: t.copy.from, to: t.copy.to, files: t.copyFiles }]
    delete t.copy
    delete t.copyFiles
    return t
  })
}

// Fields are compared against the original; a tweak whose fields all match is not a tweak.
export const diffOf = (t: Tweak) => ({
  removed: t.original.classes.filter((c) => !t.classes.includes(c)),
  added: t.classes.filter((c) => !t.original.classes.includes(c)),
})
export const propKeys = (t: Tweak) => Object.keys(t.props).filter((k) => t.props[k] !== t.original.props[k])
// What a class list amounts to for one category, so a rewrite that changes nothing
// (px-2.5 py-2.5 to p-2.5, equal sides collapsed) is not a change.
export function effectOf(classes: string[], cat: Cat): string {
  if (cat === 'pad') return JSON.stringify(readSides(classes, 'p'))
  if (cat === 'mar') return JSON.stringify(readSides(classes, 'm'))
  return [...classes].reverse().find((c) => CAT[cat].test(c)) ?? ''
}
export function catsChanged(t: Tweak): Cat[] {
  return CATS.filter((c) => effectOf(t.original.classes, c) !== effectOf(t.classes, c))
}
// Classes outside every category are compared as they are.
// A block container whose children sit one under another, like a Figma auto layout without the
// layout: it can have a gap once it is made a flex column.
export const STACK_CLASSES = ['flex', 'flex-col']
// A stack this tweak turned into a flex column: still a stack after the edit.
export const madeStack = (t: Tweak | undefined) => !!t && STACK_CLASSES.every((c) => t.classes.includes(c) && !t.original.classes.includes(c))

export const copiesChanged = (t: Tweak) => (t.copies ?? []).filter((c) => c.to !== c.from)
export function otherChanged(t: Tweak): boolean {
  const d = diffOf(t)
  // The flex column a stack's gap needs is part of that gap, not a change of its own.
  const gap = catsChanged(t).includes('gap')
  return [...d.removed, ...d.added].some((c) => !catOf(c) && !(gap && STACK_CLASSES.includes(c)))
}
export const isChanged = (t: Tweak) => !!(catsChanged(t).length || otherChanged(t) || propKeys(t).length || t.swap || copiesChanged(t).length)

// ---- Rows: one tweak, or the tweaks of a multi-select edit that read the same ----------------
export type Row = { id: string; ts: Tweak[] }
// Only the grouping key of a multi-select edit: two picks read the same when this does.
function changesOf(t: Tweak): string[] {
  return displayChanges(t).map((c) => `${c.icon ?? ''}|${c.swatch?.cls ?? ''}|${c.text}`)
}
export function rowsOf(list: Tweak[]): Row[] {
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
export function displayChanges(t: Tweak): Change[] {
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

const textsOf = (r: Row) => {
  const ts = r.ts.map((t) => t.text).filter(Boolean)
  return ts.length ? `${ts.slice(0, 3).map((x) => x.slice(0, 20)).join(', ')}${ts.length > 3 ? '…' : ''}` : ''
}
// The list's rows. `stackCount` is how many things a vertical stack holds (counted live where the page is, else as it
// was when the tweak was made); `pageOf` names the route's page.
export function itemsOf(rows: Row[], stackCount: (t: Tweak) => number, pageOf: (route: string) => string): TweakItem[] {
  return rows.map((r) => {
    const t = r.ts[0]
    const many = r.ts.length > 1
    const fallback = t.kind || t.component || roleOf(t)
    const a = t.alike ?? 0
    const n = many ? 0 : stackCount(t)
    return {
      id: r.id,
      route: t.route,
      page: pageOf(t.route),
      title: (many ? textsOf(r) : n ? `List of ${n}` : t.label || t.text.trim()) || fallback,
      badge: many ? (a ? `${r.ts.length} of ${a}` : `${r.ts.length} items`) : '',
      changes: displayChanges(t),
    }
  })
}

// A file is data (not copy) when any folder is data, fixtures or mocks, or its name says so.
// Hard-coded text found only in these files is a value the page shows, not wording to edit.
export function isDataFile(path: string): boolean {
  const parts = path.split('/')
  const base = parts[parts.length - 1]
  return parts.slice(0, -1).some((p) => /^(data|fixtures|mocks)$/i.test(p)) || /^(data|fixtures|mock[^.]*)\./i.test(base)
}

// ---- Prompt ---------------------------------------------------------------------------------
// What a note or tweak calls its element: the tag and its words, else the tag and classes.
export function elementLine(element: string, text: string): string {
  const tag = element.split(/[.\s]/)[0]
  return text ? `${tag} "${text}"` : element
}

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

// The tweak half of the prompt. `subject` is how the prompt names the Prototype ("the CRM prototype").
export function tweakPrompt(all: Row[], subject: string): string {
  const n = all.length
  const out = [
    "These are visual targets from a designer. Match the rendered result; the class edits show one way to get there. If it's cleaner to fix it in the shared component, a token, or the parent layout, do that instead, and say what you did.",
    '',
    `Tweaks on ${subject} (${n} ${n === 1 ? 'tweak' : 'tweaks'})`,
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
