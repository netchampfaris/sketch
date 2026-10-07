<script setup lang="ts">
// Click-to-annotate toolbar for prototypes. A faint trigger sits in a corner; it opens the
// toolbar in comment mode. While commenting, the page is read-only: every pointer event is
// caught before the app sees it, so a click picks an element instead of using it.
// The toolbar also hosts the tweak tool (its own files), which registers itself in `tweakApi`.
// Mounted by index.ts into its own app, so it never becomes part of the Prototype's vnode tree.
import { computed, onBeforeUnmount, ref, shallowRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useElementSize, useEventListener, useWindowSize } from '@vueuse/core'
import { Badge, Button, TabButtons, Tooltip, toast } from 'frappe-ui'
import { setKeepHandler } from 'sketch:variants'
import { saveState } from './store'
import NotePopover from './NotePopover.vue'
import Pins from './Pins.vue'
import TweakLayer from './TweakLayer.vue'
import {
	ANCHORS,
	active,
	addNote,
	analyzeBox,
	buildPrompt,
	childOf,
	clamp,
	clearNotes,
	clearSent,
	componentOf,
	copyText,
	enabled,
	flashEl,
	fracRect,
	hoverEl,
	hoverFrac,
	hoverLabel,
	infoOf,
	labelOf,
	listen,
	markSent,
	mode,
	notes,
	parentOf,
	pinPoint,
	readAnchor,
	redlines,
	removeNote,
	resolve,
	resolveNote,
	routeKey,
	setEnabled,
	storedAnchor,
	tagOf,
	targetOf,
	tweakApi,
	typing,
	updateNote,
	writeAnchor,
	type Anchor,
	type BoxInfo,
	type ComponentInfo,
	type ElInfo,
	type Mode,
	type Note,
	type Rect,
	type Redline,
} from './annotate'

const route = useRoute()
const router = useRouter()
const key = computed(() => routeKey(route))
const { width: vw, height: vh } = useWindowSize()
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

// Comment-mode machinery (picking, box, measuring) runs only for the comment tool.
const picking = computed(() => enabled.value && active.value && mode.value === 'comment')

// ---- Popover ---------------------------------------------------------------------------
type Draft = {
	x: number
	y: number
	els: Element[] // the first one is the note's element (a box note's container)
	// Read from the live elements when they are picked, never looked up again by selector.
	infos: ElInfo[]
	comp?: ComponentInfo
	box?: BoxInfo
	editing?: string // id of the note being edited
	component: string
	extra: number
}
const draft = shallowRef<Draft | null>(null)
const draftKey = ref(0)
const text = ref('')

const close = () => (draft.value = null)
// A new note may be re-aimed while nothing is typed; an edit never is.
const canRetarget = () => !draft.value || (!draft.value.editing && !text.value.trim())

function centreOf(el: Element) {
	const r = el.getBoundingClientRect()
	return { x: clamp(r.left + r.width / 2, 8, vw.value - 8), y: clamp(r.top + r.height / 2, 8, vh.value - 8) }
}

function show(els: Element[], x: number, y: number, box?: BoxInfo) {
	const first = els[0]
	const fresh = !draft.value
	const comp = componentOf(first)
	draft.value = {
		x,
		y,
		els,
		infos: els.map(infoOf),
		comp,
		box,
		component: labelOf(first),
		extra: els.length - 1,
	}
	if (fresh) {
		text.value = ''
		draftKey.value++
	}
}

function openEdit(n: Note, x: number, y: number) {
	const els = [0, ...(n.extras ?? []).map((_, i) => i + 1)].map((i) => resolveNote(n, i)).filter((e): e is Element => !!e)
	text.value = n.note
	draft.value = { x, y, els, infos: [], box: n.box, editing: n.id, component: n.component || n.element.split(/[.\s]/)[0], extra: n.extras?.length ?? 0 }
	draftKey.value++
}

function openBox(b: Rect) {
	const { container, ...info } = analyzeBox(b)
	const c = container.getBoundingClientRect()
	const box: BoxInfo = { ...info, fx: (b.x - c.left) / (c.width || 1), fy: (b.y - c.top) / (c.height || 1), fw: b.w / (c.width || 1), fh: b.h / (c.height || 1) }
	show([container], clamp(b.x + b.w, 8, vw.value - 8), clamp(b.y + b.h, 8, vh.value - 8), box)
}

function save() {
	const d = draft.value
	const t = text.value.trim()
	if (!d || !t) return
	if (d.editing) updateNote(d.editing, t)
	else {
		const el = d.els[0]
		const r = el.getBoundingClientRect()
		const c = d.comp!
		const [info, ...rest] = d.infos
		addNote(
			{
				route: key.value,
				viewport: `${window.innerWidth}x${window.innerHeight}`,
				selector: info.selector,
				component: c.component,
				componentChain: c.chain,
				file: c.file,
				element: info.element,
				text: info.text,
				state: info.state || undefined,
				extras: rest.length ? rest : undefined,
				box: d.box,
				note: t,
				offset: {
					x: r.width ? clamp((d.x - r.left) / r.width, 0, 1) : 0,
					y: r.height ? clamp((d.y - r.top) / r.height, 0, 1) : 0,
				},
				rect: { x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height) },
			},
			d.els,
		)
	}
	close()
}

