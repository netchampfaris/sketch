<script setup lang="ts">
// Tweak mode: pick an element, change its design tokens from a small popover under it. Nothing is
// saved to source; the changes live in the browser and "Copy prompt" (in the toolbar) lists them
// for a coding agent. Mounted once inside <Annotate />. Live only while the toolbar is picking in tweak mode.
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Button, Textarea, TextInput } from 'frappe-ui'
import TokenSelect from './TokenSelect.vue'
import { UI_ATTR, active, childOf, clamp, isOurs, listen, mode, newId, parentOf, resolve, routeKey, targetOf, toolbarOpen, tweakApi, typing } from './annotate'
import {
	CAT,
	KNOWN,
	alikeOf,
	alikeSet,
	baseClasses,
	buildTweakPrompt,
	cancelPreview,
	cancelProps,
	commitClasses,
	copyInfos,
	elsOfRow,
	STACK_CLASSES,
	emitSides,
	frappeOf,
	isVStack,
	madeStack,
	handRolledOf,
	isComposite,
	knownProps,
	nameOf,
	openerOfRow,
	previewClasses,
	probeTokens,
	readSides,
	reapply,
	removeTweak,
	resetAll,
	rev,
	setCopy,
	setProps,
	setRoute,
	startSync,
	stopSync,
	toggleSwap,
	tokens,
	tweakCount,
	tweakFor,
	tweakItems,
	variantNote,
	type Sides,
} from './tweak'

const live = computed(() => active.value && mode.value === 'tweak')

type R = { x: number; y: number; w: number; h: number }
type Swatch = { type: 'ink' | 'bg' | 'border'; cls: string }
type Opt = { value: string | null; label: string; right?: string; swatch?: Swatch }
// What one element says about a field; fuse() joins the fields of every selected element into one.
type Shown = {
	key: string
	label: string
	icon?: string
	value: string | null
	options: Opt[]
	noneRight?: string
	changed: boolean
	mixed?: boolean
	note?: string | null
	emptyAs?: 'space' | 'radius'
}
type IField = Shown & {
	el: Element
	classes: string[] // the committed classes the next/resetTo maths started from
	next?: (v: string | null) => string[]
	resetTo?: () => string[]
	prop?: { name: string; committed: any; original: any }
}
type Field = Shown & {
	preview: (v: string | null) => void
	commit: (v: string | null) => void
	cancel: () => void
	reset: () => void
}

// The selection is ordered; the last pick is the one the popover sits under.
const sels = shallowRef<Element[]>([])
const sel = computed(() => sels.value[sels.value.length - 1] ?? null)
const hover = shallowRef<Element | null>(null)
// The elements whose row is hovered in the toolbar's tweak list.
const hls = shallowRef<Element[]>([])
const selRect = ref<R | null>(null)
const otherRects = ref<R[]>([])
const faintRects = ref<R[]>([])
const hoverRect = ref<R | null>(null)
const hlRects = ref<R[]>([])
const hoverName = ref('')
// Copies of the selection (same maker, tag, mostly the same classes) and of the Shift-hovered element.
const alike = shallowRef<{ copies: Element[]; total: number }>({ copies: [], total: 0 })
const hoverAlike = shallowRef<Element[]>([])
const flash = ref<{ text: string; x: number; y: number } | null>(null)
let flashTimer = 0
const padSides = ref(false)
// Where on the element the click landed, as fractions: a very tall element puts the popover there.
let anchor: { fx: number; fy: number } | null = null
let lastSide: 'below' | 'above' = 'below'

// ---- Selection ------------------------------------------------------------------------
// Inside a frappe-ui component the designer means the component: select its root instead.
function retarget(el: Element): Element {
	const f = frappeOf(el)
	return f?.rootEl && f.rootEl !== el && f.rootEl.isConnected ? f.rootEl : el
}
function setSel(list: Element[], pt?: { x: number; y: number }) {
	sels.value = list
	hover.value = null
	hoverName.value = ''
	hoverAlike.value = []
	lastSide = 'below'
	anchor = null
	const t = list[list.length - 1]
	if (t && pt) {
		const r = t.getBoundingClientRect()
		if (r.width && r.height) anchor = { fx: (pt.x - r.left) / r.width, fy: (pt.y - r.top) / r.height }
	}
	selRect.value = rectOf(t ?? null)
	place()
}
function select(el: Element | null, pt?: { x: number; y: number }) {
	setSel(el ? [retarget(el)] : [], pt)
}
function deselect() {
	setSel([])
}
// frappe-ui components edit props, ours edit classes: the two never share one popover.
const kindOf = (e: Element) => frappeOf(e)?.name ?? ''
function say(text: string, pt?: { x: number; y: number }) {
	flash.value = { text, x: pt?.x ?? 16, y: pt?.y ?? 16 }
	clearTimeout(flashTimer)
	flashTimer = window.setTimeout(() => (flash.value = null), 1200)
}
// Shift+click: add to the selection, or take out of it (the last one stays).
function pick(el: Element, pt: { x: number; y: number }, additive: boolean) {
	const t = retarget(el)
	const cur = sels.value
	if (!additive || !cur.length) return setSel([t], pt)
	if (cur.includes(t)) return cur.length > 1 ? setSel(cur.filter((x) => x !== t)) : undefined
	if (kindOf(t) !== kindOf(cur[0])) return say(`Can't mix ${nameOf(t)} with ${nameOf(cur[0])}`, pt)
	setSel([...cur, t], pt)
}
// Copies that can join the selection: the same kind, and the component itself, not a part of it.
// Cached per selection; each copy is looked up once (the vnode walk is not free, up to 300 of them).
const joinable = computed(() => {
	const first = sels.value[0]
	if (!first) return []
	const kind = kindOf(first)
	return alike.value.copies.filter((c) => {
		if (!c.isConnected) return false
		const f = frappeOf(c)
		const root = f?.rootEl && f.rootEl !== c && f.rootEl.isConnected ? f.rootEl : c
		return root === c && (f?.name ?? '') === kind
	})
})
function selectAll() {
	// The current pick stays last, so the popover stays where it is.
	setSel([...joinable.value, ...sels.value])
}
function goParent() {
	if (sels.value.length !== 1) return
	let p = sel.value ? parentOf(sel.value) : null
	// A parent inside the same frappe-ui component retargets to where we are: keep climbing.
	for (let i = 0; p && !isOurs(p) && i < 8; i++, p = parentOf(p)) {
		const t = retarget(p)
		if (t !== sel.value) return select(t)
	}
}
function goChild() {
	if (sels.value.length !== 1) return
	const c = sel.value ? childOf(sel.value) : null
	if (c && retarget(c) !== sel.value) select(c)
}

