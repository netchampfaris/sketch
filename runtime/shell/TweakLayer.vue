<script setup lang="ts">
// Tweak in the Viewer shell: the popover under the picked element, its outlines, the hint and the word by the pointer.
// The page is in the frame, so the pointer is caught there and the selection lives there (runtime/agent/tweakPick.ts):
// it sends what the picked elements are (`facts`) and where they are (`outlines`), and this draws. Every change made here is the shell's own: it updates
// the tweaks (tweaks.ts) and tells the frame what to write. Mounted by the toolbar for the owner and an invited editor.
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useEventListener } from '@vueuse/core'
import { Button, Textarea, TextInput } from 'frappe-ui'
import TokenSelect from './TokenSelect.vue'
import { newId } from './annotate'
import { clamp, typing } from '../shared/dom'
import { CAT, KNOWN, STACK_CLASSES, emitSides, isComposite, madeStack, readSides, type Sides } from '../shared/tweak'
import type { TweakFacts } from '../shared/protocol'
import {
	alike,
	anchor,
	cancelPreview,
	cancelProps,
	commitClasses,
	copyFieldsOf,
	facts,
	inspect,
	outlines,
	previewClasses,
	rev,
	say,
	setCopy,
	setProps,
	tellKeys,
	toggleSwap,
	tokens,
	tweakOf,
	type ClassStep,
	type PropStep,
} from './tweaks'
import { onFrame } from './frame'

const props = defineProps<{ live: boolean }>()
const live = computed(() => props.live)

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
	el: TweakFacts
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

// The selection, as the frame last reported it. The last pick is the one the popover sits under.
const sels = computed(() => (live.value ? facts.value : []))
const sel = computed(() => sels.value[sels.value.length - 1] ?? null)
const selRect = computed<R | null>(() => (live.value ? outlines.value.sel : null))
const padSides = ref(false)
let lastSide: 'below' | 'above' = 'below'
// Space held here (the frame says when it is held there).
const peekHere = ref(false)
const peek = computed(() => peekHere.value || outlines.value.peek)
// A prop tried on while its list hovers a row, until it is kept or put back: what the trigger shows meanwhile.
const propPreview = ref<Record<string, any>>({})

// A new selection: the popover keeps to the side it opens on until it stops fitting, and spacing opens per side when
// the sides already differ.
watch(
	() => sels.value.map((f) => f.ref).join(','),
	() => {
		lastSide = 'below'
		peekHere.value = false
		propPreview.value = {}
		const f = sel.value
		if (!f) return
		const t = tweakOf(f)
		const s = readSides(t ? t.classes : f.classes, 'p')
		padSides.value = s.l !== s.r || s.t !== s.b
	},
)

// ---- The popover's place ---------------------------------------------------------------
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
		const a = anchor.value
		const pt = a ? { x: r.x + a.fx * r.w, y: r.y + a.fy * r.h } : { x: r.x + r.w / 2, y: (Math.max(r.y, 0) + Math.min(r.y + r.h, vh)) / 2 }
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
// The rects come once a frame while things move; the panel's own height changes with its fields.
watch([selRect, facts, rev, padSides], () => nextTick(place), { flush: 'post' })
useEventListener(window, 'resize', () => place())

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
function single(el: TweakFacts) {
	const t = tweakOf(el)
	const classes = t ? [...t.classes] : [...el.classes]
	const orig = t ? t.original.classes : classes
	const name = el.name
	const cs = el.cs

	// frappe-ui components: their own props, nothing else.
	if (el.kind) {
		const fields: IField[] = el.known.map((prop) => {
			const now = el.props[prop]
			const committed = t && prop in t.props ? t.props[prop] : now
			const original = t && prop in t.original.props ? t.original.props[prop] : now
			const tried = `${el.ref}:${prop}`
			return {
				key: prop,
				label: prop[0].toUpperCase() + prop.slice(1),
				value: (tried in propPreview.value ? propPreview.value[tried] : committed) ?? null,
				options: (KNOWN[el.kind]?.[prop] ?? []).map((x) => ({ value: x, label: x })),
				changed: committed !== original,
				el,
				classes,
				prop: { name: prop, committed, original },
			}
		})
		return { name, frappe: true as const, comp: fields }
	}

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
			note: el.notes[cat] ?? null,
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
			note: el.notes.gap ?? null,
			el,
			classes,
			next,
			resetTo: () => [...base().filter((c) => !ownStack(c)), ...orig.filter((c) => CAT.gap.test(c))],
		}
	}

	const styleField = classField('Style', 'style', cs.fontSize)
	const composite = !!styleField.value && isComposite(styleField.value)
	const rolled = el.rolled
	const stack = madeStack(t) || el.stack

	return {
		name,
		frappe: false as const,
		text: el.hasText ? [classField('Colour', 'ink'), styleField, ...(composite ? [] : [classField('Weight', 'weight', cs.fontWeight)])] : [],
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
		padNote: el.notes.pad ?? null,
		marNote: el.notes.mar ?? null,
		gap: /flex|grid/.test(cs.display ?? '') || stack ? gapField(stack) : null,
		fill: [classField('Background', 'bg', '', 'lucide-paint-bucket'), ...(el.bordered ? [classField('Border colour', 'border')] : []), { ...classField('Radius', 'radius', cs.borderTopLeftRadius), icon: 'lucide-square-round-corner', emptyAs: 'radius' as const }],
		rolled: rolled ? { name: rolled, lower: rolled.replace(/([a-z])([A-Z])/g, '$1 $2').toLowerCase(), added: !!t?.swap } : null,
	}
}