// Keep on a Variants set is a normal note, anchored on the set's first element.
setKeepHandler((el, note) => {
	const r = el.getBoundingClientRect()
	const c = componentOf(el)
	const info = infoOf(el)
	addNote(
		{
			route: key.value,
			viewport: `${window.innerWidth}x${window.innerHeight}`,
			selector: info.selector,
			component: c.component,
			componentChain: c.chain,
			file: c.file,
			element: info.element,
			text: info.text,
			state: info.state || undefined,
			note,
			offset: { x: 0.5, y: 0.5 },
			rect: { x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height) },
		},
		[el],
	)
})
onBeforeUnmount(() => setKeepHandler(null))

function remove() {
	if (draft.value?.editing) removeNote(draft.value.editing)
	close()
}

// Parent and child (the \ and Enter keys) swap the first element; any shift-clicked extras stay.
function step(dir: 'parent' | 'child') {
	const d = draft.value
	if (!d || d.editing || d.box) return
	const next = dir === 'parent' ? parentOf(d.els[0]) : childOf(d.els[0])
	if (!next) return
	const p = centreOf(next)
	show([next, ...d.els.slice(1).filter((e) => e !== next)], p.x, p.y)
}

// ---- Frame: outlines, box and redlines, re-measured on scroll and resize ---------------
type Out = { key: string; x: number; y: number; w: number; h: number; dashed?: boolean }
const outs = shallowRef<Out[]>([])
const lines = shallowRef<Redline[]>([])
// The hover outline is one element that glides; it keeps its last box while it fades out.
const hoverBox = shallowRef<Rect | null>(null)
const hoverOn = ref(false)
const glide = ref(true)
const scrolling = ref(false)
const dragRect = ref<Rect | null>(null)
const alt = ref(false)
const shift = ref(false)
// Shift held while the pointer moves means picking more elements (not typing a capital):
// the note box steps aside until Shift is released.
const shiftPick = ref(false)

const toRect = (r: DOMRect): Rect => ({ x: r.left, y: r.top, w: r.width, h: r.height })
const toDom = (r: Rect) => new DOMRect(r.x, r.y, r.w, r.h)

let raf = 0
function measure() {
	raf = 0
	const o: Out[] = []
	const d = draft.value
	let sel: Rect | null = null
	if (d) {
		const live = d.els.filter((e) => e.isConnected)
		if (live[0]) sel = toRect(live[0].getBoundingClientRect())
		if (d.box && live[0]) {
			sel = fracRect(live[0].getBoundingClientRect(), d.box)
			o.push({ key: 'draft-box', ...sel, dashed: true })
		} else live.forEach((e, i) => o.push({ key: `sel-${i}`, ...toRect(e.getBoundingClientRect()) }))
	}
	const he = hoverEl.value?.isConnected ? hoverEl.value : null
	let on = false
	if (he) {
		const r = he.getBoundingClientRect()
		if (hoverFrac.value) o.push({ key: 'hover-box', ...fracRect(r, hoverFrac.value), dashed: true })
		else {
			on = true
			hoverBox.value = toRect(r)
		}
	}
	// While a note is open only the selection shows, unless Shift (add or remove) or Alt (measure) is held.
	if ((d && !(shift.value || alt.value)) || dragRect.value) on = false
	if (on && !hoverOn.value) {
		// Appearing: jump to the element, then glide from the next frame on.
		glide.value = false
		requestAnimationFrame(() => (glide.value = true))
	}
	hoverOn.value = on
	if (flashEl.value?.isConnected) o.push({ key: 'flash', ...toRect(flashEl.value.getBoundingClientRect()) })
	outs.value = o

	// Hold Alt: against the selection when there is one, else the hovered element against its parent.
	let l: Redline[] = []
	if (picking.value && alt.value && he) {
		if (sel) {
			if (!d!.els.includes(he)) l = redlines(toDom(sel), he.getBoundingClientRect())
		} else {
			const p = parentOf(he)
			if (p) l = redlines(p.getBoundingClientRect(), he.getBoundingClientRect())
		}
	}
	lines.value = l
}
function schedule() {
	if (!raf) raf = requestAnimationFrame(measure)
}
watch([hoverEl, hoverFrac, flashEl, draft, alt, shift, picking], schedule, { flush: 'post' })
// Scroll doesn't bubble, so listen in the capture phase to catch the app's inner scrollers.
// The glide is off while scrolling, or the outline would trail the content.
let scrollTimer = 0
function onScroll() {
	scrolling.value = true
	clearTimeout(scrollTimer)
	scrollTimer = window.setTimeout(() => (scrolling.value = false), 120)
	schedule()
}
useEventListener(window, 'scroll', onScroll, { capture: true, passive: true })
useEventListener(window, 'resize', schedule)

// ---- Picking ---------------------------------------------------------------------------
const stop = (e: Event) => {
	e.stopPropagation()
	e.stopImmediatePropagation()
}

let down: { x: number; y: number } | null = null
let dragging = false
let skipClick = false
function resetDrag() {
	down = null
	dragging = false
	dragRect.value = null
}

function onDown(e: MouseEvent) {
	if (!targetOf(e)) return
	// No default: no text selection, and shift-click can't extend one.
	e.preventDefault()
	stop(e)
	skipClick = false
	if (e.button === 0) down = { x: e.clientX, y: e.clientY }
}