// The copies are looked up when the selection changes, not every frame.
watch(sels, (l) => ((peek.value = false), (alike.value = l.length ? alikeSet(l) : { copies: [], total: 0 })))

// Spacing opens per side when the sides already differ.
watch(sel, (el) => {
	if (!el) return
	probeTokens()
	const t = tweakFor(el)
	const c = t ? t.classes : baseClasses(el)
	const s = readSides(c, 'p')
	padSides.value = s.l !== s.r || s.t !== s.b
})

// ---- Outlines and the popover's place -------------------------------------------------
const rectOf = (el: Element | null): R | null => {
	if (!el) return null
	const r = el.getBoundingClientRect()
	return { x: r.left, y: r.top, w: r.width, h: r.height }
}
const sameR = (a: R | null, b: R | null) => (!a && !b) || (!!a && !!b && a.x === b.x && a.y === b.y && a.w === b.w && a.h === b.h)

const W = 304
const M = 8
const panel = ref<HTMLElement | null>(null)
const pos = ref({ left: 0, top: 0, maxH: 400, up: false })

// 8px under the element, left edges aligned; above when there is no room below; at the click
// when the element is taller than 60% of the viewport. The side it is on only changes when it stops fitting.
function place() {
	const r = selRect.value
	if (!r) return
	const vw = window.innerWidth
	const vh = window.innerHeight
	const h = (panel.value?.scrollHeight ?? 280) + 2
	let x = r.x
	let top = r.y
	let bottom = r.y + r.h
	let gapBelow = r.y < 28 ? 32 : 8 // the name tag sits under the element when it has no room above
	let gapAbove = 30 // and over it otherwise
	if (r.h > vh * 0.6) {
		const pt = anchor ? { x: r.x + anchor.fx * r.w, y: r.y + anchor.fy * r.h } : { x: r.x + r.w / 2, y: (Math.max(r.y, 0) + Math.min(r.y + r.h, vh)) / 2 }
		x = pt.x
		top = bottom = pt.y
		gapBelow = gapAbove = 12
	}
	const below = vh - M - (bottom + gapBelow)
	const above = top - gapAbove - M
	const order: ('below' | 'above')[] = lastSide === 'below' ? ['below', 'above'] : ['above', 'below']
	let side = order.find((s) => h <= (s === 'below' ? below : above))
	if (!side) side = below >= above ? 'below' : 'above'
	lastSide = side
	const space = Math.max(120, side === 'below' ? below : above)
	const used = Math.min(h, space)
	const next = {
		left: Math.round(clamp(x, M, vw - W - M)),
		top: Math.round(side === 'below' ? bottom + gapBelow : Math.max(M, top - gapAbove - used)),
		maxH: Math.round(space),
		up: side === 'above',
	}
	const p = pos.value
	if (p.left !== next.left || p.top !== next.top || p.maxH !== next.maxH || p.up !== next.up) pos.value = next
}
const panelStyle = computed(() => ({
	left: `${pos.value.left}px`,
	top: `${pos.value.top}px`,
	maxHeight: `${pos.value.maxH}px`,
	transformOrigin: pos.value.up ? 'bottom left' : 'top left',
}))

