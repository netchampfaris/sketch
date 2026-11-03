// Tweak's DOM half, in the Viewer shell's frame: what an element is and holds (its classes, its frappe-ui props, its
// hard-coded copy, its alike copies), the writes that try a change on or keep it, and the watch that keeps every kept
// tweak on the page while Vue re-renders. The shell holds the tweaks, draws the panel and builds the prompt
// (runtime/shell/tweaks.ts); it sends the tweaks here only so they stay applied (`tweak:reapply`).
//
// Nothing here saves anything, and nothing here reads anyone's notes: the shell's list of tweaks is the person's own
// class, prop and copy edits, which this page shows anyway. The same maths as runtime/annotate/tweak.ts, which the
// in-frame toolbar keeps until the flag goes (plan step 7).
import * as FUI from 'frappe-ui'
import * as FUI_LIST from 'frappe-ui/list'
import { CANDIDATES, CAT, CATS, KNOWN, catOf, classOf, isDataFile, type Cat, type Group, type Tokens } from '../shared/tweak'
import type { PropValue, TweakCopy, TweakFacts, TweakSync } from '../shared/protocol'
import {
	UI_ATTR,
	componentOf,
	fileOfName,
	generatedId,
	isOurs,
	isOursName,
	nameOfType,
	resolve,
	selectorOf,
	sourceFiles,
	summaryOf,
	textOf,
	vnodeOf,
} from './dom'

// ---- Tokens: the candidates this Runtime really styles -----------------------------------------
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

let probed: Promise<Tokens | null> | null = null
// The tokens, once: null when the runtime was too slow to tell (the shell keeps every candidate then).
export function probeTokens(): Promise<Tokens | null> {
	return (probed ??= doProbe().catch(() => null))
}
async function doProbe(): Promise<Tokens | null> {
	// The sentinel rule has the specificity of one class and sits first in <head>, so any real
	// utility (same specificity, later) overrides it, and a class that sets nothing leaves it.
	const sheet = document.createElement('style')
	sheet.setAttribute(UI_ATTR, '')
	sheet.textContent =
		'.tweak-probe{display:flex;padding:7px;margin:7px;gap:7px;border:7px solid rgb(1,2,3);border-radius:7px;background-color:rgb(1,2,3);color:rgb(1,2,3);font-size:7px;font-weight:111;line-height:7px}'
	document.head.insertBefore(sheet, document.head.firstChild)
	const box = document.createElement('div')
	box.setAttribute(UI_ATTR, '')
	box.style.cssText = 'position:fixed;left:-9999px;top:0;visibility:hidden;pointer-events:none'
	document.body.appendChild(box)
	const mk = (cls: string) => {
		const d = document.createElement('div')
		d.className = `tweak-probe ${cls}`
		box.appendChild(d)
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
		if (!keep.pad.includes('4') || !keep.ink.includes('text-ink-gray-7')) return null
		return keep
	} finally {
		box.remove()
		sheet.remove()
	}
}

// ---- Classes ------------------------------------------------------------------------------------
export const baseClasses = (el: Element): string[] => Array.from(el.classList).filter((c) => !c.includes(':'))

// Responsive and state variants are never edited, but the designer should know they exist.
function variantNote(el: Element, cat: Cat): string | null {
	const hits = Array.from(el.classList).filter((c) => c.includes(':') && catOf(c.slice(c.lastIndexOf(':') + 1)) === cat)
	if (!hits.length) return null
	const wide = hits.every((c) => /^(?:sm|md|lg|xl|2xl):/.test(c))
	return `Also ${hits.join(', ')}${wide ? ' on wider screens' : ''}`
}

// ---- Component instances -----------------------------------------------------------------------
export type FrappeInfo = { name: string; inst: any; rootEl: Element | null }
const knownProps = (f: FrappeInfo) => Object.keys(KNOWN[f.name] ?? {}).filter((k) => k in f.inst.props)

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

// Inside a frappe-ui component the designer means the component: select its root instead.
export function retarget(el: Element): Element {
	const f = frappeOf(el)
	return f?.rootEl && f.rootEl !== el && f.rootEl.isConnected ? f.rootEl : el
}
// frappe-ui components edit props, ours edit classes: the two never share one popover.
export const kindOf = (e: Element) => frappeOf(e)?.name ?? ''

// ---- The kept tweaks, as the shell last sent them -----------------------------------------------
let mirror: TweakSync[] = []
// Live elements: the one each tweak was made on, while it lives; else its selector finds it again.
const refs = new Map<string, WeakRef<Element>>()
let currentRoute = ''
export const setRoute = (k: string) => void (currentRoute = k)

export function elOfTweak(t: TweakSync): Element | null {
	const r = refs.get(t.id)?.deref()
	if (r?.isConnected) return r
	if (t.route !== currentRoute) return null
	const el = resolve(t.selector)
	if (el) refs.set(t.id, new WeakRef(el))
	return el
}
export const tweakFor = (el: Element): TweakSync | undefined => mirror.find((t) => t.route === currentRoute && elOfTweak(t) === el)
// The tweaks of a list row, by id, and their elements on the page now.
export const elsOfTweaks = (ids: string[]): Element[] =>
	mirror.filter((t) => ids.includes(t.id)).map(elOfTweak).filter((e): e is Element => !!e)