function onMove(e: PointerEvent) {
	alt.value = e.altKey
	shift.value = e.shiftKey
	shiftPick.value = e.shiftKey && !!draft.value && !draft.value.editing && !draft.value.box
	if (down && e.buttons === 0) resetDrag() // the button was released outside the window
	if (down) {
		if (!dragging && Math.hypot(e.clientX - down.x, e.clientY - down.y) > 4) {
			dragging = true
			hoverEl.value = null
		}
		if (dragging) {
			dragRect.value = { x: Math.min(down.x, e.clientX), y: Math.min(down.y, e.clientY), w: Math.abs(e.clientX - down.x), h: Math.abs(e.clientY - down.y) }
			return
		}
	}
	const el = targetOf(e)
	// Over our own UI (not a pin, which outlines its element on purpose) there is nothing to outline.
	if (!el && e.target instanceof Element && !e.target.closest('[data-annotate-pin]')) hoverEl.value = null
	if (!el || el === document.body || el === document.documentElement) return
	if (el !== hoverEl.value || hoverFrac.value) {
		hoverEl.value = el
		hoverFrac.value = null
		hoverLabel.value = tagOf(el)
	}
}

function onUp(e: MouseEvent) {
	if (!down) return
	const was = dragging
	const rect = dragRect.value
	resetDrag()
	if (!was) return
	e.preventDefault()
	stop(e)
	skipClick = true // the click that follows a drag is not a pick
	if (rect && canRetarget()) openBox(rect)
}

function onClick(e: MouseEvent) {
	const el = targetOf(e)
	if (!el) return
	e.preventDefault()
	stop(e)
	if (skipClick) {
		skipClick = false
		return
	}
	const d = draft.value
	// A keyboard activation (Enter on a focused element) has no pointer: aim at the element's centre.
	const at = e.detail === 0 ? centreOf(el) : { x: e.clientX, y: e.clientY }
	if (!d) return show([el], at.x, at.y)
	if (d.editing) return
	if (e.shiftKey && !d.box) {
		// Shift adds or removes; the last element can't be removed.
		if (!d.els.includes(el)) show([...d.els, el], d.x, d.y)
		else if (d.els.length > 1) show(d.els.filter((x) => x !== el), d.x, d.y)
		return
	}
	if (canRetarget()) show([el], at.x, at.y)
}

// Everything else is ours alone: the app must not see it.
function swallow(e: Event) {
	if (targetOf(e)) stop(e)
}

// Listeners live only while commenting, and are removed on exit or unmount.
let off: (() => void) | null = null
function attach() {
	off = listen([
		['pointermove', onMove],
		['mousedown', onDown],
		['mouseup', onUp],
		['click', onClick],
		['pointerdown', swallow],
		['pointerup', swallow],
		['dblclick', swallow],
		['contextmenu', swallow],
		['auxclick', swallow],
	])
}
function detach() {
	off?.()
	off = null
}

watch(
	picking,
	(on) => {
		detach()
		resetDrag()
		alt.value = false
		shift.value = false
		if (on) attach()
		else {
			hoverEl.value = null
			close()
		}
	},
	{ immediate: true },
)
// The one owner of the crosshair: either tool picking turns it on.
watch(
	() => picking.value || (active.value && mode.value === 'tweak'),
	(on) => (document.body.style.cursor = on ? 'crosshair' : ''),
	{ immediate: true },
)
watch(enabled, (on) => {
	if (!on) {
		close()
		listOpen.value = false
	}
})
watch(mode, () => (listOpen.value = false))

let flashTimer = 0
let unmounted = false
onBeforeUnmount(() => {
	detach()
	cancelAnimationFrame(raf)
	clearTimeout(flashTimer)
	clearTimeout(snapTimer)
	clearTimeout(scrollTimer)
	clearTimeout(confirmTimer)
	document.body.style.cursor = ''
	hoverEl.value = null
	hoverFrac.value = null
	flashEl.value = null
	unmounted = true
})

// Leaving a page with a half-written note keeps it as that page's draft; coming back restores it.
type Saved = { text: string; selectors: string[]; x: number; y: number; box?: BoxInfo }
const saved = new Map<string, Saved>()
watch(key, async (now, was) => {
	const d = draft.value
	if (d && !d.editing) {
		if (text.value.trim()) saved.set(was, { text: text.value, selectors: d.infos.map((i) => i.selector), x: d.x, y: d.y, box: d.box })
		close()
	}
	const s = saved.get(now)
	if (!s) return
	// The page needs a moment to render its elements again.
	for (let i = 0; i < 30; i++) {
		if (unmounted || key.value !== now || !enabled.value) return
		const els = s.selectors.map((sel) => resolve(sel))
		if (els.every(Boolean)) {
			saved.delete(now)
			close()
			const first = els[0] as Element
			const c = first.getBoundingClientRect()
			const p = s.box ? fracRect(c, s.box) : null
			const at = p ? { x: clamp(p.x + p.w, 8, vw.value - 8), y: clamp(p.y + p.h, 8, vh.value - 8) } : centreOf(first)
			show(els as Element[], at.x, at.y, s.box)
			text.value = s.text
			return
		}
		await sleep(50)
	}
})