let raf = 0
// Frames run while something may have moved: a change of selection or hover, a scroll, a resize,
// a DOM change, a transition. Each of those keeps them going for a moment (a CSS transition moves
// things without any event), then the loop rests instead of reading rects every frame.
let until = 0
function poke(ms = 600) {
	until = Math.max(until, performance.now() + ms)
	if (!raf && (live.value || hls.value.length > 0)) raf = requestAnimationFrame(frame)
}
function frame() {
	raf = 0
	// A removed element: drop it from the selection quietly, the tweak stays.
	if (sels.value.some((e) => !e.isConnected)) setSel(sels.value.filter((e) => e.isConnected))
	if (hover.value && !hover.value.isConnected) hover.value = null
	if (hls.value.some((e) => !e.isConnected)) hls.value = hls.value.filter((e) => e.isConnected)
	const s = rectOf(sel.value)
	if (!sameR(s, selRect.value)) selRect.value = s
	setRects(otherRects, sels.value.slice(0, -1))
	// With a selection, only Shift (add or remove) brings the hover outline back, as in comment mode.
	const h = hover.value && !sels.value.includes(hover.value) && (!sels.value.length || shift) ? rectOf(hover.value) : null
	if (!sameR(h, hoverRect.value)) hoverRect.value = h
	setRects(hlRects, hls.value.filter((e) => !sels.value.includes(e)))
	// Copies of the selection (and of the Shift-hovered element) that are not picked, and on screen.
	const picked = new Set(sels.value)
	const vh = window.innerHeight
	const vw = window.innerWidth
	const faint = new Set([...alike.value.copies, ...hoverAlike.value])
	setRects(
		faintRects,
		[...faint].filter((e) => !picked.has(e) && e.isConnected),
		(r) => r.w > 0 && r.h > 0 && r.y < vh && r.y + r.h > 0 && r.x < vw && r.x + r.w > 0,
	)
	place()
	if (performance.now() < until) raf = requestAnimationFrame(frame)
}
function setRects(target: { value: R[] }, els: Element[], keep: (r: R) => boolean = () => true) {
	const next = els.map((e) => rectOf(e)!).filter((r) => r && keep(r))
	if (next.length !== target.value.length || next.some((r, i) => !sameR(r, target.value[i]))) target.value = next
}
// What can move things on screen, other than our own overlays restyling themselves.
let mut: MutationObserver | null = null
const WIN_EVENTS = ['scroll', 'resize', 'transitionrun', 'transitionend', 'animationstart', 'animationend']
function onWin(e: Event) {
	if (e.target instanceof Node && isOurs(e.target)) return
	poke()
}
function watchLayout(on: boolean) {
	mut?.disconnect()
	mut = null
	for (const t of WIN_EVENTS) window.removeEventListener(t, onWin, true)
	if (!on) return
	for (const t of WIN_EVENTS) window.addEventListener(t, onWin, { capture: true, passive: true })
	mut = new MutationObserver((rs) => {
		if (rs.some((r) => !(r.type === 'attributes' && isOurs(r.target)))) poke()
	})
	mut.observe(document.body, { childList: true, subtree: true, attributes: true, characterData: true })
}
watch(
	() => live.value || hls.value.length > 0,
	(on) => {
		cancelAnimationFrame(raf)
		raf = 0
		watchLayout(on)
		if (on) poke()
	},
	{ immediate: true },
)
watch([sels, hover, hls, alike, hoverAlike, rev, padSides], () => poke(), { flush: 'post' })

const boxStyle = (r: R) => ({ width: `${r.w}px`, height: `${r.h}px`, transform: `translate(${r.x}px, ${r.y}px)` })
const tagStyle = (r: R) => ({ left: `${Math.max(4, r.x)}px`, top: r.y < 28 ? `${r.y + r.h + 4}px` : `${r.y - 24}px` })

// ---- Fields ---------------------------------------------------------------------------
const px = (v: string) => (/^-?[\d.]+$/.test(v) ? `${parseFloat(v) * 4}px` : '')
const STRIP: Record<string, (c: string) => string> = {
	ink: (c) => c.replace('text-ink-', ''),
	style: (c) => c.replace(/^text-/, ''),
	weight: (c) => c.replace('font-', ''),
	bg: (c) => c.replace('bg-surface-', ''),
	border: (c) => c.replace('border-outline-', ''),
	radius: (c) => c.replace(/^rounded-?/, '') || 'default',
}
const SWATCH: Record<string, Swatch['type']> = { ink: 'ink', bg: 'bg', border: 'border' }
const NONE: Opt = { value: null, label: 'None' }
const MIXED = '\u0000mixed'

const hasText = (el: Element) => Array.from(el.childNodes).some((n) => n.nodeType === 3 && !!n.textContent?.trim())
const ICONS: Record<string, string> = {
	Horizontal: 'lucide-move-horizontal',
	Vertical: 'lucide-move-vertical',
	Top: 'lucide-panel-top',
	Right: 'lucide-panel-right',
	Bottom: 'lucide-panel-bottom',
	Left: 'lucide-panel-left',
}