// One field over every selected element: equal values show, different ones read "mixed"; an edit
// writes each element from its own classes.
const gid = () => `g${newId()}`
function tryProp(fs: IField[], name: string, v: any) {
	const next = { ...propPreview.value }
	for (const f of fs) next[`${f.el.ref}:${name}`] = v
	propPreview.value = next
}
function untryProp(fs: IField[], name: string) {
	const next = { ...propPreview.value }
	for (const f of fs) delete next[`${f.el.ref}:${name}`]
	propPreview.value = next
}
function fuse(fs: IField[]): Field {
	const f0 = fs[0]
	const same = !f0.mixed && fs.every((f) => !f.mixed && f.value === f0.value)
	const meta = () => ({ id: gid(), alike: alike.value.total })
	const prop = f0.prop
	const edits = (v: string | null): ClassStep[] => fs.map((f) => [f.el, f.next!(v)])
	const each = (v: (f: IField) => any): PropStep[] => fs.map((f) => [f.el, v(f)])
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
		preview: (v) => (prop ? (tryProp(fs, prop.name, v), setProps(each(() => v), prop.name, false)) : previewClasses(edits(v))),
		commit: (v) => (prop ? (untryProp(fs, prop.name), setProps(each(() => v), prop.name, true, meta())) : commitClasses(edits(v), meta())),
		cancel: () => (prop ? (untryProp(fs, prop.name), cancelProps(each((f) => f.prop!.committed), prop.name)) : cancelPreview(fs.map((f) => [f.el, f.classes]))),
		reset: () => (prop ? setProps(each((f) => f.prop!.original), prop.name, true, meta()) : commitClasses(fs.map((f) => [f.el, f.resetTo!()]), meta())),
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
	return el ? copyFieldsOf(el) : []
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

// ---- Keys, with the focus here (in the popover, say) ---------------------------------------
// The frame hears them while the focus is in the page. Taken before the toolbar's own, so Escape lets go of the
// selection before it puts the tool down.
function onKey(e: KeyboardEvent) {
	if (!live.value) return
	if (e.key === 'Shift') return tellKeys({ shift: e.type === 'keydown' })
	if (e.key === ' ' && e.type === 'keyup') {
		// The release must not click a focused button either.
		if (!peekHere.value) return
		peekHere.value = false
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
		// An open token list closes on its own Escape first; after that Escape clears the selection.
		if (e.defaultPrevented || document.querySelector('[data-tweak-select] [role="listbox"]')) return
		inspect('clear')
	} else if (e.key === ' ') {
		if (inSelect) return
		// Hold to see the page without our outlines; repeats still must not scroll it.
		if (!e.repeat) peekHere.value = true
	} else if (e.key !== '\\' && inSelect) return
	else if (e.key === '\\') inspect('parent')
	else if (e.key === 'Enter' && !t?.closest?.('button,a')) inspect('child')
	else return
	e.preventDefault()
	e.stopImmediatePropagation()
}
useEventListener(document, 'keydown', onKey, { capture: true })
useEventListener(document, 'keyup', onKey, { capture: true })
useEventListener(window, 'blur', () => {
	if (peekHere.value) peekHere.value = false
})

// A press or scroll in the page: an open token list closes, as it does on a press outside it.
onBeforeUnmount(
	onFrame('tweak:info', (d) => {
		if (d.outside && live.value) document.body.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }))
	}),
)