// ---- Keyboard --------------------------------------------------------------------------
// Switch tool, or switch it off when it is already the one in use (the C and T keys).
function pick(m: Mode) {
	if (active.value && mode.value === m) active.value = false
	else use(m)
}
// The tabs only ever switch on: the current tab stays lit, and Escape or close is the way off.
function use(m: Mode) {
	mode.value = m
	active.value = true
}

useEventListener(document, 'keydown', (e: KeyboardEvent) => {
	alt.value = e.altKey
	shift.value = e.shiftKey
	if (e.key === 'Escape') {
		// The tweak layer takes its own Escape first and says so.
		if (!enabled.value || e.defaultPrevented) return
		// Let an open frappe-ui dialog take its own Escape.
		if (document.querySelector('[role="dialog"][data-state="open"]')) return
		if (dragging) resetDrag()
		else if (draft.value) close()
		else if (listOpen.value) listOpen.value = false
		else if (active.value) active.value = false
		else return
		e.preventDefault()
		return
	}
	if (e.metaKey || e.ctrlKey || e.altKey || e.isComposing) return
	const tool: Mode | null = e.key === 'c' || e.key === 'C' ? 'comment' : e.key === 't' || e.key === 'T' ? 'tweak' : null
	if (tool && !e.repeat && !typing(e.target)) {
		if (!enabled.value) {
			setEnabled(true)
			use(tool)
		} else pick(tool)
		e.preventDefault()
		return
	}
	// Parent and child, only while nothing is typed. Enter on a focused button stays that button's.
	const d = draft.value
	if (!d || d.editing || d.box || text.value.trim()) return
	if (e.key === '\\') step('parent')
	else if (e.key === 'Enter' && !e.shiftKey && !(e.target as HTMLElement | null)?.closest?.('button')) step('child')
	else return
	e.preventDefault()
})
// Leaving the page window leaves no hover behind.
useEventListener(document.documentElement, 'mouseleave', () => {
	if (picking.value) hoverEl.value = null
})
// Closing a note drops the stale hover too.
watch(draft, (d) => !d && picking.value && (hoverEl.value = null))
useEventListener(document, 'keyup', (e: KeyboardEvent) => {
	alt.value = e.altKey
	shift.value = e.shiftKey
	if (!e.shiftKey) shiftPick.value = false
})
// A held Alt or Shift never gets its keyup when the window loses focus.
useEventListener(window, 'blur', () => {
	alt.value = false
	shift.value = false
	shiftPick.value = false
	resetDrag()
})

// ---- Toolbar position ------------------------------------------------------------------
const INSET = 16
const anchor = ref<Anchor>(readAnchor())
// Until the toolbar has been moved once, the trigger keeps to the bottom-right corner.
const moved = ref(storedAnchor() !== null)
// The faint trigger sits where the toolbar last snapped: 12px in from a corner, centred on a centre anchor.
const triggerStyle = computed(() => {
	const [v, h] = (moved.value ? anchor.value : 'bottom-right').split('-')
	const s: Record<string, string> = v === 'top' ? { top: '12px' } : { bottom: '12px' }
	// Above the Variants pill when there is one: the pill sets --sketch-variants-h, and the -8px fallback cancels the +8px.
	if (v === 'bottom' && h === 'right') s.bottom = 'calc(12px + var(--sketch-variants-h, -8px) + 8px)'
	if (h === 'left') s.left = '12px'
	else if (h === 'right') s.right = '12px'
	else s.left = 'calc(50% - 16px)'
	return s
})
const bar = ref<HTMLElement | null>(null)
const { width: bw, height: bh } = useElementSize(bar, { width: 0, height: 0 }, { box: 'border-box' })
const ready = computed(() => bw.value > 0 && bh.value > 0)

// Resizing the window re-places the toolbar: every position is derived from the anchor.
function place(a: Anchor) {
	const [v, h] = a.split('-')
	const left = h === 'left' ? INSET : h === 'right' ? vw.value - bw.value - INSET : (vw.value - bw.value) / 2
	const top = v === 'top' ? INSET : vh.value - bh.value - INSET
	return { left: clamp(left, 0, Math.max(0, vw.value - bw.value)), top: clamp(top, 0, Math.max(0, vh.value - bh.value)) }
}
const dragPos = ref<{ left: number; top: number } | null>(null)
const pos = computed(() => dragPos.value ?? place(anchor.value))
const barBox = computed(() => ({ left: pos.value.left, top: pos.value.top, right: pos.value.left + bw.value, bottom: pos.value.top + bh.value }))

// The toolbar drags by its background. A press anywhere on it may become a drag: past 4px of
// travel it is one, and the click that ends it is swallowed so no button fires.
const snapping = ref(false)
const barDragging = ref(false)
let snapTimer = 0
let grab: { x: number; y: number; left: number; top: number } | null = null
let swallowBarClick = false
function barDown(e: PointerEvent) {
	if (e.button !== 0) return
	grab = { x: e.clientX, y: e.clientY, ...pos.value }
}
function barMove(e: PointerEvent) {
	if (!grab) return
	if (!barDragging.value) {
		if (Math.hypot(e.clientX - grab.x, e.clientY - grab.y) <= 4) return
		barDragging.value = true
		;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
		listOpen.value = false
		clearTimeout(snapTimer)
		snapping.value = false
	}
	dragPos.value = {
		left: clamp(grab.left + e.clientX - grab.x, 0, vw.value - bw.value),
		top: clamp(grab.top + e.clientY - grab.y, 0, vh.value - bh.value),
	}
}
function barUp() {
	const p = dragPos.value
	const was = barDragging.value
	grab = null
	barDragging.value = false
	if (!was || !p) return
	swallowBarClick = true
	window.setTimeout(() => (swallowBarClick = false), 50)
	let best = anchor.value
	let min = Infinity
	for (const a of ANCHORS) {
		const q = place(a)
		const dist = Math.hypot(q.left - p.left, q.top - p.top)
		if (dist < min) {
			min = dist
			best = a
		}
	}
	anchor.value = best
	moved.value = true
	writeAnchor(best)
	snapping.value = true
	dragPos.value = null
	snapTimer = window.setTimeout(() => (snapping.value = false), 200)
}
function barClick(e: MouseEvent) {
	if (!swallowBarClick) return
	swallowBarClick = false
	e.stopPropagation()
	e.preventDefault()
}