// One element's fields. Each knows its own element and classes, so a field of many can write each
// element from its own start.
function single(el: Element) {
	const t = tweakFor(el)
	const classes = t ? [...t.classes] : baseClasses(el)
	const orig = t ? t.original.classes : classes
	const f = frappeOf(el)
	const name = nameOf(el)

	// frappe-ui components: their own props, nothing else.
	if (f) {
		const inst = f.inst
		const fields: IField[] = knownProps(f).map((prop) => {
			const committed = t && prop in t.props ? t.props[prop] : inst.props[prop]
			const original = t && prop in t.original.props ? t.original.props[prop] : inst.props[prop]
			return {
				key: prop,
				label: prop[0].toUpperCase() + prop.slice(1),
				value: inst.props[prop] ?? null,
				options: KNOWN[f.name][prop].map((x) => ({ value: x, label: x })),
				changed: committed !== original,
				el,
				classes,
				prop: { name: prop, committed, original },
			}
		})
		return { name, frappe: true as const, comp: fields }
	}

	const cs = getComputedStyle(el)

	// One category, one dropdown. Choosing a composite text style drops the weight class it replaces.
	function classField(label: string, cat: 'ink' | 'style' | 'weight' | 'bg' | 'border' | 'radius', noneRight = '', icon?: string): IField {
		const re = CAT[cat]
		const last = (l: string[]) => [...l].reverse().find((c) => re.test(c)) ?? null
		const cur = last(classes)
		const sw = SWATCH[cat]
		const next = (v: string | null) => {
			let n = classes.filter((c) => !re.test(c))
			if (v) n.push(v)
			if (cat === 'style' && v && isComposite(v)) n = n.filter((c) => !CAT.weight.test(c))
			return n
		}
		const alsoWeight = (c: string) => cat === 'style' && CAT.weight.test(c)
		return {
			key: cat,
			label,
			icon,
			value: cur,
			options: [NONE, ...tokens.value[cat].map((c) => ({ value: c, label: STRIP[cat](c), swatch: sw ? { type: sw, cls: c } : undefined }))],
			noneRight,
			changed: cur !== last(orig),
			note: variantNote(el, cat),
			el,
			classes,
			next,
			resetTo: () => [...classes.filter((c) => !re.test(c) && !alsoWeight(c)), ...orig.filter((c) => re.test(c) || alsoWeight(c))],
		}
	}

	// Padding and margin: read four sides with CSS precedence, write the smallest class set.
	function spaceField(label: string, pre: 'p' | 'm', keys: (keyof Sides)[], computedVal: string): IField {
		const cat = pre === 'p' ? 'pad' : 'mar'
		const sides = readSides(classes, pre)
		const osides = readSides(orig, pre)
		const vals = keys.map((k) => sides[k])
		const v = vals.every((x) => x === vals[0]) ? vals[0] : MIXED
		const rebuild = (s: Sides) => [...classes.filter((c) => !CAT[cat].test(c)), ...emitSides(pre, s)]
		const setTo = (nv: string | null) => {
			const s = { ...sides }
			keys.forEach((k) => (s[k] = nv))
			return rebuild(s)
		}
		return {
			key: keys.join(''),
			label,
			icon: ICONS[label],
			value: v === MIXED ? null : v,
			mixed: v === MIXED,
			emptyAs: 'space',
			options: [NONE, ...tokens.value[cat].map((x) => ({ value: x, label: x, right: px(x) }))],
			noneRight: computedVal,
			changed: keys.some((k) => sides[k] !== osides[k]),
			note: null,
			el,
			classes,
			next: setTo,
			resetTo: () => {
				const s = { ...sides }
				keys.forEach((k) => (s[k] = osides[k]))
				return rebuild(s)
			},
		}
	}

	// A block stack has no gap of its own: a gap makes it a flex column, and no gap puts it back.
	function gapField(stack: boolean): IField {
		const re = /^gap-(?!x-|y-)(.+)$/
		const val = (l: string[]) => [...l].reverse().map((c) => c.match(re)?.[1]).find(Boolean) ?? null
		const cur = val(classes)
		const base = () => classes.filter((c) => !CAT.gap.test(c))
		const ownStack = (c: string) => STACK_CLASSES.includes(c) && !orig.includes(c)
		const next = (v: string | null) => {
			if (!stack) return [...base(), ...(v ? [`gap-${v}`] : [])]
			if (!v || v === '0') return base().filter((c) => !ownStack(c))
			const b = base()
			return [...b, ...STACK_CLASSES.filter((c) => !b.includes(c)), `gap-${v}`]
		}
		return {
			key: 'gap',
			label: 'Gap',
			icon: 'lucide-between-horizontal-start',
			value: cur,
			options: [NONE, ...tokens.value.gap.map((x) => ({ value: x, label: x, right: px(x) }))],
			noneRight: cs.columnGap === 'normal' ? '0px' : cs.columnGap,
			emptyAs: 'space',
			changed: cur !== val(orig),
			note: variantNote(el, 'gap'),
			el,
			classes,
			next,
			resetTo: () => [...base().filter((c) => !ownStack(c)), ...orig.filter((c) => CAT.gap.test(c))],
		}
	}

	const styleField = classField('Style', 'style', cs.fontSize)
	const composite = !!styleField.value && isComposite(styleField.value)
	const bordered = ['Top', 'Right', 'Bottom', 'Left'].some((s) => parseFloat((cs as any)[`border${s}Width`]) > 0)
	const rolled = handRolledOf(el)
	const stack = madeStack(t) || isVStack(el)

	return {
		name,
		frappe: false as const,
		text: hasText(el) ? [classField('Colour', 'ink'), styleField, ...(composite ? [] : [classField('Weight', 'weight', cs.fontWeight)])] : [],
		pad: {
			axes: [spaceField('Horizontal', 'p', ['l', 'r'], cs.paddingLeft), spaceField('Vertical', 'p', ['t', 'b'], cs.paddingTop)],
			sides: [
				spaceField('Top', 'p', ['t'], cs.paddingTop),
				spaceField('Right', 'p', ['r'], cs.paddingRight),
				spaceField('Bottom', 'p', ['b'], cs.paddingBottom),
				spaceField('Left', 'p', ['l'], cs.paddingLeft),
			],
		},
		// Margin is usually one side, so it is always the four sides.
		mar: {
			sides: [
				spaceField('Top', 'm', ['t'], cs.marginTop),
				spaceField('Right', 'm', ['r'], cs.marginRight),
				spaceField('Bottom', 'm', ['b'], cs.marginBottom),
				spaceField('Left', 'm', ['l'], cs.marginLeft),
			],
		},
		padNote: variantNote(el, 'pad'),
		marNote: variantNote(el, 'mar'),
		gap: /flex|grid/.test(cs.display) || stack ? gapField(stack) : null,
		fill: [classField('Background', 'bg', '', 'lucide-paint-bucket'), ...(bordered ? [classField('Border colour', 'border')] : []), { ...classField('Radius', 'radius', cs.borderTopLeftRadius), icon: 'lucide-square-round-corner', emptyAs: 'radius' as const }],
		rolled: rolled ? { name: rolled, lower: rolled.replace(/([a-z])([A-Z])/g, '$1 $2').toLowerCase(), added: !!t?.swap } : null,
	}
}