watch(live, (on) => {
	if (!on) peekHere.value = false
})
</script>

<template>
	<!-- A hovered row of the toolbar's list: the element, outlined. Works with the picker off. -->
	<div
		v-for="(r, i) in outlines.hl"
		:key="'h' + i"
		class="pointer-events-none fixed left-0 top-0 z-[2147483000] rounded-[4px] border-[1.5px] border-solid border-outline-violet-6"
		:style="boxStyle(r)"
	>
		<span class="absolute inset-0 rounded-[3px] bg-surface-violet-7 opacity-[0.06]" />
	</div>

	<div v-if="live" class="contents" :class="peek && 'invisible'">
		<!-- Hover outline: the same style as the selection at 60%, gliding between elements. -->
		<template v-if="outlines.hover">
			<div
				class="pointer-events-none fixed left-0 top-0 z-[2147483000] rounded-[4px] border-[1.5px] border-solid border-outline-violet-6 opacity-60 transition-[transform,width,height] duration-[90ms] ease-out motion-reduce:transition-none"
				:style="boxStyle(outlines.hover)"
			>
				<span class="absolute inset-0 rounded-[3px] bg-surface-violet-7 opacity-[0.06]" />
			</div>
			<div
				v-if="outlines.hoverName"
				class="pointer-events-none fixed z-[2147483000] whitespace-nowrap rounded-[4px] bg-surface-violet-7 px-1.5 py-0.5 text-xs font-medium text-white opacity-80"
				:style="tagStyle(outlines.hover)"
			>
				{{ outlines.hoverName }}
			</div>
		</template>

		<!-- Copies of what is picked: dashed and faint, so the pick stays the loudest thing. -->
		<div
			v-for="(r, i) in outlines.faint"
			:key="'f' + i"
			class="pointer-events-none fixed left-0 top-0 z-[2147483000] rounded-[4px] border border-dashed border-outline-violet-6 opacity-40"
			:style="boxStyle(r)"
		/>
		<div
			v-for="(r, i) in outlines.others"
			:key="'o' + i"
			class="pointer-events-none fixed left-0 top-0 z-[2147483000] rounded-[4px] border-[1.5px] border-solid border-outline-violet-6"
			:style="boxStyle(r)"
		>
			<span class="absolute inset-0 rounded-[3px] bg-surface-violet-7 opacity-[0.06]" />
		</div>
		<div
			v-if="say"
			class="pointer-events-none fixed z-[2147483000] whitespace-nowrap rounded-[4px] bg-surface-violet-7 px-1.5 py-0.5 text-xs font-medium text-white"
			:style="{ left: `${say.x + 12}px`, top: `${say.y + 12}px` }"
		>
			{{ say.text }}
		</div>

		<template v-if="selRect">
			<div
				class="pointer-events-none fixed left-0 top-0 z-[2147483000] rounded-[4px] border-[1.5px] border-solid border-outline-violet-6"
				:style="boxStyle(selRect)"
			>
				<span class="absolute inset-0 rounded-[3px] bg-surface-violet-7 opacity-[0.06]" />
			</div>
			<div
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
				v-if="sel && model && selRect"
				ref="panel"
				role="region"
				aria-label="Tweak"
				class="pointer-events-auto fixed z-[2147483000] w-[304px] overflow-y-auto rounded-5 border border-outline-gray-2 bg-surface-elevation-2 p-2 shadow-xl"
				:style="panelStyle"
				@pointerdown.stop
				@focusin.stop
			>
				<div class="flex items-center gap-2 px-1 pb-2">
					<p class="min-w-0 truncate text-base font-medium text-ink-gray-9">{{ model.name }}</p>
					<span v-if="alike.total > 1" class="shrink-0 text-sm text-ink-gray-5">{{ sels.length }} of {{ alike.total }}</span>
					<Button v-if="alike.joinable" class="ml-auto shrink-0" size="sm" variant="ghost" label="Select all" @click="inspect('all')" />
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