// ---- Toolbar actions: the count and copy belong to the tool in use ---------------------
const tweakCount = computed(() => tweakApi.value?.count.value ?? 0)
const tweakItems = computed(() => tweakApi.value?.items?.value ?? [])
const unsent = computed(() => notes.value.filter((n) => !n.sent))
const hasSent = computed(() => notes.value.some((n) => n.sent))
const count = computed(() => (mode.value === 'tweak' ? tweakCount.value : notes.value.length))
const noun = computed(() => (mode.value === 'tweak' ? 'tweak' : 'note'))
const plural = (n: number, w: string) => `${n} ${w}${n === 1 ? '' : 's'}`
const countLabel = computed(() => (mode.value === 'tweak' ? plural(tweakCount.value, 'tweak') : unsent.value.length ? plural(unsent.value.length, 'note') : 'All sent'))

// Tabs: one tooltip for the pair, worded for the tab under the pointer.
const tabOptions = [
	{ label: 'Comment', value: 'comment', iconLeft: 'lucide-mouse-pointer-click', onClick: () => use('comment') },
	{ label: 'Tweak', value: 'tweak', iconLeft: 'lucide-paintbrush', onClick: () => use('tweak') },
]
const tabHover = ref<Mode>('comment')
function onTabHover(e: PointerEvent) {
	const v = (e.target as Element).closest('[data-value]')?.getAttribute('data-value')
	if (v === 'comment' || v === 'tweak') tabHover.value = v
}
const tabTip = computed(() => (tabHover.value === 'tweak' ? 'Try token changes live (T)' : 'Leave notes on elements (C)'))

function openFromTrigger() {
	setEnabled(true)
	use('comment')
}

// Notes: copies what hasn't gone out yet, or everything when it all has; then marks it sent.
async function copy() {
	if (mode.value === 'tweak') {
		const api = tweakApi.value
		if (!api) return
		const n = api.count.value
		if (!n) return
		if (!(await copyText(api.copy()))) return toast.error('Could not copy to the clipboard')
		return toast.success(`Copied ${plural(n, 'tweak')}`)
	}
	const list = unsent.value.length ? unsent.value : notes.value
	if (!list.length) return
	const ok = await copyText(buildPrompt(list))
	if (!ok) return toast.error('Could not copy to the clipboard')
	markSent(list.map((n) => n.id))
	toast.success(`Copied ${plural(list.length, 'note')}`)
}

// Clearing asks in place: the first click turns the button into "Clear 3 notes", a second click
// within 3s does it. A dialog would sit under the picker, which would pick its button instead.
const confirming = ref(false)
let confirmTimer = 0
function clear() {
	clearTimeout(confirmTimer)
	if (!confirming.value) {
		confirming.value = true
		confirmTimer = window.setTimeout(() => (confirming.value = false), 3000)
		return
	}
	confirming.value = false
	if (mode.value === 'tweak') tweakApi.value?.reset()
	else {
		clearNotes()
		close()
	}
}
watch([mode, enabled], () => (confirming.value = false))

// ---- Lists (notes or tweaks) -----------------------------------------------------------
const listOpen = ref(false)
const groupBy = <T extends { route: string }>(items: T[]) => {
	const m = new Map<string, T[]>()
	for (const n of items) m.set(n.route, [...(m.get(n.route) ?? []), n])
	return [...m]
}
const groups = computed(() => groupBy(notes.value))
const tweakGroups = computed(() => groupBy(tweakItems.value))
// The list has nothing left to show at zero, and a hovered tweak row must not leave its highlight behind.
watch(count, (n) => !n && (listOpen.value = false))
watch(listOpen, (on) => {
	if (!on) {
		confirming.value = false
		tweakApi.value?.highlight(null)
	}
})

const panelBelow = computed(() => anchor.value.startsWith('top'))
const panelStyle = computed(() => {
	const b = barBox.value
	const w = 320
	const left = `${clamp((b.left + b.right) / 2 - w / 2, 8, Math.max(8, vw.value - w - 8))}px`
	// Above the toolbar, or below it when the toolbar sits at the top.
	return panelBelow.value ? { left, top: `${b.bottom + 8}px` } : { left, bottom: `${vh.value - b.top + 8}px` }
})

// Outside click closes it. Registered before the pick listeners, so it still sees page clicks they swallow.
useEventListener(
	document,
	'pointerdown',
	(e: PointerEvent) => {
		if (!listOpen.value) return
		if (e.target instanceof Element && e.target.closest('[data-notes-panel],[data-notes-trigger]')) return
		listOpen.value = false
	},
	{ capture: true },
)