// One field over every selected element: equal values show, different ones read "mixed"; an edit
// writes each element from its own classes.
const gid = () => `g${newId()}`
function fuse(fs: IField[]): Field {
	const f0 = fs[0]
	const same = !f0.mixed && fs.every((f) => !f.mixed && f.value === f0.value)
	const meta = () => ({ id: gid(), alike: alike.value.total })
	const prop = f0.prop
	const edits = (v: string | null): [Element, string[]][] => fs.map((f) => [f.el, f.next!(v)])
	return {
		key: f0.key,
		label: f0.label,
		icon: f0.icon,
		options: f0.options,
		noneRight: f0.noneRight,
		emptyAs: f0.emptyAs,
		note: f0.note,
		value: same ? f0.value : null,
		mixed: !same,
		changed: fs.some((f) => f.changed),
		preview: (v) => (prop ? setProps(fs.map((f) => [f.el, v]), prop.name, false) : previewClasses(edits(v))),
		commit: (v) => (prop ? setProps(fs.map((f) => [f.el, v]), prop.name, true, meta()) : commitClasses(edits(v), meta())),
		cancel: () => (prop ? cancelProps(fs.map((f) => [f.el, f.prop!.committed]), prop.name) : cancelPreview(fs.map((f) => [f.el, f.classes]))),
		reset: () => (prop ? setProps(fs.map((f) => [f.el, f.prop!.original]), prop.name, true, meta()) : commitClasses(fs.map((f) => [f.el, f.resetTo!()]), meta())),
	}
}
// Rows present for every element, matched by key.
const fuseAll = (lists: IField[][]): Field[] => lists[0].filter((f) => lists.every((l) => l.some((x) => x.key === f.key))).map((f) => fuse(lists.map((l) => l.find((x) => x.key === f.key)!)))

const model = computed(() => {
	rev.value
	const ms = sels.value.map(single)
	if (!ms.length) return null
	const m0: any = ms[ms.length - 1]
	const one = ms.length === 1
	if (m0.frappe) return { name: m0.name as string, frappe: true as const, comp: fuseAll(ms.map((m: any) => m.comp)) }
	const all = ms as any[]
	return {
		name: m0.name as string,
		frappe: false as const,
		text: all.every((m) => m.text.length) ? fuseAll(all.map((m) => m.text)) : [],
		pad: { axes: fuseAll(all.map((m) => m.pad.axes)), sides: fuseAll(all.map((m) => m.pad.sides)) },
		mar: { sides: fuseAll(all.map((m) => m.mar.sides)) },
		padNote: one ? (m0.padNote as string | null) : null,
		marNote: one ? (m0.marNote as string | null) : null,
		gap: all.every((m) => m.gap) ? fuse(all.map((m) => m.gap)) : null,
		fill: fuseAll(all.map((m) => m.fill)),
		rolled: one ? (m0.rolled as { name: string; lower: string; added: boolean } | null) : null,
	}
})

// The Copy fields: an element made of one hard-coded text, or a frappe-ui component with several.
// Text from data (a name, "12 days") has none.
const copyFields = computed(() => {
	rev.value
	const el = sels.value.length === 1 ? sel.value : null
	return el ? copyInfos(el) : []
})
const onCopy = (i: number, v: string) => sel.value && setCopy(sel.value, i, v)

const b = (f: Field) => ({
	modelValue: f.value,
	options: f.options,
	label: f.label,
	icon: f.icon,
	noneRight: f.noneRight,
	emptyAs: f.emptyAs,
	changed: f.changed,
	mixed: f.mixed,
	onPreview: f.preview,
	onCommit: f.commit,
	onCancel: f.cancel,
	onReset: f.reset,
})

// ---- Picking --------------------------------------------------------------------------
const pickable = (t: Element | null) => (t && t !== document.body && t !== document.documentElement ? t : null)
const stop = (e: Event) => {
	e.preventDefault()
	e.stopPropagation()
	e.stopImmediatePropagation()
}

// ---- Floating layers ------------------------------------------------------------------
// A HoverCard, Popover or menu is teleported out of #app and closes when the pointer leaves it,
// which is exactly what travelling to our popover does. While something inside one is selected,
// the events that would close it are swallowed.
function layerOf(el: Element | null): Element | null {
	if (!el || isOurs(el)) return null
	const app = document.querySelector('#app')
	if (!app || app.contains(el)) return null
	let n: Element = el
	while (n.parentElement && n.parentElement !== document.body) n = n.parentElement
	return n.parentElement === document.body && !isOurs(n) ? n : null
}
const lockedLayer = computed(() => layerOf(sel.value) ?? layerOf(hover.value))
const LEAVE = ['pointerleave', 'pointerout', 'mouseleave', 'mouseout', 'focusout', 'blur']
function keepOpen(e: Event) {
	const l = lockedLayer.value
	if (l && e.target instanceof Node && l.contains(e.target)) e.stopImmediatePropagation()
}
// Once the lock lets go the layer closes on the pointer's next move, as it would on the page.

// Hold Space: every overlay of ours turns invisible (not removed, so the popover keeps its state).
const peek = ref(false)

// While Shift is held, the hovered element shows its copies: what a Shift+click would offer.
let shift = false
function setShift(v: boolean) {
	if (v === shift) return
	shift = v
	poke()
	hoverAlike.value = shift && hover.value ? alikeOf(hover.value) : []
}