export const openerOf = (ids: string[]): string | undefined => mirror.find((t) => ids.includes(t.id) && t.opener)?.opener

const diffOf = (t: TweakSync) => ({
	removed: t.original.classes.filter((c) => !t.classes.includes(c)),
	added: t.classes.filter((c) => !t.original.classes.includes(c)),
})
const propKeys = (t: TweakSync) => Object.keys(t.props).filter((k) => t.props[k] !== t.original.props[k])
const copiesChanged = (t: TweakSync) => t.copies.filter((c) => c.to !== c.from)

// The shell's list now. A tweak it no longer keeps (reverted, reset, or matching the page again) is put back as the page
// had it; `bind` ties each new tweak to the element it was made on.
export function setTweaks(list: TweakSync[], bind: Record<string, string>, refOf: (ref: string) => Element | null) {
	const keep = new Set(list.map((t) => t.id))
	for (const t of mirror) if (!keep.has(t.id)) {
		revert(t)
		refs.delete(t.id)
	}
	for (const [id, ref] of Object.entries(bind)) {
		const el = refOf(ref)
		if (el) refs.set(id, new WeakRef(el))
	}
	mirror = list
	syncSoon()
}

// ---- Alike elements -----------------------------------------------------------------------------
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
	for (const t of mirror) {
		const e = t.route === currentRoute ? elOfTweak(t) : null
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

// ---- Hard-coded copy ----------------------------------------------------------------------------
// The page embeds the prototype's files. A text is copy when a file other than the data files and
// our own tooling contains it as a literal; text that appears nowhere is computed or from data.
let sources: { copy: [string, string][]; data: [string, string][] } | null = null
const squash = (s: string) => s.replace(/\s+/g, ' ')
function loadSources() {
	if (sources) return sources
	sources = { copy: [], data: [] }
	try {
		for (const [path, body] of Object.entries(sourceFiles())) {
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
function copySource(text: string, el: Element): { files: string[] } | null {
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
// other element only when it is made of exactly one. A text the person already edited comes as they left it.
const MAX_COPY = 6
function copyInfos(el: Element, kept: TweakSync | undefined): TweakCopy[] {
	const nodes = copyNodes(el)
	const root = frappeOf(el)?.rootEl === el
	if (!root && nodes.length !== 1) return []
	const out: TweakCopy[] = []
	nodes.forEach((n, i) => {
		const k = kept?.copies.find((c) => c.i === i)
		let c: TweakCopy | null = null
		// The shell has the files it was found in.
		if (k) c = { ...k, files: [] }
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
// One text, written in place.
export function writeCopyAt(el: Element, i: number, to: string, stem: boolean) {
	const node = copyNodes(el)[i]
	if (node) writeCopy(node, to, stem)
}

// A hand-made look-alike of a frappe-ui component: the name of the component it should be.
function handRolledOf(el: Element): string | null {
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

// ---- Stacks -------------------------------------------------------------------------------------
// A block container whose children sit one under another, like a Figma auto layout without the
// layout: it can have a gap once it is made a flex column.
const visibleKids = (el: Element) =>
	Array.from(el.children).filter((c) => {
		if (isOurs(c)) return false
		const cs = getComputedStyle(c)
		return cs.display !== 'none' && cs.position !== 'absolute' && cs.position !== 'fixed'
	})
function isVStack(el: Element): boolean {
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
const STACK = ['flex', 'flex-col']
const madeStack = (t: TweakSync | undefined) => !!t && STACK.every((c) => t.classes.includes(c) && !t.original.classes.includes(c))
// How many things each kept stack on this page holds, for the list's "List of n".
export function stackCounts(): Record<string, number> {
	const out: Record<string, number> = {}
	for (const t of mirror) {
		const el = t.route === currentRoute ? elOfTweak(t) : null
		if (el && (isVStack(el) || madeStack(t))) out[t.id] = visibleKids(el).length
	}
	return out
}

// ---- What opened a floating layer ---------------------------------------------------------------
// What last opened something (a popover, a menu): the trigger inside the app with aria-expanded,
// aria-haspopup or aria-controls. A tweak made inside that layer keeps it, to open it again.
let lastOpener: string | null = null
let toolOn = () => false
function recordOpener(e: Event) {
	// While a tool is picking, clicks pick; they open nothing.
	if (toolOn()) return
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
// The first of an element's texts, only when it has several.
function firstOfMany(el: Element): string {
	const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT)
	const texts: string[] = []
	for (let n = w.nextNode(); n; n = w.nextNode()) if (n.nodeValue?.trim()) texts.push(squash(n.nodeValue.trim()))
	return texts.length > 1 ? texts[0].slice(0, 60) : ''
}

// ---- Facts: one element, as the shell's panel reads it --------------------------------------------
const CS_KEYS = ['fontSize', 'fontWeight', 'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft', 'marginTop', 'marginRight', 'marginBottom', 'marginLeft', 'columnGap', 'borderTopLeftRadius', 'display'] as const

export function factsOf(el: Element, ref: string): TweakFacts {
	const t = tweakFor(el)
	const f = frappeOf(el)
	const cs = getComputedStyle(el)
	const csOut: Record<string, string> = {}
	for (const k of CS_KEYS) csOut[k] = cs[k]
	const notes: Record<string, string> = {}
	for (const c of CATS) {
		const n = variantNote(el, c)
		if (n) notes[c] = n
	}
	const known = f ? knownProps(f) : []
	const props: Record<string, PropValue> = {}
	for (const k of known) {
		const v = f!.inst.props[k]
		if (typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean') props[k] = v
	}
	const copies = copyInfos(el, t)
	const info = componentOf(el)
	const own = ownerName(el)
	if (isOursName(own)) Object.assign(info, { component: own, file: fileOfName(own) })
	return {
		ref,
		tweak: t?.id ?? '',
		name: nameOf(el),
		kind: f ? f.name : '',
		classes: baseClasses(el),
		known,
		props,
		cs: csOut,
		notes,
		hasText: Array.from(el.childNodes).some((n) => n.nodeType === 3 && !!n.textContent?.trim()),
		bordered: ['Top', 'Right', 'Bottom', 'Left'].some((s) => parseFloat((cs as any)[`border${s}Width`]) > 0),
		rolled: f ? '' : (handRolledOf(el) ?? ''),
		stack: isVStack(el),
		copies,
		where: {
			selector: selectorOf(el),
			component: info.component,
			file: info.file ?? '',
			path: info.chain,
			element: summaryOf(el),
			text: textOf(el),
			label: firstOfMany(el),
			items: isVStack(el) ? visibleKids(el).length : 0,
			opener: !document.querySelector('#app')?.contains(el) && !isOurs(el) ? (lastOpener ?? '') : '',
			viewport: `${window.innerWidth}×${window.innerHeight}`,
		},
	}
}

// ---- Writing ------------------------------------------------------------------------------------
export function writeDom(el: Element, next: string[]) {
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

// A frappe-ui prop, set on the instance. A null value is no value.
export function writeProp(el: Element, key: string, v: PropValue | null) {
	const f = frappeOf(el)
	if (!f || !(key in f.inst.props)) return
	f.inst.props[key] = v ?? undefined
	f.inst.update()
}

// ---- Keeping tweaks applied ---------------------------------------------------------------------
// Vue rewrites class and props on re-render. Re-apply only the difference from the original,
// so classes Vue changes for its own reasons (an active state) are left alone.
function syncOne(t: TweakSync) {
	const el = elOfTweak(t)
	if (!el) return
	// A re-render resets the text: write it again (only when it differs, so the observer settles).
	for (const c of copiesChanged(t)) writeCopyAt(el, c.i, c.to, c.stem)
	const d = diffOf(t)
	// frappe-ui components take props only: a class change stored against one (an older session) is not applied.
	if (!((d.added.length || d.removed.length) && frappeOf(el))) {
		const cur = baseClasses(el)
		const rm = d.removed.filter((c) => cur.includes(c))
		const add = d.added.filter((c) => !cur.includes(c))
		if (rm.length) el.classList.remove(...rm)
		if (add.length) el.classList.add(...add)
	}
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
let onSynced = () => {}

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
	for (const t of mirror) {
		if (t.route !== currentRoute) continue
		const el = elOfTweak(t)
		if (!el) {
			missing = true
			continue
		}
		if (app && !app.contains(el)) missing = true
		want(el, t.copies.length ? { attributes: true, attributeFilter: ['class'], characterData: true, childList: true, subtree: true } : { attributes: true, attributeFilter: ['class'] })
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
		for (const t of mirror) if (t.route === currentRoute) syncOne(t)
		watchTargets()
	} finally {
		syncing = false
	}
	onSynced()
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

// `tool` says whether a tool is picking (a click then picks and opens nothing); `synced` runs after each pass.
export function startSync(tool: () => boolean, synced: () => void) {
	toolOn = tool
	onSynced = synced
	started = true
	mo = new MutationObserver((rs) => {
		syncSoon()
		// A popover opening adds its layer under <body>; its content may fill in a moment later.
		if (rs.some((r) => r.target === document.body && Array.from(r.addedNodes).some((n) => n instanceof Element && !isOurs(n)))) reapply()
	})
	for (const t of ['pointerdown', 'click']) document.addEventListener(t, recordOpener, true)
	reapply()
}

// Put one element back as the page had it.
function revert(t: TweakSync) {
	const el = elOfTweak(t)
	if (!el) return
	for (const c of t.copies) writeCopyAt(el, c.i, c.from, c.stem)
	const d = diffOf(t)
	if (d.added.length) el.classList.remove(...d.added)
	if (d.removed.length) el.classList.add(...d.removed)
	const f = propKeys(t).length ? frappeOf(el) : null
	if (f) {
		for (const k of propKeys(t)) f.inst.props[k] = t.original.props[k]
		f.inst.update()
	}
}