// A note on another page needs its route first, then a moment for the page to render.
async function reveal(n: Note, behavior: ScrollBehavior): Promise<Element | null> {
	if (routeKey(route) !== n.route) await router.push(n.route).catch(() => {})
	for (let i = 0; i < 30 && !unmounted; i++) {
		const el = resolveNote(n)
		if (el) {
			el.scrollIntoView({ block: 'center', behavior })
			return el
		}
		await sleep(50)
	}
	return null
}

async function jump(n: Note) {
	const el = await reveal(n, 'smooth')
	if (!el) return
	flashEl.value = el
	clearTimeout(flashTimer)
	flashTimer = window.setTimeout(() => (flashEl.value = null), 1000)
}

async function edit(n: Note) {
	listOpen.value = false
	await reveal(n, 'auto')
	const p = pinPoint(n)
	openEdit(n, p.x, p.y)
}

function revealTweak(id: string) {
	listOpen.value = false
	tweakApi.value?.reveal(id)
}
</script>

<template>
	<!-- The faint way in. Stays mounted so it can fade out as the toolbar fades in at the same spot. -->
	<Tooltip :text="tweakCount ? `Annotate (C), ${plural(tweakCount, 'tweak')} applied` : 'Annotate (C)'">
		<button
			type="button"
			data-annotate-ui
			aria-label="Annotate"
			:aria-hidden="enabled"
			:tabindex="enabled ? -1 : 0"
			:style="triggerStyle"
			class="fixed z-[60] flex size-8 items-center justify-center rounded-[10px] bg-black-overlay-800 text-white shadow-sm ring-1 ring-white-overlay-100 transition-opacity duration-150"
			:class="enabled ? 'pointer-events-none opacity-0' : ['pointer-events-auto hover:opacity-100 focus-visible:opacity-100', tweakCount ? 'opacity-60' : 'opacity-20']"
			@click="openFromTrigger"
		>
			<span class="lucide-mouse-pointer-click size-4" aria-hidden="true" />
			<!-- Tweaks stay applied with the toolbar closed; the dot says the page isn't as built. -->
			<span v-if="tweakCount" class="absolute -right-1 -top-1 size-2.5 rounded-full bg-surface-violet-7 ring-2 ring-surface-base" aria-hidden="true" />
		</button>
	</Tooltip>

	<!-- Always mounted so tweaks stay applied while the toolbar is closed. -->
	<TweakLayer />

	<template v-if="enabled">
		<Pins v-if="mode === 'comment'" :route="key" :selected="draft?.editing" @open="(n, x, y) => openEdit(n, x, y)" />

		<!-- The hover outline: one element that glides, fades out when picking ends. -->
		<div
			data-annotate-ui
			class="pointer-events-none fixed left-0 top-0 z-[60] rounded-[4px] border-[1.5px] border-outline-blue-6"
			:class="[hoverOn ? 'opacity-100' : 'opacity-0', glide && !scrolling ? 'transition-[transform,width,height,opacity] duration-[90ms] ease-out motion-reduce:transition-opacity' : 'transition-opacity duration-100']"
			:style="hoverBox ? { transform: `translate(${hoverBox.x}px, ${hoverBox.y}px)`, width: `${hoverBox.w}px`, height: `${hoverBox.h}px` } : { display: 'none' }"
			aria-hidden="true"
		>
			<!-- Own layer so the tint can be faint while the border stays solid. -->
			<span class="absolute inset-0 bg-surface-blue-7 opacity-[0.06]" />
			<span
				v-if="hoverLabel"
				class="absolute left-0 max-w-xs truncate whitespace-pre rounded-[4px] bg-surface-blue-7 px-1.5 py-0.5 text-xs font-medium text-white"
				:class="hoverBox && hoverBox.y < 30 ? 'top-full mt-1' : 'bottom-full mb-1'"
			>{{ hoverLabel }}</span>
		</div>

		<!-- Selected elements, the box of a note, the flash after a jump. Never catch the pointer. -->
		<div
			v-for="o in outs"
			:key="o.key"
			data-annotate-ui
			class="pointer-events-none fixed z-[60] border-[1.5px] border-outline-blue-6"
			:class="o.dashed ? 'rounded-5 border-dashed' : 'rounded-[4px]'"
			:style="{ left: `${o.x}px`, top: `${o.y}px`, width: `${o.w}px`, height: `${o.h}px` }"
			aria-hidden="true"
		>
			<span class="absolute inset-0 bg-surface-blue-7" :class="o.dashed ? 'rounded-5 opacity-[0.08]' : 'opacity-[0.06]'" />
		</div>

		<!-- The box while it is being dragged, with its size. -->
		<Transition enter-from-class="opacity-0" enter-active-class="transition-opacity duration-100">
			<div
				v-if="dragRect"
				data-annotate-ui
				class="pointer-events-none fixed z-[60] rounded-5 border-[1.5px] border-dashed border-outline-blue-6"
				:style="{ left: `${dragRect.x}px`, top: `${dragRect.y}px`, width: `${dragRect.w}px`, height: `${dragRect.h}px` }"
				aria-hidden="true"
			>
				<span class="absolute inset-0 rounded-5 bg-surface-blue-7 opacity-[0.08]" />
				<span
					class="absolute right-0 whitespace-nowrap rounded-[4px] bg-surface-blue-7 px-1 text-xs tabular-nums text-white"
					:class="dragRect.y + dragRect.h > vh - 28 ? 'bottom-1 right-1' : 'top-full mt-1'"
				>{{ Math.round(dragRect.w) }} × {{ Math.round(dragRect.h) }}</span>
			</div>
		</Transition>

		<!-- Hold Alt: distances in px. -->
		<template v-for="(l, i) in lines" :key="`l${i}`">
			<div
				data-annotate-ui
				class="pointer-events-none fixed z-[60] bg-surface-red-7"
				:style="{ left: `${l.x}px`, top: `${l.y}px`, width: `${l.w}px`, height: `${l.h}px` }"
				aria-hidden="true"
			/>
			<div
				data-annotate-ui
				class="pointer-events-none fixed z-[60] -translate-x-1/2 -translate-y-1/2 rounded-[4px] bg-surface-red-7 px-1 text-xs tabular-nums text-white"
				:style="{ left: `${l.lx}px`, top: `${l.ly}px` }"
				aria-hidden="true"
			>{{ l.label }}</div>
		</template>

		<Transition
			enter-from-class="opacity-0 scale-[0.96] motion-reduce:scale-100"
			enter-active-class="transition duration-[140ms] ease-out motion-reduce:transition-opacity"
			leave-active-class="transition duration-100 ease-in"
			leave-to-class="opacity-0"
		>
			<NotePopover
				v-if="draft"
				:key="draftKey"
				:class="shiftPick && 'invisible'"
				v-model="text"
				:x="draft.x"
				:y="draft.y"
				:component="draft.component"
				:extra="draft.extra"
				:editing="!!draft.editing"
				:avoid="ready ? barBox : null"
				@save="save"
				@cancel="close"
				@delete="remove"
			/>
		</Transition>

		<Transition
			:enter-from-class="panelBelow ? 'opacity-0 -translate-y-1' : 'opacity-0 translate-y-1'"
			enter-active-class="transition duration-[140ms] ease-out motion-reduce:transition-opacity"
			leave-active-class="transition-opacity duration-100"
			leave-to-class="opacity-0"
		>
			<div
				v-if="listOpen"
				data-annotate-ui
				data-notes-panel
				class="pointer-events-auto fixed z-[60] flex max-h-96 w-80 flex-col rounded-5 border border-outline-gray-2 bg-surface-elevation-2 shadow-xl"
				:style="panelStyle"
			>
				<div class="min-h-0 flex-1 overflow-y-auto p-1.5">
					<!-- Notes -->
					<template v-if="mode === 'comment'">
						<template v-for="[r, list] in groups" :key="r">
							<p v-if="groups.length > 1" class="px-2 pt-2 pb-1 text-sm text-ink-gray-5">{{ r }}</p>
							<div
								v-for="(n, i) in list"
								:key="n.id"
								data-annotate-ui
								role="button"
								tabindex="0"
								class="group flex cursor-pointer gap-2 rounded-lg px-2 py-1.5 transition-colors duration-100 hover:bg-surface-gray-2"
								:class="n.sent && 'opacity-60'"
								@click="jump(n)"
								@keydown.enter.self="jump(n)"
							>
								<span
									class="mt-px flex size-5 shrink-0 items-center justify-center rounded-full text-xs font-semibold tabular-nums text-white"
									:class="n.sent ? 'bg-surface-gray-6' : 'bg-surface-blue-7'"
								>{{ i + 1 }}</span>
								<div class="min-w-0 flex-1">
									<p class="flex items-baseline gap-2">
										<span class="truncate text-base font-medium text-ink-gray-8">{{ n.component || n.element.split(/[.\s]/)[0] }}</span>
										<span v-if="n.sent" class="shrink-0 text-sm text-ink-gray-5">Sent</span>
									</p>
									<p class="line-clamp-2 text-base text-ink-gray-6">{{ n.note }}</p>
								</div>
								<span class="hidden shrink-0 items-start group-hover:flex group-focus-within:flex">
									<Button variant="ghost" icon="lucide-pencil" aria-label="Edit note" @click.stop="edit(n)" />
									<Button variant="ghost" icon="lucide-trash-2" aria-label="Delete note" @click.stop="removeNote(n.id)" />
								</span>
							</div>
						</template>
					</template>

					<!-- Tweaks -->
					<template v-else>
						<template v-for="[r, list] in tweakGroups" :key="r">
							<p class="flex items-baseline gap-1.5 px-2 pt-2 pb-1 text-sm text-ink-gray-5">
								{{ list[0].page }}
								<span class="tabular-nums text-ink-gray-4">{{ list.length }}</span>
							</p>
							<div
								v-for="t in list"
								:key="t.id"
								data-annotate-ui
								role="button"
								tabindex="0"
								class="group flex cursor-pointer gap-2 rounded-lg px-2 py-1.5 transition-colors duration-100 hover:bg-surface-gray-2"
								@mouseenter="tweakApi?.highlight(t.id)"
								@mouseleave="tweakApi?.highlight(null)"
								@click="revealTweak(t.id)"
								@keydown.enter.self="revealTweak(t.id)"
							>
								<div class="min-w-0 flex-1">
									<p class="flex items-center gap-2">
										<span class="min-w-0 truncate text-base font-medium text-ink-gray-8">{{ t.title }}</span>
										<Badge v-if="t.badge" class="shrink-0" theme="gray" variant="subtle" size="sm" :label="t.badge" />
									</p>
									<p v-if="t.changes.length" class="mt-0.5 flex flex-wrap items-center gap-2 text-p-sm text-ink-gray-6">
										<span v-for="(c, ci) in t.changes" :key="ci" class="inline-flex items-center gap-1">
											<span v-if="c.icon" class="size-3.5 shrink-0 text-ink-gray-5" :class="c.icon" aria-hidden="true" />
											<span v-else-if="c.swatch?.kind === 'ink'" class="size-2.5 shrink-0 rounded-full bg-current" :class="c.swatch.cls" aria-hidden="true" />
											<span v-else-if="c.swatch?.kind === 'bg'" class="size-2.5 shrink-0 rounded-full border border-outline-gray-2" :class="c.swatch.cls" aria-hidden="true" />
											<span v-else-if="c.swatch" class="size-2.5 shrink-0 rounded-full border-2 border-solid" :class="c.swatch.cls" aria-hidden="true" />
											{{ c.text }}
										</span>
									</p>
								</div>
								<span class="hidden shrink-0 items-start group-hover:flex group-focus-within:flex">
									<Tooltip text="Revert" :hover-delay="600">
										<Button variant="ghost" icon="lucide-x" aria-label="Revert tweak" @click.stop="tweakApi?.remove(t.id)" />
									</Tooltip>
								</span>
							</div>
						</template>
					</template>
				</div>

				<div class="flex items-center gap-1.5 border-t border-outline-gray-1 p-1.5">
					<!-- Where this list stands on the server. A failed save is retried on the next change. -->
					<span
						class="flex items-center gap-1 px-1 text-p-sm"
						:class="saveState === 'error' ? 'text-ink-red-3' : 'text-ink-gray-5'"
						role="status"
					>
						<span
							class="size-3.5 shrink-0"
							:class="saveState === 'saved' ? 'lucide-check' : saveState === 'error' ? 'lucide-triangle-alert' : 'lucide-loader-circle animate-spin motion-reduce:animate-none'"
							aria-hidden="true"
						/>
						{{ saveState === 'saved' ? 'Saved' : saveState === 'error' ? 'Not saved' : 'Saving…' }}
					</span>
					<Button v-if="mode === 'comment' && hasSent" variant="ghost" label="Clear sent" @click="clearSent" />
					<Button
						class="ml-auto"
						:variant="confirming ? 'subtle' : 'ghost'"
						:theme="confirming ? 'red' : 'gray'"
						:label="confirming ? (mode === 'tweak' ? `Reset ${plural(count, 'tweak')}` : `Clear ${plural(count, 'note')}`) : mode === 'tweak' ? 'Reset all' : 'Clear all'"
						@click="clear"
					/>
				</div>
			</div>
		</Transition>

		<Transition
			appear
			enter-from-class="opacity-0 translate-y-2 motion-reduce:translate-y-0"
			enter-active-class="transition duration-[180ms] ease-out motion-reduce:transition-opacity"
		>
			<div
				ref="bar"
				data-annotate-ui
				role="toolbar"
				aria-label="Annotate"
				class="pointer-events-auto fixed z-[60] flex touch-none items-center gap-1.5 rounded-5 border border-outline-gray-2 bg-surface-elevation-2 p-1.5 shadow-lg"
				:class="[barDragging ? 'cursor-grabbing' : 'cursor-grab', ready ? '' : 'opacity-0', snapping && 'transition-[left,top] duration-150 ease-out motion-reduce:transition-none']"
				:style="{ left: `${pos.left}px`, top: `${pos.top}px` }"
				@pointerdown="barDown"
				@pointermove="barMove"
				@pointerup="barUp"
				@pointercancel="barUp"
				@click.capture="barClick"
			>
				<!-- Tool switch. The current tab stays lit; Escape or close is the way off. -->
				<Tooltip :text="tabTip" :hover-delay="600">
					<div class="inline-flex" @pointerover="onTabHover">
						<TabButtons :options="tabOptions" :model-value="mode" />
					</div>
				</Tooltip>

				<span v-if="count" data-notes-trigger>
					<Tooltip :text="mode === 'tweak' ? 'Show tweaks' : 'Show notes'" :hover-delay="600">
						<Button :variant="listOpen ? 'subtle' : 'ghost'" :label="countLabel" @click="listOpen = !listOpen" />
					</Tooltip>
				</span>

				<Tooltip v-if="!count" :text="`No ${noun}s yet`" :hover-delay="600">
					<span class="inline-flex" tabindex="0">
						<Button variant="ghost" icon-left="lucide-copy" label="Copy prompt" disabled />
					</span>
				</Tooltip>
				<Tooltip v-else text="Copy prompt for Claude" :hover-delay="600">
					<Button variant="ghost" icon-left="lucide-copy" label="Copy prompt" @click="copy" />
				</Tooltip>

				<Tooltip text="Hide toolbar" :hover-delay="600">
					<Button variant="ghost" icon="lucide-x" aria-label="Close toolbar" @click="setEnabled(false)" />
				</Tooltip>
			</div>
		</Transition>
	</template>
</template>