let lastTarget: Element | null = null
function onMove(e: PointerEvent) {
	shift = e.shiftKey
	const t = targetOf(e)
	// The vnode walk behind the name is not free: only when the pointer enters another element.
	if (t === lastTarget) return
	lastTarget = t
	const p = pickable(t)
	const el = p ? retarget(p) : null
	hover.value = el
	hoverName.value = el ? nameOf(el) : ''
	hoverAlike.value = shift && el ? alikeOf(el) : []
}
// Set while we click a trigger ourselves (the list reopening a popover): the page must get that click.
let passthrough = false
function swallow(e: Event) {
	if (!passthrough && targetOf(e)) stop(e)
}
function onClick(e: MouseEvent) {
	if (passthrough) return
	const t = targetOf(e)
	if (!t) return
	stop(e)
	const el = pickable(t)
	if (el) pick(el, { x: e.clientX, y: e.clientY }, e.shiftKey)
}

function onKey(e: KeyboardEvent) {
	if (e.key === 'Shift') return setShift(e.type === 'keydown')
	if (e.key === ' ' && e.type === 'keyup') {
		// The release must not click a focused button either.
		if (!peek.value) return
		peek.value = false
		e.preventDefault()
		return e.stopImmediatePropagation()
	}
	if (e.type === 'keyup') return
	if (e.metaKey || e.ctrlKey || e.altKey || e.isComposing || !sel.value) return
	const t = e.target as HTMLElement | null
	// Escape leaves the Copy field first; the next one deselects as usual.
	if (e.key === 'Escape' && typing(t) && t?.closest?.('[data-tweak-copy]')) {
		t.blur()
		e.preventDefault()
		return e.stopImmediatePropagation()
	}
	const inSelect = !!t?.closest?.('[data-tweak-select]')
	// A text field owns its keys; a dropdown owns all but \, so parent still works right after a tweak.
	if (typing(t) && !(e.key === 'Escape' && !inSelect)) return
	if (e.key === 'Escape') {
		// An open token list closes on its own Escape first; after that Escape clears the selection,
		// even over a page popover (it would otherwise close that too).
		if (e.defaultPrevented || document.querySelector('[data-tweak-select] [role="listbox"]')) return
		deselect()
	} else if (e.key === ' ') {
		if (inSelect) return
		// Hold to see the page without our outlines; repeats still must not scroll it.
		if (!e.repeat) peek.value = true
	} else if (e.key !== '\\' && inSelect) return
	else if (e.key === '\\') goParent()
	else if (e.key === 'Enter' && !t?.closest?.('button,a')) goChild()
	else return
	e.preventDefault()
	e.stopImmediatePropagation()
}

let off: (() => void) | null = null
function attach() {
	off = listen([
		['pointermove', onMove],
		['pointerdown', swallow],
		['mousedown', swallow],
		['mouseup', swallow],
		['click', onClick],
		['dblclick', swallow],
		['keydown', onKey],
		['keyup', onKey],
		['blur', () => (setShift(false), (peek.value = false))],
		...LEAVE.map((t) => [t, keepOpen] as [string, (e: any) => void]),
	])
}
function detach() {
	off?.()
	off = null
	lastTarget = null
	shift = false
	peek.value = false
	sels.value = []
	hover.value = null
	hoverName.value = ''
	hoverAlike.value = []
	selRect.value = null
	otherRects.value = []
	faintRects.value = []
	hoverRect.value = null
}

// Applied tweaks stay when the mode goes off; only the picker and the popover go.
watch(
	live,
	(on) => {
		detach()
		if (on) attach()
	},
	{ immediate: true },
)

// ---- The toolbar's list ---------------------------------------------------------------
const route = useRoute()
const router = useRouter()

// A list row is one tweak or a whole multi-select edit.
function highlight(id: string | null) {
	hls.value = id ? elsOfRow(id) : []
	if (!hls.value.length) hlRects.value = []
}

async function reveal(id: string) {
	const item = tweakItems.value.find((x) => x.id === id)
	if (!item) return
	if (item.route !== routeKey(route)) await router.push(item.route).catch(() => {})
	// The page may still be mounting after the route change. An element inside a popover is not
	// there until its trigger has been clicked: do that once, then give the layer 1.5s to appear.
	let els: Element[] = []
	let deadline = Date.now() + 2500
	let opened = false
	while (!els.length && Date.now() < deadline) {
		els = elsOfRow(id)
		if (els.length) break
		const sel = opened ? null : openerOfRow(id)
		const trigger = sel ? resolve(sel) : null
		if (trigger) {
			opened = true
			deadline = Math.max(deadline, Date.now() + 1500)
			// Already open and still empty: it is only filling in.
			if (trigger.getAttribute('aria-expanded') !== 'true') {
				passthrough = true
				try {
					;(trigger as HTMLElement).click()
				} finally {
					passthrough = false
				}
			}
		}
		await new Promise((r) => setTimeout(r, 100))
	}
	if (!els.length) return
	toolbarOpen.value = true
	active.value = true
	mode.value = 'tweak'
	els[0].scrollIntoView({ block: 'center' })
	// The mode watcher clears the selection when it switches on: select after it has run.
	await nextTick()
	setSel(els)
}

watch(
	() => routeKey(route),
	(k) => {
		setRoute(k)
		deselect()
		hls.value = []
		hlRects.value = []
		reapply()
	},
	{ immediate: true },
)

onMounted(() => {
	startSync()
	tweakApi.value = { count: tweakCount, items: tweakItems, copy: buildTweakPrompt, reset: resetAll, remove: removeTweak, reveal, highlight }
})
onBeforeUnmount(() => {
	detach()
	watchLayout(false)
	cancelAnimationFrame(raf)
	stopSync()
	tweakApi.value = null
})
</script>

<template>
	<!-- A hovered row of the toolbar's list: the element, outlined. Works with the picker off. -->
	<div
		v-for="(r, i) in hlRects"
		:key="'h' + i"
		:[UI_ATTR]="''"
		class="pointer-events-none fixed left-0 top-0 z-[2147483000] rounded-[4px] border-[1.5px] border-solid border-outline-violet-6"
		:style="boxStyle(r)"
	>
		<span class="absolute inset-0 rounded-[3px] bg-surface-violet-7 opacity-[0.06]" />
	</div>

	<div v-if="live" :[UI_ATTR]="''" class="contents" :class="peek && 'invisible'">
		<!-- Hover outline: the same style as the selection at 60%, gliding between elements. -->
		<template v-if="hoverRect">
			<div
				:[UI_ATTR]="''"
				class="pointer-events-none fixed left-0 top-0 z-[2147483000] rounded-[4px] border-[1.5px] border-solid border-outline-violet-6 opacity-60 transition-[transform,width,height] duration-[90ms] ease-out motion-reduce:transition-none"
				:style="boxStyle(hoverRect)"
			>
				<span class="absolute inset-0 rounded-[3px] bg-surface-violet-7 opacity-[0.06]" />
			</div>
			<div
				v-if="hoverName"
				:[UI_ATTR]="''"
				class="pointer-events-none fixed z-[2147483000] whitespace-nowrap rounded-[4px] bg-surface-violet-7 px-1.5 py-0.5 text-xs font-medium text-white opacity-80"
				:style="tagStyle(hoverRect)"
			>
				{{ hoverName }}
			</div>
		</template>

		<!-- Copies of what is picked: dashed and faint, so the pick stays the loudest thing. -->
		<div
			v-for="(r, i) in faintRects"
			:key="'f' + i"
			:[UI_ATTR]="''"
			class="pointer-events-none fixed left-0 top-0 z-[2147483000] rounded-[4px] border border-dashed border-outline-violet-6 opacity-40"
			:style="boxStyle(r)"
		/>
		<div
			v-for="(r, i) in otherRects"
			:key="'o' + i"
			:[UI_ATTR]="''"
			class="pointer-events-none fixed left-0 top-0 z-[2147483000] rounded-[4px] border-[1.5px] border-solid border-outline-violet-6"
			:style="boxStyle(r)"
		>
			<span class="absolute inset-0 rounded-[3px] bg-surface-violet-7 opacity-[0.06]" />
		</div>
		<div
			v-if="flash"
			:[UI_ATTR]="''"
			class="pointer-events-none fixed z-[2147483000] whitespace-nowrap rounded-[4px] bg-surface-violet-7 px-1.5 py-0.5 text-xs font-medium text-white"
			:style="{ left: `${flash.x + 12}px`, top: `${flash.y + 12}px` }"
		>
			{{ flash.text }}
		</div>

		<template v-if="selRect">
			<div
				:[UI_ATTR]="''"
				class="pointer-events-none fixed left-0 top-0 z-[2147483000] rounded-[4px] border-[1.5px] border-solid border-outline-violet-6"
				:style="boxStyle(selRect)"
			>
				<span class="absolute inset-0 rounded-[3px] bg-surface-violet-7 opacity-[0.06]" />
			</div>
			<div
				:[UI_ATTR]="''"
				class="pointer-events-none fixed z-[2147483000] whitespace-nowrap rounded-[4px] bg-surface-violet-7 px-1.5 py-0.5 text-xs font-medium text-white"
				:style="tagStyle(selRect)"
			>
				{{ model?.name }}
			</div>
		</template>

		<Transition
			enter-from-class="opacity-0"
			enter-active-class="transition-opacity duration-150"
			leave-active-class="transition-opacity duration-150"
			leave-to-class="opacity-0"
		>
			<div
				v-if="!sel"
				:[UI_ATTR]="''"
				class="pointer-events-none fixed right-4 top-4 z-[2147483000] rounded-5 border border-outline-gray-2 bg-surface-elevation-2 px-2.5 py-1.5 text-sm text-ink-gray-6 shadow-sm"
			>
				Click an element to tweak it. Shift-click adds more. Hold Space to peek.
			</div>
		</Transition>

		<Transition
			enter-from-class="opacity-0 scale-[0.97] motion-reduce:scale-100"
			enter-active-class="transition duration-[140ms] ease-out motion-reduce:transition-opacity"
			leave-active-class="transition-opacity duration-100"
			leave-to-class="opacity-0"
		>
			<div
				v-if="sel && model"
				ref="panel"
				:[UI_ATTR]="''"
				role="region"
				aria-label="Tweak"
				class="fixed z-[2147483000] w-[304px] overflow-y-auto rounded-5 border border-outline-gray-2 bg-surface-elevation-2 p-2 shadow-xl"
				:style="panelStyle"
				@pointerdown.stop
				@focusin.stop
			>
				<div class="flex items-center gap-2 px-1 pb-2">
					<p class="min-w-0 truncate text-base font-medium text-ink-gray-9">{{ model.name }}</p>
					<span v-if="alike.total > 1" class="shrink-0 text-sm text-ink-gray-5">{{ sels.length }} of {{ alike.total }}</span>
					<Button v-if="joinable.length" class="ml-auto shrink-0" size="sm" variant="ghost" label="Select all" @click="selectAll" />
				</div>

				<div v-if="copyFields.length" data-tweak-copy class="mb-2 border-t border-outline-gray-1 pt-2">
					<p class="mb-1.5 text-sm text-ink-gray-5">Copy<span v-if="copyFields.length > 1" class="ml-1.5 text-ink-gray-4">{{ copyFields.length }}</span></p>
					<div class="space-y-1.5">
						<div v-for="c in copyFields" :key="c.i" class="flex items-start gap-1.5">
							<div class="min-w-0 flex-1">
								<Textarea v-if="c.from.length > 60" size="sm" :rows="2" :model-value="c.to" @update:model-value="(v: string) => onCopy(c.i, v)" />
								<TextInput v-else size="sm" :model-value="c.to" @update:model-value="(v: string) => onCopy(c.i, v)" />
							</div>
							<Button v-if="c.to !== c.from" size="sm" variant="ghost" icon="lucide-rotate-ccw" aria-label="Reset copy" title="Reset copy" @click="onCopy(c.i, c.from)" />
						</div>
					</div>
				</div>

				<!-- frappe-ui component: its props, nothing else. -->
				<template v-if="model.frappe">
					<!-- Labels on top, two columns at most; one prop takes the whole width. -->
					<div v-if="model.comp.length" class="grid gap-x-3 gap-y-3 border-t border-outline-gray-1 pt-2" :class="model.comp.length === 1 ? 'grid-cols-1' : 'grid-cols-2'">
						<div v-for="f in model.comp" :key="f.key" class="min-w-0">
							<p class="mb-1 text-sm text-ink-gray-5">{{ f.label }}</p>
							<TokenSelect v-bind="b(f)" />
						</div>
					</div>
					<p v-else-if="!copyFields.length" class="border-t border-outline-gray-1 px-1 pt-2 text-sm text-ink-gray-5">frappe-ui {{ model.name }}: no props to tweak</p>
				</template>

				<template v-else>
					<div v-if="model.text.length" class="mb-2 border-t border-outline-gray-1 pt-2">
						<p class="mb-1.5 text-sm text-ink-gray-5">Text</p>
						<div class="grid gap-1" :class="model.text.length === 3 ? 'grid-cols-[1.4fr_1fr_1fr]' : 'grid-cols-2'">
							<TokenSelect v-for="f in model.text" :key="f.key" v-bind="b(f)" />
						</div>
						<template v-for="f in model.text" :key="f.key + 'n'">
							<p v-if="f.note" class="mt-1 text-xs text-ink-gray-5">{{ f.note }}</p>
						</template>
					</div>

					<div class="mb-2 border-t border-outline-gray-1 pt-2">
						<div class="mb-1.5 flex items-center justify-between">
							<p class="text-sm text-ink-gray-5">Padding and gap</p>
							<Button size="sm" :variant="padSides ? 'subtle' : 'ghost'" icon="lucide-square-dashed" title="Per side" aria-label="Per side" @click="padSides = !padSides" />
						</div>
						<div v-if="!padSides" class="grid gap-1" :class="model.gap ? 'grid-cols-3' : 'grid-cols-2'">
							<TokenSelect v-for="f in model.pad.axes" :key="f.key" v-bind="b(f)" />
							<TokenSelect v-if="model.gap" v-bind="b(model.gap)" />
						</div>
						<template v-else>
							<div class="grid grid-cols-4 gap-1">
								<TokenSelect v-for="f in model.pad.sides" :key="f.key" v-bind="b(f)" />
							</div>
							<div v-if="model.gap" class="mt-1 grid grid-cols-2 gap-1">
								<TokenSelect v-bind="b(model.gap)" />
							</div>
						</template>
						<p v-if="model.padNote" class="mt-1 text-xs text-ink-gray-5">{{ model.padNote }}</p>
						<p v-if="model.gap?.note" class="mt-1 text-xs text-ink-gray-5">{{ model.gap.note }}</p>
					</div>

					<div class="mb-2 border-t border-outline-gray-1 pt-2">
						<p class="mb-1.5 text-sm text-ink-gray-5">Margin</p>
						<div class="grid grid-cols-4 gap-1">
							<TokenSelect v-for="f in model.mar.sides" :key="f.key" v-bind="b(f)" />
						</div>
						<p v-if="model.marNote" class="mt-1 text-xs text-ink-gray-5">{{ model.marNote }}</p>
					</div>

					<div class="border-t border-outline-gray-1 pt-2">
						<p class="mb-1.5 text-sm text-ink-gray-5">Fill</p>
						<div class="grid gap-1" :class="model.fill.length === 3 ? 'grid-cols-3' : 'grid-cols-2'">
							<TokenSelect v-for="f in model.fill" :key="f.key" v-bind="b(f)" />
						</div>
						<template v-for="f in model.fill" :key="f.key + 'n'">
							<p v-if="f.note" class="mt-1 text-xs text-ink-gray-5">{{ f.note }}</p>
						</template>
					</div>

					<!-- This element looks like a frappe-ui component the page built by hand. -->
					<div
						v-if="model.rolled"
						class="mt-2 flex items-center gap-2 rounded-6 border border-outline-amber-3 bg-surface-amber-2 p-2 text-ink-amber-7"
					>
						<span class="lucide-triangle-alert size-4 shrink-0" aria-hidden="true" />
						<p class="min-w-0 flex-1 text-base-medium">Hand-rolled {{ model.rolled.lower }}</p>
						<Button
							variant="outline"
							theme="gray"
							size="sm"
							:icon-left="model.rolled.added ? 'lucide-check' : undefined"
							:label="model.rolled.added ? 'Added' : `Use ${model.rolled.name}`"
							@click="sel && toggleSwap(sel, model.rolled!.name)"
						/>
					</div>
				</template>
			</div>
		</Transition>
	</div>
</template>
