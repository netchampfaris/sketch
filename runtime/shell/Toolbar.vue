<script setup lang="ts">
// The annotate toolbar on the live page, drawn by the Viewer shell over the Prototype's frame. A faint trigger sits in a corner; it opens the toolbar. Note is the owner's
// (or an invited editor's own) instructions for their agent; Comment is a conversation with people. A signed-in
// reader sees Comment only; a Guest sees "Sign in to comment".
//
// The page and its elements live in the frame, so picking does too (runtime/agent/pick.ts): while a tool
// picks, the frame swallows the pointer and reports hovers and picks; the shell draws the outlines, pins and
// boxes from the rects it reports (frame.ts). Words and people never go to the frame, and nothing the frame
// says can save anything: notes and comments are written from the shell's own buttons and keys (here, and
// the canvas's Ask agent in CanvasLayer.vue).
//
// Tweak draws here too (TweakLayer.vue): the frame picks and writes, the shell holds the tweaks, their list and the prompt.
// Over the frame's canvas this is the canvas's toolbar, as in the frame: its tiles take the pins (CanvasLayer.vue draws
// them), a click on a tile comes from the frame as a `tile:pick`, and the panel's Comments and Notes tabs are drawn
// from here.
import { computed, defineComponent, h, markRaw, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { useElementSize, useEventListener, useWindowSize } from '@vueuse/core'
import { Badge, BottomSheet, Button, TabButtons, Tooltip, providePortalTarget, toast } from 'frappe-ui'
import {
	ANCHORS,
	active,
	addNote,
	buildPrompt,
	clearNotes,
	clearSent,
	copyText,
	enabled,
	markSent,
	mode,
	noteNumber,
	notes,
	readAnchor,
	removeNote,
	setEnabled,
	storedAnchor,
	updateNote,
	writeAnchor,
	type Anchor,
	type Note,
} from './annotate'
import { clamp, typing } from '../shared/dom'
import type { Mode } from '../shared/protocol'
import { heldDrafts, load, openCount, openThread, read, spotOfThread, startListening, status, stopListening, threadById, type Anchor as PinAnchor, type Thread } from './comments'
import { host, isGuest } from './host'
import CanvasComments from './CanvasComments.vue'
import CanvasNotes from './CanvasNotes.vue'
import CommentPopover from './CommentPopover.vue'
import CommentsPanel from './CommentsPanel.vue'
import NotePopover from './NotePopover.vue'
import TilePins from './TilePins.vue'
import { canvasUi, handlers, tileAnchor } from './tiles'
import { tileExists, tileLabel, whereOf, type TileHit, type TileSpot } from '../shared/tiles'
import type { BoxInfo, ComponentInfo, ElInfo, Pick, Rect, Redline } from '../shared/protocol'
import type { DemoPick } from '../shared/picks'
import CommentPins from './CommentPins.vue'
import NotePins from './NotePins.vue'
import TweakLayer from './TweakLayer.vue'
import { buildTweakPrompt, findRow, highlight, inspect, removeTweak, resetAll, routeOfRow, tweakCount, tweakItems } from './tweaks'
import { labels, onFrame, onRefsGone, page, post, rects, resolveRect, resolveRects, track, type Target } from './frame'
import { demo } from './demo'
import { pinHover } from './pinHover'
import { saveState } from './notes'
import { applyPicks, canvas, picksShown, pointOf, revealTile, showView } from './canvas'
import { hasUnreadThreads } from './badges'

const props = defineProps<{ noter: boolean }>()

const key = computed(() => page.key)
const { width: vw, height: vh } = useWindowSize()
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

const noter = props.noter
const guest = isGuest()
// Readers have one tool; a Guest has none, only the way to sign in.
if (!noter) mode.value = 'comment'
if (guest) setEnabled(true)
// Phone only: the comments list as a bottom sheet.
const sheetOpen = ref(false)
// The canvas is open over the page: its tiles take the pins, and its panel (or on a phone the sheet) takes the list.
const canvasOpen = computed(() => canvas.open)
const sheetMode = computed(() => (canvasOpen.value ? canvas.phone : vw.value < 640))
// Our tooltips and sheet open in a plain host inside ours, so they keep their own z-index.
const menuHost = ref<HTMLElement | null>(null)
const portalHost = ref<HTMLElement | null>(null)
providePortalTarget(() => portalHost.value ?? undefined)

// Picking (hover, box, measuring) runs in the frame for the two tools that pin things to the page.
// A phone's comments sheet covers the page, so nothing is picked while it is open. Over the canvas a click picks a
// tile instead of an element (the frame's canvas reports it), so the page behind is never picked.
const pins = computed(() => mode.value === 'note' || mode.value === 'comment')
const picking = computed(() => enabled.value && active.value && pins.value && !guest && !sheetOpen.value && !canvasOpen.value)
const tilePicking = computed(() => enabled.value && active.value && pins.value && !guest && canvasOpen.value && !sheetOpen.value)
// Tweak picks in the frame too, on the live page only (tweakPick.ts).
const tweakLive = computed(() => noter && enabled.value && active.value && mode.value === 'tweak' && !canvasOpen.value)
watch([picking, tweakLive, mode, () => page.ready], () => post('tool', { mode: mode.value, active: picking.value || tweakLive.value }), { immediate: true })
watch(
	[tilePicking, mode, () => page.ready],
	() => {
		canvas.tool = tilePicking.value ? (mode.value === 'note' ? 'note' : 'comment') : ''
		post('canvas:tool', { tool: canvas.tool })
	},
	{ immediate: true },
)

// ---- Popover ---------------------------------------------------------------------------
// One element of the box: its ref while the frame knows it, its selector after; what it was when picked.
type El = { sel: string; ref?: string; info?: ElInfo }
type Draft = {
	x: number
	y: number
	els: El[] // the first one is the note's element (a box note's container)
	comp?: ComponentInfo
	// The first element's box when it was picked, until the frame reports it again.
	rect?: Rect
	picks?: DemoPick[]
	box?: BoxInfo
	// A note made from a thread ("Add to notes"): the thread's own anchor, kept as it is.
	anchor?: PinAnchor
	// The note or thread the box is open on; none for a new one.
	editing?: Editing
	// A click on a canvas tile: which tile, and where on it.
	tile?: TileHit
	component: string
	extra: number
}
type Editing = { kind: 'note'; id: string } | { kind: 'thread'; id: string }
const draft = shallowRef<Draft | null>(null)
const draftKey = ref(0)
const text = ref('')

// The elements the frame keeps measuring for the box: its selection (outlines), and the element its pin rides on. On the
// canvas the pin rides on a tile (`spot`), whose place the shell works out from the canvas's pan and zoom.
type Point = { x: number; y: number }
type Follow = Target & { fx: number; fy: number; spot?: TileSpot }
const follow = shallowRef<Follow | null>(null)
let nudge: Point | null = null
let pendingAt: Point | null = null
onBeforeUnmount(
	track(() => {
		const out: Record<string, Target> = {}
		draft.value?.els.forEach((e, i) => (out[`sel-${i}`] = { sel: e.sel, ref: e.ref }))
		if (follow.value && !follow.value.spot) out.box = { sel: follow.value.sel, ref: follow.value.ref }
		if (flash.value) out.flash = flash.value
		return out
	}),
)
// The selection, for Alt's distances in the frame.
watch(draft, (d, was) => {
	// The box closed: the outline under a still pointer waits for it to move, here and in the frame.
	if (!d && was) frameHover.value = { ...frameHover.value, rect: null, label: '', lines: [] }
	post('selection', { refs: (d?.els ?? []).map((e) => e.ref).filter((r): r is string => !!r), ...(d?.box ? { box: d.box } : {}), ...(!d && was ? { drop: true } : {}) })
})

// The comment box rides with its pin: where the frame says the pin's element is now. A pin that fans out of a pile keeps
// its offset from that point.
const at = computed<Point | null>(() => {
	const f = follow.value
	if (!f || !draft.value) return null
	const r = f.spot ? null : rects.box
	const p = f.spot ? pointOf(f.spot, f) : r && { x: r.x + f.fx * r.w, y: r.y + f.fy * r.h }
	if (!p) return null
	if (pendingAt) {
		nudge = { x: pendingAt.x - p.x, y: pendingAt.y - p.y }
		pendingAt = null
	}
	return { x: p.x + (nudge?.x ?? 0), y: p.y + (nudge?.y ?? 0) }
})
function followPin(f: Follow | null, x: number, y: number) {
	delete rects.box
	follow.value = f
	nudge = null
	pendingAt = f ? { x, y } : null
}
watch(draft, (d) => !d && (follow.value = null))
// What a pin rides on: its tile on the canvas, else its element.
const followOf = (a: PinAnchor): Follow =>
	a.tile ? { sel: '', spot: { route: a.route, tile: a.tile }, fx: a.offset.x, fy: a.offset.y } : { sel: a.selector, fx: a.offset.x, fy: a.offset.y }

// Closing a new comment that has words keeps it as a Draft pin on the page (`heldDrafts`), whatever closed it: a click
// outside, Escape, another tool. An empty one just goes. `as` is the tool the box was opened in, for a tool change.
function close(as: Mode = mode.value) {
	const d = draft.value
	const words = text.value
	const anchor = newAnchor.value
	if (d && as === 'comment' && !d.editing && words.trim() && anchor) {
		heldDrafts.value = [...heldDrafts.value, { id: `draft-${Date.now()}`, anchor, text: words, state: d }]
		text.value = ''
	}
	draft.value = null
}
// A Draft pin reopens its box where the pin is now, with the words as they were.
function reopenDraft(id: string, x: number, y: number) {
	const h = heldDrafts.value.find((d) => d.id === id)
	if (!h) return
	close()
	heldDrafts.value = heldDrafts.value.filter((d) => d.id !== id)
	const a = h.anchor
	draft.value = { ...(h.state as Draft), x, y }
	text.value = h.text
	draftKey.value++
	followPin(followOf(a), x, y)
}
// A new note may be re-aimed while nothing is typed; an edit never is.
const canRetarget = () => !draft.value || (!draft.value.editing && !text.value.trim())

const elOf = (p: Pick): El => ({ sel: p.el.selector, ref: p.ref, info: p.el })
// `first` is the pick of the first element: what the box names and where it is.
function show(els: El[], x: number, y: number, first: Pick, box?: BoxInfo) {
	const fresh = !draft.value
	draft.value = { x, y, els, comp: first.component, rect: first.rect, picks: first.picks, box, component: first.label, extra: els.length - 1 }
	if (fresh) {
		text.value = ''
		draftKey.value++
	}
	const r = first.rect
	followPin({ sel: first.el.selector, ref: first.ref, fx: r.w ? (x - r.x) / r.w : 0, fy: r.h ? (y - r.y) / r.h : 0 }, x, y)
}
// What a draft's first element was picked as, when it is opened again from its parts.
const firstOf = (d: Draft): Pick | null =>
	d.els[0]?.info && d.comp && d.rect
		? { kind: 'click', ref: d.els[0].ref ?? '', el: d.els[0].info, label: d.component, component: d.comp, rect: d.rect, x: d.x, y: d.y, shift: false, keyboard: false, picks: d.picks ?? [] }
		: null

const noteRefs = new Map<string, string[]>()
const notesOn = (n: Note): El[] => [n.selector, ...(n.extras ?? []).map((e) => e.selector)].map((sel, i) => ({ sel, ref: noteRefs.get(n.id)?.[i] }))

function openEdit(n: Note, x: number, y: number) {
	text.value = n.note
	draft.value = { x, y, els: notesOn(n), box: n.box, editing: { kind: 'note', id: n.id }, component: n.component || n.element.split(/[.\s]/)[0], extra: n.extras?.length ?? 0 }
	draftKey.value++
}

// Where a new note or comment sits: the picked elements, and the point clicked within the first.
function anchorOf(d: Draft): PinAnchor {
	const r = rects['sel-0'] ?? d.rect!
	const c = d.comp!
	const [info, ...rest] = d.els.map((e) => e.info!)
	return {
		route: key.value,
		viewport: `${window.innerWidth}x${window.innerHeight}`,
		selector: info.selector,
		component: c.component,
		componentChain: c.chain,
		file: c.file || undefined,
		element: info.element,
		text: info.text,
		state: info.state || undefined,
		extras: rest.length ? rest : undefined,
		box: d.box,
		offset: {
			x: r.w ? clamp((d.x - r.x) / r.w, 0, 1) : 0,
			y: r.h ? clamp((d.y - r.y) / r.h, 0, 1) : 0,
		},
		rect: { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.w), h: Math.round(r.h) },
	}
}

function save() {
	const d = draft.value
	const t = text.value.trim()
	if (!d || !t) return
	if (d.editing) {
		if (d.editing.kind === 'note') updateNote(d.editing.id, t)
	} else if (d.anchor) {
		const { picks, ...where } = d.anchor
		addNote({ ...where, note: t })
	} else if (d.tile) addNote({ ...tileAnchor(d.tile, d.tile), note: t })
	else {
		addNote({ ...anchorOf(d), note: t })
		// The pins of a note made this visit follow the very elements it was made on, as long as they live.
		const n = notes.value[notes.value.length - 1]
		noteRefs.set(n.id, d.els.map((e) => e.ref ?? ''))
	}
	close()
}

// ---- Picks from the frame ---------------------------------------------------------------
onBeforeUnmount(
	onFrame('pick', (p) => {
		if (!picking.value) return
		listOpen.value = false
		const d = draft.value
		if (p.kind === 'box') return void (canRetarget() && show([elOf(p)], p.x, p.y, p, p.box))
		if (p.kind === 'step') {
			if (!d || d.editing || d.box) return
			return show([elOf(p), ...d.els.slice(1).filter((e) => e.ref !== p.ref)], p.x, p.y, p)
		}
		// A comment box open: the first click outside it only closes it. Shift-click still adds to a new comment's elements.
		if (d && mode.value === 'comment' && !(p.shift && !d.editing && !d.box)) return close()
		if (!d) return show([elOf(p)], p.x, p.y, p)
		if (d.editing) return
		if (p.shift && !d.box) {
			// Shift adds or removes; the last element can't be removed.
			const first = firstOf(d)
			if (!first) return
			if (!d.els.some((e) => e.ref === p.ref)) show([...d.els, elOf(p)], d.x, d.y, first)
			else if (d.els.length > 1) {
				const els = d.els.filter((e) => e.ref !== p.ref)
				show(els, d.x, d.y, els[0].ref === first.ref ? first : p)
			}
			return
		}
		if (canRetarget()) show([elOf(p)], p.x, p.y, p)
	}),
)

// A click on a canvas tile opens the same box a click on an element does, with the tile as its anchor.
function onTilePick(hit: TileHit) {
	const d = draft.value
	// A comment box open: the first click outside it only closes it.
	if (d && mode.value === 'comment') return close()
	if (d && (d.editing || text.value.trim())) return
	const fresh = !d
	draft.value = { x: hit.x, y: hit.y, els: [], tile: hit, component: tileLabel(hit.tile), extra: 0 }
	if (fresh) {
		text.value = ''
		draftKey.value++
	}
	followPin({ sel: '', spot: { route: hit.route, tile: hit.tile }, fx: hit.fx, fy: hit.fy }, hit.x, hit.y)
}
onBeforeUnmount(
	onFrame('tile:pick', (p) => {
		if (!tilePicking.value) return
		const clamp01 = (n: number) => clamp(n, 0, 1)
		onTilePick({ ...p.spot, fx: clamp01(p.fx), fy: clamp01(p.fy), x: p.x, y: p.y })
	}),
)
// A click on the canvas off every tile: a click outside the comment box, which closes it.
onBeforeUnmount(onFrame('canvas:click', () => draft.value && mode.value === 'comment' && close()))

// ---- Comments: the thread open beside its pin ---------------------------------------------
const thread = computed(() => {
	const e = draft.value?.editing
	return e?.kind === 'thread' ? threadById(e.id) : undefined
})
const newAnchor = computed(() => {
	const d = draft.value
	if (!d || d.editing) return undefined
	if (d.tile) return tileAnchor(d.tile, d.tile)
	if (!d.comp) return undefined
	// On the live page the thread also keeps what the Demo showed, so it can be put back that way.
	return d.picks?.length ? { ...anchorOf(d), picks: d.picks } : anchorOf(d)
})

const until = async (ok: () => boolean | Promise<boolean>, ms = 4000) => {
	for (const t0 = Date.now(); !(await ok()); await sleep(50)) if (Date.now() - t0 > ms || unmounted) return false
	return true
}

function openThreadAt(t: Thread, x: number, y: number) {
	if (!picksShown(t.anchor.picks)) return void showPicksThen(t, x, y)
	openThreadNow(t, x, y)
}
// A thread made on other options than the Demo shows: put the Demo on them first, then open it where its element now is.
async function showPicksThen(t: Thread, x: number, y: number) {
	const p = t.anchor.picks
	applyPicks(p)
	let r: Rect | null = null
	await until(async () => picksShown(p) && !!(r = await resolveRect(t.anchor.selector)), 1500)
	const a = t.anchor
	if (unmounted) return
	const box = r as Rect | null
	openThreadNow(t, box ? box.x + a.offset.x * box.w : x, box ? box.y + a.offset.y * box.h : y)
}
function openThreadNow(t: Thread, x: number, y: number) {
	const a = t.anchor
	const els = [a.selector, ...(a.extras ?? []).map((e) => e.selector)].map((sel) => ({ sel }))
	draft.value = { x, y, els, box: a.box, editing: { kind: 'thread', id: t.id }, component: a.component || a.element.split(/[.\s]/)[0], extra: a.extras?.length ?? 0 }
	draftKey.value++
	followPin(followOf(a), x, y)
}
// A thread you made keeps its popover: it turns from the composer into the thread in place.
function onCreated(t: Thread) {
	const d = draft.value
	if (d) draft.value = { ...d, editing: { kind: 'thread', id: t.id }, comp: undefined }
	text.value = ''
}
// The owner's "Add to notes": the Note tool opens on the thread's words, in the same place. Nothing is saved until
// the owner saves the note.
async function onNoteDraft(d: { note: string; anchor: PinAnchor }) {
	const was = draft.value
	if (!was) return
	use('note')
	// Changing tool closes the open box; the new one opens once that has happened.
	await nextTick()
	text.value = d.note
	// The box's header names the thread's place, as every other note's does: its tile on the canvas, else its element.
	const a = d.anchor
	const place = a.tile ? tileLabel(a.tile) : a.component || a.element.split(/[.\s]/)[0]
	draft.value = { ...was, editing: undefined, anchor: a, component: place || was.component }
	draftKey.value++
}
// The thread is gone (deleted here, or by its author or the owner in another tab).
watch(thread, (t, was) => {
	if (was && !t && draft.value?.editing?.kind === 'thread' && draft.value.editing.id === was.id) close()
})
// A new comment or note on a tile has no pin yet: the canvas layer draws a draft one where the tile was clicked.
watch(
	draft,
	(d) => {
		const t = d && !d.editing ? d.tile : undefined
		canvasUi.draft = t ? { spot: { route: t.route, tile: t.tile }, fx: t.fx, fy: t.fy } : null
	},
	{ immediate: true },
)
watch(
	() => {
		const e = draft.value?.editing
		return e && `${e.kind}:${e.id}`
	},
	() => {
		const e = draft.value?.editing
		canvasUi.noteId = e?.kind === 'note' ? e.id : ''
		openThread.value = e?.kind === 'thread' ? e.id : null
		// Opening a thread is reading it.
		if (e?.kind === 'thread') read(e.id)
	},
)

// The page a list row points at: its route first, then a moment for the page to render it.
async function goTo(route: string) {
	if (key.value === route) return
	post('nav', { path: route })
	await until(() => key.value === route, 2000)
}
// ---- The canvas: reaching a tile's thread or note from a list, from the live page or the canvas
// A thread or note opened from the canvas's list lives on the live page, so the toolbar stays open for it.
let stayOpen = false
async function leaveCanvas() {
	if (!canvasOpen.value) return
	stayOpen = true
	post('canvas:close', {})
	await until(() => !canvas.open)
}
// Show something pinned to a tile: open the canvas if it is not, bring the tile into view, then open the box at
// its pin. A tile that has gone has no pin to open at (its row sits under "Removed from canvas"), so the box opens beside
// the row instead, and the thread can still be read and resolved.
async function openOnCanvas(spot: TileSpot, at: { x: number; y: number }, show: (x: number, y: number) => void, row?: HTMLElement) {
	if (!canvasOpen.value) {
		showView(spot.tile.view || `page:${spot.route}`)
		if (!(await until(() => canvas.open && !!canvas.model))) return
	}
	const point = tileExists(canvas.model, spot) === false ? null : await revealTile(spot, { fx: at.x, fy: at.y })
	if (unmounted) return
	if (point) return show(point.x, point.y)
	const r = row?.getBoundingClientRect()
	show(r ? r.left : vw.value / 2, r ? r.top + r.height / 2 : vh.value / 2)
}
// Reaching a thread from the list: its page first, then the pin, then the thread. On a tile: the canvas, then the tile.
async function openFromList(t: Thread, row?: HTMLElement) {
	sheetOpen.value = false
	const a = t.anchor
	const spot = spotOfThread(t)
	if (spot) return openOnCanvas(spot, a.offset, (x, y) => openThreadAt(t, x, y), row)
	await leaveCanvas()
	await goTo(a.route)
	// Made on other options than the Demo shows: show those first, so its element is on the page to be found.
	if (!picksShown(a.picks)) {
		applyPicks(a.picks)
		await sleep(50)
	}
	const found = await until(async () => !!(await resolveRect(a.selector)), 1500)
	if (found) post('scrollTo', { selector: a.selector, smooth: true })
	await sleep(found ? 250 : 0)
	const r = found ? await resolveRect(a.selector) : null
	openThreadAt(t, r ? r.x + a.offset.x * r.w : a.rect.x + a.offset.x * a.rect.w, r ? r.y + a.offset.y * r.h : a.rect.y + a.offset.y * a.rect.h)
}

// A link from the gallery ("Arohi mentioned you") opens the prototype on that thread: `?comment=<id>`. The link is
// used once, so a reload does not open it again.
async function openLinked() {
	const url = new URL(location.href)
	const id = url.searchParams.get('comment')
	if (!id || guest) return
	url.searchParams.delete('comment')
	history.replaceState(history.state, '', url.pathname + url.search + url.hash)
	if (!enabled.value) setEnabled(true)
	use('comment')
	if ((await until(() => page.ready, 8000)) && (await until(() => !!threadById(id), 8000))) await openFromList(threadById(id)!)
}
onMounted(openLinked)

// Back from signing in (signIn below): Comment mode opens again, where the visitor was. The link is used once.
function openCommenting() {
	const url = new URL(location.href)
	if (url.searchParams.get('commenting') !== '1') return
	url.searchParams.delete('commenting')
	history.replaceState(history.state, '', url.pathname + url.search + url.hash)
	if (guest) return
	setEnabled(true)
	use('comment')
}
onMounted(openCommenting)

// The canvas layer draws the pins and the panel's extra tabs from components registered here. The pins call back into
// `handlers`; the tabs are the lists with this toolbar's actions wired in.
const commentsTab = markRaw(defineComponent({ setup: () => () => h(CanvasComments, { route: key.value, onChoose: openFromList }) }))
const notesTab = markRaw(defineComponent({ setup: () => () => h(CanvasNotes, { selected: canvasUi.noteId, onChoose: openNoteFromList }) }))
canvas.canComment = !guest
canvas.canNote = noter
canvas.Pins = markRaw(TilePins)
canvas.tabs = guest ? {} : { comments: commentsTab, ...(noter ? { notes: notesTab } : {}) }
handlers.thread = openThreadAt
handlers.note = openEdit
handlers.draft = reopenDraft
onBeforeUnmount(() => {
	Object.assign(canvas, { canComment: false, canNote: false, tool: '', Pins: null, tabs: {}, tab: 'browse' })
	handlers.thread = handlers.note = handlers.draft = null
})
// The canvas reads the threads as it opens, and its tab shows no count until it knows both the threads and the tiles:
// the server's number cannot know which tiles have gone, and a count that changes when the tab opens is wrong at first.
watch(canvasOpen, (open) => open && !guest && void load(true), { immediate: true })
const tabCount = computed(() => (canvasOpen.value && (status.value !== 'ready' || !canvas.model) ? 0 : openCount.value))
watch([tabCount, () => notes.value.length], ([c, n]) => (canvas.counts = { comments: c, notes: n }), { immediate: true })

// A note from a list: on a tile, bring the tile into view; on the page, leave the canvas first.
async function openNoteFromList(n: Note, row?: HTMLElement) {
	if (n.tile) return openOnCanvas({ route: n.route, tile: n.tile }, n.offset, (x, y) => openEdit(n, x, y), row)
	await leaveCanvas()
	await edit(n)
}

function remove() {
	const e = draft.value?.editing
	if (e?.kind === 'note') removeNote(e.id)
	close()
}

// Parent and child (the \ and Enter keys) swap the first element; any shift-clicked extras stay. The frame answers
// with a `step` pick.
function step(dir: 'parent' | 'child') {
	const d = draft.value
	const ref = d?.els[0]?.ref
	if (!d || d.editing || d.box || !ref) return
	post('step', { dir, ref })
}

// ---- Outlines, box and redlines, from the frame's rects ----------------------------------
type Out = { key: string; x: number; y: number; w: number; h: number; dashed?: boolean }
const frameHover = shallowRef<{ rect: Rect | null; label: string; lines: Redline[]; alt: boolean; shift: boolean }>({ rect: null, label: '', lines: [], alt: false, shift: false })
onBeforeUnmount(onFrame('hover', (h) => (frameHover.value = h)))
const dragRect = ref<Rect | null>(null)
onBeforeUnmount(onFrame('drag', (d) => (dragRect.value = d.rect)))
// Alt or Shift held, in the frame (the pointer is there) or here (the focus is).
const keys = ref({ alt: false, shift: false })
const alt = computed(() => frameHover.value.alt || keys.value.alt)
const shift = computed(() => frameHover.value.shift || keys.value.shift)
// Shift held while the pointer moves means picking more elements (not typing a capital): the note box steps aside
// until Shift is released.
const shiftPick = computed(() => frameHover.value.shift && !!draft.value && !draft.value.editing && !draft.value.box)
// Outlined for a second after a jump from the notes list.
const flash = shallowRef<Target | null>(null)
// A new frame knows none of the refs the box, its pin, the flash and this visit's notes hold: they go by selector.
onBeforeUnmount(
	onRefsGone(() => {
		noteRefs.clear()
		const d = draft.value
		if (d?.els.some((e) => e.ref)) draft.value = { ...d, els: d.els.map((e) => ({ sel: e.sel, info: e.info })) }
		if (follow.value?.ref) follow.value = { ...follow.value, ref: undefined }
		if (flash.value?.ref) flash.value = { ...flash.value, ref: undefined }
	}),
)

const fracOf = (c: Rect, f: BoxInfo): Rect => ({ x: c.x + f.fx * c.w, y: c.y + f.fy * c.h, w: f.fw * c.w, h: f.fh * c.h })
// The hover outline is one element that glides; it keeps its last box while it fades out.
const hoverBox = shallowRef<Rect | null>(null)
const hoverOn = ref(false)
const glide = ref(true)
const scrolling = ref(false)
const hoverLabel = ref('')
const outs = computed<Out[]>(() => {
	const o: Out[] = []
	const d = draft.value
	if (d) {
		const live = d.els.map((_, i) => rects[`sel-${i}`]).filter((r): r is Rect => !!r)
		if (d.box && live[0]) o.push({ key: 'draft-box', ...fracOf(live[0], d.box), dashed: true })
		else live.forEach((r, i) => o.push({ key: `sel-${i}`, ...r }))
	}
	const ph = pinHover.value
	if (ph && ph.box && rects[ph.id]) o.push({ key: 'hover-box', ...fracOf(rects[ph.id]!, ph.box), dashed: true })
	if (flash.value && rects.flash) o.push({ key: 'flash', ...rects.flash })
	return o
})
// A pin's element, or the page element under the pointer while a tool picks.
const hovered = computed<{ rect: Rect; label: string } | null>(() => {
	const ph = pinHover.value
	if (ph) return !ph.box && rects[ph.id] ? { rect: rects[ph.id]!, label: labels[ph.id] ?? '' } : null
	const h = frameHover.value
	return picking.value && h.rect ? { rect: h.rect, label: h.label } : null
})
watch(
	[hovered, draft, alt, shift, dragRect],
	() => {
		const h = hovered.value
		let on = !!h
		if (h) {
			hoverBox.value = h.rect
			hoverLabel.value = h.label
		}
		// While a note is open only the selection shows, unless Shift (add or remove) or Alt (measure) is held.
		if ((draft.value && !(shift.value || alt.value)) || dragRect.value) on = false
		if (on && !hoverOn.value) {
			// Appearing: jump to the element, then glide from the next frame on.
			glide.value = false
			requestAnimationFrame(() => (glide.value = true))
		}
		hoverOn.value = on
	},
	{ flush: 'post' },
)
// Hold Alt: the frame measures against the selection when there is one, else the hovered element against its parent.
const lines = computed(() => (picking.value && alt.value ? frameHover.value.lines : []))
// The glide is off while the page scrolls, or the outline would trail the content.
let scrollTimer = 0
watch(
	() => frameHover.value.rect,
	(r, was) => {
		if (!r || !was || r === was) return
		scrolling.value = true
		clearTimeout(scrollTimer)
		scrollTimer = window.setTimeout(() => (scrolling.value = false), 120)
	},
)

watch(
	picking,
	(on) => {
		dragRect.value = null
		keys.value = { alt: false, shift: false }
		if (!on) {
			pinHover.value = null
			close()
		}
	},
	{ immediate: true },
)
watch(enabled, (on) => {
	if (!on) {
		close()
		listOpen.value = false
	}
})
watch(mode, (_m, was) => {
	listOpen.value = false
	close(was)
})
// The panel's tab and the tool follow each other. Comment mode is the Comments tab, Note mode the Notes tab, and
// anything else Browse; picking a tab picks the tool, and Escape or the Browse tab puts the tool down.
watch(
	[canvasOpen, enabled, active, mode],
	() => {
		if (!canvasOpen.value) return
		const tab = enabled.value && active.value && !guest ? (mode.value === 'note' ? 'notes' : mode.value === 'comment' ? 'comments' : 'browse') : 'browse'
		if (canvas.tab !== tab) canvas.tab = tab
	},
	{ immediate: true },
)
watch(
	() => canvas.tab,
	(tab) => {
		if (!canvasOpen.value || guest) return
		if (tab === 'browse') {
			if (active.value && pins.value) active.value = false
		} else if (tab === 'comments' || (tab === 'notes' && noter)) {
			const m: Mode = tab === 'notes' ? 'note' : 'comment'
			if (!(enabled.value && active.value && mode.value === m)) {
				setEnabled(true)
				use(m)
			}
		}
	},
)
// The canvas has its own toolbar: this one, placed beside the panel. It is open while the canvas is (so nothing
// floats over it twice), and the page's faint trigger and close button are hidden. Leaving puts it back as it was.
// Tweaks are for the live page: the canvas has none.
let openBefore = enabled.value
watch(
	canvasOpen,
	(open) => {
		close()
		if (open) {
			openBefore = enabled.value
			setEnabled(true)
		} else if (!guest) setEnabled(stayOpen || openBefore)
		if (!open) stayOpen = false
		if (open && mode.value === 'tweak') {
			active.value = false
			mode.value = 'note'
		}
	},
	{ immediate: true },
)
// Comment mode is the only time comments are read and kept fresh.
watch(
	() => !guest && enabled.value && mode.value === 'comment',
	(on) => {
		if (on) startListening()
		else {
			stopListening()
			sheetOpen.value = false
		}
	},
	{ immediate: true },
)
onBeforeUnmount(stopListening)

let flashTimer = 0
let unmounted = false
onBeforeUnmount(() => {
	clearTimeout(flashTimer)
	clearTimeout(snapTimer)
	clearTimeout(scrollTimer)
	clearTimeout(confirmTimer)
	post('tool', { mode: mode.value, active: false })
	unmounted = true
})

// Leaving a page with a half-written note keeps it as that page's draft; coming back restores it.
type Saved = { text: string; draft: Draft }
const saved = new Map<string, Saved>()
watch(key, async (now, was) => {
	const d = draft.value
	if (d && !d.editing) {
		if (text.value.trim()) saved.set(was, { text: text.value, draft: d })
		close()
	}
	const s = saved.get(now)
	if (!s) return
	// The page needs a moment to render its elements again.
	for (let i = 0; i < 30; i++) {
		if (unmounted || key.value !== now || !enabled.value) return
		const sels = s.draft.els.map((e) => e.sel)
		const found = await resolveRects(sels)
		if (sels.every((sel) => found[sel])) {
			saved.delete(now)
			close()
			const c = found[sels[0]]!
			const p = s.draft.box ? fracOf(c, s.draft.box) : null
			const x = p ? clamp(p.x + p.w, 8, vw.value - 8) : clamp(c.x + c.w / 2, 8, vw.value - 8)
			const y = p ? clamp(p.y + p.h, 8, vh.value - 8) : clamp(c.y + c.h / 2, 8, vh.value - 8)
			const first = firstOf({ ...s.draft, rect: c })
			if (first) show(s.draft.els, x, y, first, s.draft.box)
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

// One key, from this page or from the frame (where the focus is while a person works in the page). `layer` is what
// the page had open: a page dialog takes its own Escape, and in Comment mode so does a page menu, popover or list.
type Key = { key: string; meta: boolean; ctrl: boolean; alt: boolean; repeat: boolean; layer: '' | 'dialog' | 'layer'; fromFrame: boolean }
function onKey(k: Key, prevent: () => void) {
	if (k.key === 'Escape') {
		if (!enabled.value) return
		// With the focus here the page never heard it: its open layer takes it now.
		if (!k.fromFrame && k.layer) post('escape', {})
		// Let a dialog or one of our menus take its own Escape: our menu closes first, then the box, then the tool.
		// Commenting, an open page menu, popover or list closes first too; the other tools step aside for dialogs only.
		if (k.layer === 'dialog' || document.querySelector('[role="dialog"][data-state="open"]') || ownMenuOpen() || (mode.value === 'comment' && k.layer === 'layer')) return
		if (dragRect.value) dragRect.value = null
		else if (draft.value) close()
		// The last Escape leaves the tool altogether: the tool goes off and its panel closes with it.
		else if (active.value || listOpen.value) {
			active.value = false
			listOpen.value = false
		} else return
		prevent()
		return
	}
	if (k.meta || k.ctrl || k.alt) return
	const key = k.key.toLowerCase()
	const tool: Mode | null = guest ? null : key === 'c' ? 'comment' : noter && key === 'n' ? 'note' : noter && key === 't' && !canvasOpen.value ? 'tweak' : null
	if (tool && !k.repeat) {
		if (!enabled.value) {
			setEnabled(true)
			use(tool)
		} else pick(tool)
		prevent()
	}
}
// One of our own menus is open (a comment's ⋯, the panel's ⋯).
const ownMenuOpen = () => !!document.querySelector('[role="menu"][data-state="open"]')
const layerNow = (): Key['layer'] => (page.dialogOpen ? 'dialog' : page.pageLayerOpen ? 'layer' : '')

useEventListener(document, 'keydown', (e: KeyboardEvent) => {
	keys.value = { alt: e.altKey, shift: e.shiftKey }
	if (e.isComposing) return
	if (e.key === 'Escape') {
		// The comment box's own Escape (an edit in place, the mention list) is taken before it gets here.
		if (e.defaultPrevented) return
		return onKey({ key: e.key, meta: e.metaKey, ctrl: e.ctrlKey, alt: e.altKey, repeat: e.repeat, layer: layerNow(), fromFrame: false }, () => e.preventDefault())
	}
	if (!typing(e.target)) onKey({ key: e.key, meta: e.metaKey, ctrl: e.ctrlKey, alt: e.altKey, repeat: e.repeat, layer: '', fromFrame: false }, () => e.preventDefault())
	if (e.defaultPrevented) return
	// Parent and child, only while nothing is typed. Enter on a focused button stays that button's.
	const d = draft.value
	if (!d || d.editing || d.box || text.value.trim() || e.metaKey || e.ctrlKey || e.altKey) return
	if (e.key === '\\') step('parent')
	else if (e.key === 'Enter' && !e.shiftKey && !(e.target as HTMLElement | null)?.closest?.('button')) step('child')
	else return
	e.preventDefault()
})
useEventListener(document, 'keyup', (e: KeyboardEvent) => (keys.value = { alt: e.altKey, shift: e.shiftKey }))
useEventListener(window, 'blur', () => (keys.value = { alt: false, shift: false }))
// The frame forwards Escape and the tool keys only, and never while a person types in the page.
onBeforeUnmount(
	onFrame('key', (k) =>
		onKey({ key: k.key, meta: k.mods.includes('meta'), ctrl: k.mods.includes('ctrl'), alt: k.mods.includes('alt'), repeat: false, layer: k.layer, fromFrame: true }, () => {}),
	),
)

// A click anywhere outside the comment box closes it: on the panel, the toolbar. (A click on the page is a pick, and
// the pick closes it instead of starting another.) A drag is not a click. A pin opens its own thread, and the box's
// own menus and toasts are part of it. Only the box that was open when the press began: a row that opens another
// thread keeps it open.
let pressAt: Point | null = null
let pressDraft: Draft | null = null
useEventListener(
	document,
	'pointerdown',
	(e: PointerEvent) => {
		pressAt = { x: e.clientX, y: e.clientY }
		pressDraft = draft.value
	},
	{ capture: true },
)
useEventListener(document, 'click', (e: MouseEvent) => {
	if (!draft.value || mode.value !== 'comment' || draft.value !== pressDraft) return
	if (pressAt && Math.hypot(e.clientX - pressAt.x, e.clientY - pressAt.y) > 4) return
	const t = e.target
	if (!(t instanceof Element) || !t.isConnected) return
	if (t.closest('[data-comment-popover],[data-annotate-menus],[data-annotate-pin],[data-sonner-toaster],[role="menu"],[role="dialog"]:not([data-sketch-ui])')) return
	close()
})

// ---- Toolbar position ------------------------------------------------------------------
const LIVE_INSET = 12
const anchor = ref<Anchor>(readAnchor())
// Until the toolbar has been moved once, the trigger keeps to the bottom-right corner.
const moved = ref(storedAnchor() !== null)
// On a phone, everything at the bottom edge rides above the Prototype's own bottom bar.
const navH = computed(() => page.navBottom)
// Above the Variants pill when there is one: the shell's pill publishes its height in --sketch-variants-h (DemoPill.vue).
// The faint trigger sits where the toolbar last snapped: 12px in from a corner, centred on a centre anchor.
// The canvas's panel covers the right edge: the toolbar and its trigger sit in the room left of it.
const reserve = computed(() => (canvasOpen.value ? canvas.reserve : 0))
const triggerStyle = computed(() => {
	const [v, h] = (moved.value ? anchor.value : 'bottom-right').split('-')
	const s: Record<string, string> = v === 'top' ? { top: '12px' } : { bottom: `${12 + navH.value}px` }
	// Above the Variants pill when there is one: --sketch-variants-h is its own height plus the bar's, and the -8px fallback cancels the +8px.
	if (v === 'bottom' && h === 'right') s.bottom = `calc(12px + max(var(--sketch-variants-h, -8px) + 8px, ${navH.value}px))`
	if (h === 'left') s.left = '12px'
	else if (h === 'right') s.right = `${12 + reserve.value}px`
	else s.left = 'calc(50% - 16px)'
	return s
})
const bar = ref<HTMLElement | null>(null)
const { width: bw, height: bh } = useElementSize(bar, { width: 0, height: 0 }, { box: 'border-box' })
const ready = computed(() => bw.value > 0 && bh.value > 0)

// Resizing the window re-places the toolbar: every position is derived from the anchor.
// The tabs stay under the pointer when the mode changes, and the bar stays centred: the owner's bar is always as wide as
// the widest mode's (the unseen twin below measures it up front, so even the first switch holds still). What follows the
// tabs comes and goes on the right, and Close stays at the far end.
const widest = ref(0)
const ghost = ref<HTMLElement | null>(null)
const { width: gw } = useElementSize(ghost, { width: 0, height: 0 }, { box: 'border-box' })
watch([bw, gw], ([w, g]) => (widest.value = Math.max(widest.value, w, g)))
const phone = computed(() => vw.value < 640)
watch(phone, () => (widest.value = bw.value))
// On the canvas the bar is as wide as its own widest mode (the twin below, without Close and the count), never the live page's.
const slotW = computed(() => (canvasOpen.value ? Math.max(bw.value, gw.value) : Math.max(bw.value, widest.value)))
function place(a: Anchor) {
	// On the canvas the toolbar keeps the panel's 12px from the edges.
	const INSET = canvasOpen.value ? 12 : LIVE_INSET
	const [v, h] = a.split('-')
	const room = vw.value - reserve.value
	// On the canvas the zoom pill holds the bottom-right corner; parked there, the toolbar stands left of it.
	const corner = canvasOpen.value && v === 'bottom' && h === 'right' ? canvas.corner : 0
	const left = h === 'left' ? INSET : h === 'right' ? room - slotW.value - INSET - corner : (room - slotW.value) / 2
	const top = v === 'top' ? INSET : vh.value - bh.value - INSET - navH.value
	return { left: clamp(left, 0, Math.max(0, vw.value - bw.value)), top: clamp(top, 0, Math.max(0, vh.value - bh.value)) }
}
const dragPos = ref<{ left: number; top: number } | null>(null)
const pos = computed(() => dragPos.value ?? place(anchor.value))
const barBox = computed(() => ({ left: pos.value.left, top: pos.value.top, right: pos.value.left + bw.value, bottom: pos.value.top + bh.value }))
// On a phone the open toolbar and the Demo pill both live at the bottom edge: the pill rides above the toolbar only when
// the two would sit on each other, which the pill works out from where the toolbar ends.
watch(
	[() => enabled.value && phone.value && !canvasOpen.value && anchor.value.startsWith('bottom') && !!bh.value, bh, navH, () => barBox.value.right, () => page.ready],
	([on, , , right]) => Object.assign(demo, { toolbarLift: on ? LIVE_INSET + navH.value + bh.value + 8 : 0, toolbarRight: on ? right : 0 }),
	{ immediate: true },
)

// The toolbar drags by its background. A press anywhere on it may become a drag: past 4px of
// travel it is one, and the click that ends it is swallowed so no button fires.
const snapping = ref(false)
const barDragging = ref(false)
let snapTimer = 0
// The panel opening or closing slides the toolbar to its new place.
watch(reserve, () => {
	clearTimeout(snapTimer)
	snapping.value = true
	snapTimer = window.setTimeout(() => (snapping.value = false), 200)
})
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
// A press on the toolbar keeps the focus where it was (in the page, say), so a page menu or popover that is open stays
// open and the tool keys still reach the frame. Typing into the toolbar is never needed.
const keepFocus = (e: MouseEvent) => e.preventDefault()

// Unread threads on this page (any page, on the canvas): the dot on the Comment tool and on the closed launcher, the doors
// to them. While Comment is the tool in use the rows carry their own dots.
const unread = computed(() => hasUnreadThreads(canvasOpen.value ? undefined : page.path))
const unreadDot = computed(() => unread.value && !(active.value && mode.value === 'comment'))

// ---- Toolbar actions: the count and copy belong to the tool in use ---------------------
const unsent = computed(() => notes.value.filter((n) => !n.sent))
const hasSent = computed(() => notes.value.some((n) => n.sent))
const count = computed(() => (mode.value === 'tweak' ? tweakCount.value : mode.value === 'note' ? notes.value.length : 0))
const noun = computed(() => (mode.value === 'tweak' ? 'tweak' : 'note'))
const plural = (n: number, w: string) => `${n} ${w}${n === 1 ? '' : 's'}`
const countLabel = computed(() => (mode.value === 'tweak' ? plural(tweakCount.value, 'tweak') : unsent.value.length ? plural(unsent.value.length, 'note') : 'All sent'))

// Tabs: one tooltip for the three, worded for the tab under the pointer. The Comment tab carries
// the number of threads still open.
// Under 640px the tabs are icons: the three labels would not fit. Each keeps its name for assistive tech.
// A reader's one tool toggles: pressing it again puts it down.
const tool = (m: Mode) => (noter ? use(m) : pick(m))
const tab = (label: string, value: Mode, icon: string, name = label) =>
	phone.value ? { label: name, value, icon, onClick: () => tool(value) } : { label, value, iconLeft: icon, onClick: () => tool(value) }
// With a count beside it the Comment icon is no longer a square: it sizes to its content, the tab's own padding around both,
// and its name moves to screen-reader text beside the count.
// On the canvas the panel's Comments tab carries the number, so the toolbar does not say it twice.
const shownOpen = computed(() => (canvasOpen.value ? 0 : openCount.value))
const commentTab = () =>
	phone.value && shownOpen.value
		? { label: '', name: `Comment, ${shownOpen.value} open`, value: 'comment' as Mode, iconLeft: 'lucide-message-circle', onClick: () => tool('comment') }
		: tab('Comment', 'comment', 'lucide-message-circle', shownOpen.value ? `Comment, ${shownOpen.value} open` : 'Comment')
// The canvas has no Tweak: tokens change on the live page.
const tabOptions = computed(() =>
	(noter ? [tab('Note', 'note', 'lucide-sticky-note'), tab('Tweak', 'tweak', 'lucide-paintbrush'), commentTab()] : [commentTab()]).filter((o) => !(canvasOpen.value && o.value === 'tweak')),
)
const tabHover = ref<Mode>('note')
function onTabHover(e: PointerEvent) {
	const v = (e.target as Element).closest('[data-value]')?.getAttribute('data-value')
	if (v === 'note' || v === 'comment' || v === 'tweak') tabHover.value = v
}
const TIPS: Record<Mode, string> = {
	note: 'Leave notes for your agent (N)',
	tweak: 'Try token changes live (T)',
	comment: 'Talk it through with people (C)',
}
const tabTip = computed(() => TIPS[tabHover.value])

function openFromTrigger() {
	setEnabled(true)
	use(noter ? 'note' : 'comment')
}

// The comments panel: a floating card on the right, collapsed from its own button; on a phone a bottom sheet.
const panelOpen = ref(true)
const showPanel = computed(() => enabled.value && active.value && mode.value === 'comment' && !guest)
const togglePanel = () => (sheetMode.value ? (sheetOpen.value = !sheetOpen.value) : (panelOpen.value = !panelOpen.value))
const panelShown = computed(() => (sheetMode.value ? sheetOpen.value : panelOpen.value))
// The card starts below a typical page header (its action buttons sit top right), so it never covers them and the page never moves.
// It also keeps clear of the toolbar when the toolbar is parked on the right edge.
const PANEL_TOP = 72
const panelTop = computed(() => {
	const right = anchor.value.endsWith('right')
	return Math.max(PANEL_TOP, anchor.value.startsWith('top') && right ? barBox.value.bottom + 8 : 0)
})
const panelBox = computed(() => {
	const right = anchor.value.endsWith('right')
	const bottom = anchor.value.startsWith('bottom') && right ? vh.value - barBox.value.top + 8 : 12
	return { top: `${panelTop.value}px`, '--comments-list-max': `${Math.max(120, vh.value - panelTop.value - bottom - 96)}px` }
})
// Where the card really is, so a comment box can keep off it.
const panelEl = ref<HTMLElement | null>(null)
const { width: panelW, height: panelH } = useElementSize(panelEl, { width: 288, height: 0 }, { box: 'border-box' })
// On the canvas the card is the canvas's own panel, which takes `reserve` from the right edge.
const panelRect = computed(() =>
	canvasOpen.value
		? reserve.value && !sheetMode.value
			? { left: vw.value - reserve.value, right: vw.value, top: 0, bottom: vh.value }
			: null
		: showPanel.value && !phone.value && panelOpen.value && panelH.value
			? { left: vw.value - 12 - panelW.value, right: vw.value - 12, top: panelTop.value, bottom: panelTop.value + panelH.value }
			: null,
)

// Notes: copies what hasn't gone out yet, or everything when it all has; then marks it sent.
async function copy() {
	if (mode.value === 'tweak') {
		const n = tweakCount.value
		if (!n) return
		if (!(await copyText(buildTweakPrompt()))) return toast.error('Could not copy to the clipboard')
		return toast.success(`Copied ${plural(n, 'tweak')}`)
	}
	const list = unsent.value.length ? unsent.value : notes.value
	if (!list.length) return
	const ok = await copyText(buildPrompt(list))
	if (!ok) return toast.error('Could not copy to the clipboard')
	markSent(list.map((n) => n.id))
	toast.success(`Copied ${plural(list.length, 'note')}`)
}

// Clearing asks in place: the first click turns the button into "Clear 3 notes" (or "Reset 3 tweaks"), a second click
// within 3s does it.
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
	if (mode.value === 'tweak') resetAll()
	else {
		clearNotes()
		noteRefs.clear()
		close()
	}
}
watch([mode, enabled], () => (confirming.value = false))

// ---- The notes list --------------------------------------------------------------------
const listOpen = ref(false)
// A note on a tile is listed under the tile, in words; the others under their page.
const groups = computed(() => {
	const m = new Map<string, Note[]>()
	for (const n of notes.value) {
		const k = n.tile ? whereOf({ route: n.route, tile: n.tile }) : n.route
		m.set(k, [...(m.get(k) ?? []), n])
	}
	return [...m]
})
const tweakGroups = computed(() => {
	const m = new Map<string, typeof tweakItems.value>()
	for (const t of tweakItems.value) m.set(t.route, [...(m.get(t.route) ?? []), t])
	return [...m]
})
// The list has nothing left to show at zero, and a hovered tweak row must not leave its highlight behind.
watch(count, (n) => !n && (listOpen.value = false))
watch(listOpen, (on) => {
	if (!on) {
		confirming.value = false
		highlight(null)
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

// Outside click closes it. A press in the page while a tool picks comes as a pick, which closes it too.
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

// A note on another page needs its route first, then a moment for the page to render. Its element's box, or null.
async function reveal(n: Note, smooth: boolean): Promise<Rect | null> {
	await leaveCanvas()
	await goTo(n.route)
	for (let i = 0; i < 30 && !unmounted; i++) {
		if (await resolveRect(n.selector)) {
			post('scrollTo', { selector: n.selector, smooth })
			await sleep(smooth ? 0 : 50)
			return resolveRect(n.selector)
		}
		await sleep(50)
	}
	return null
}

async function jump(n: Note) {
	if (n.tile) return openNoteFromList(n)
	if (!(await reveal(n, true))) return
	flash.value = { sel: n.selector, ref: noteRefs.get(n.id)?.[0] }
	clearTimeout(flashTimer)
	flashTimer = window.setTimeout(() => (flash.value = null), 1000)
}

async function edit(n: Note) {
	listOpen.value = false
	if (n.tile) return openNoteFromList(n)
	const r = await reveal(n, false)
	const p = r ? { x: r.x + n.offset.x * r.w, y: r.y + n.offset.y * r.h } : { x: n.rect.x + n.offset.x * n.rect.w, y: n.rect.y + n.offset.y * n.rect.h }
	openEdit(n, p.x, p.y)
}

// A Guest: the server remembers where they were, then shows the login.
function signIn() {
	// The hash is the page the visitor was on; `commenting` opens Comment mode again when they return.
	const here = new URL(location.href)
	here.searchParams.set('commenting', '1')
	const back = here.pathname + here.search + location.hash
	location.assign(`/api/method/sketch.api.sign_in_to_comment?back=${encodeURIComponent(back)}`)
}

// A tweak row: its page, its elements (opening the popover they live in), then Tweak on with them selected.
async function revealTweak(id: string) {
	listOpen.value = false
	const route = routeOfRow(id)
	if (!route) return
	await goTo(route)
	if (!(await findRow(id)) || unmounted) return
	setEnabled(true)
	use('tweak')
	// Tweak turning on clears the frame's selection: select once the frame has heard it.
	await nextTick()
	inspect('select')
}

const noteSelected = computed(() => (draft.value?.editing?.kind === 'note' ? draft.value.editing.id : undefined))
</script>

<template>
	<div ref="portalHost" />
	<!-- The faint way in. Stays mounted so it can fade out as the toolbar fades in at the same spot. -->
	<Tooltip v-if="!guest && !canvasOpen" :text="tweakCount ? `Annotate (N), ${plural(tweakCount, 'tweak')} applied` : noter ? 'Annotate (N)' : 'Comment (C)'">
		<button
			type="button"
			:aria-label="noter ? 'Annotate' : 'Comment'"
			:aria-hidden="enabled"
			:tabindex="enabled ? -1 : 0"
			:style="triggerStyle"
			class="fixed z-[2147482995] flex size-8 items-center justify-center rounded-[10px] bg-black-overlay-800 text-white shadow-sm ring-1 ring-white-overlay-100 transition-opacity duration-150"
			:class="enabled ? 'pointer-events-none opacity-0' : ['pointer-events-auto hover:opacity-100 focus-visible:opacity-100', tweakCount || unread ? 'opacity-60' : 'opacity-20']"
			@mousedown="keepFocus"
			@click="openFromTrigger"
		>
			<span :class="noter ? 'lucide-mouse-pointer-click' : 'lucide-message-circle'" class="size-4" aria-hidden="true" />
			<!-- Tweaks stay applied with the toolbar closed; the dot says the page isn't as built. -->
			<span v-if="tweakCount" class="absolute -right-1 size-2.5 rounded-full bg-surface-violet-7 ring-2 ring-surface-base" :class="unread ? '-bottom-1' : '-top-1'" aria-hidden="true" />
			<!-- Unread comments: the dot on the door to them. -->
			<span v-if="unread" class="absolute -right-1 -top-1 size-2.5 rounded-full bg-surface-blue-6 ring-2 ring-surface-base" role="img" aria-label="Unread comments" />
		</button>
	</Tooltip>

	<!-- Always mounted so a hovered list row still outlines its elements with the picker off. -->
	<TweakLayer v-if="noter" :live="tweakLive" />

	<template v-if="enabled">
		<NotePins v-if="mode === 'note' && !canvasOpen" :route="key" :selected="noteSelected" :refs="noteRefs" @open="(n, x, y) => openEdit(n, x, y)" />
		<CommentPins v-if="active && mode === 'comment' && !guest && !canvasOpen && !(phone && sheetOpen)" :route="key" @open="openThreadAt" @draft="reopenDraft" />

		<!-- The hover outline: one element that glides, fades out when picking ends. -->
		<div
			class="pointer-events-none fixed left-0 top-0 z-[2147482995] rounded-[4px] border-[1.5px] border-outline-blue-6"
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
			class="pointer-events-none fixed z-[2147482995] border-[1.5px] border-outline-blue-6"
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
				class="pointer-events-none fixed z-[2147482995] rounded-5 border-[1.5px] border-dashed border-outline-blue-6"
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
				class="pointer-events-none fixed z-[2147482995] bg-surface-red-7"
				:style="{ left: `${l.x}px`, top: `${l.y}px`, width: `${l.w}px`, height: `${l.h}px` }"
				aria-hidden="true"
			/>
			<div
				class="pointer-events-none fixed z-[2147482995] -translate-x-1/2 -translate-y-1/2 rounded-[4px] bg-surface-red-7 px-1 text-xs tabular-nums text-white"
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
				v-if="draft && mode === 'note'"
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
			enter-from-class="opacity-0 scale-[0.96] motion-reduce:scale-100"
			enter-active-class="transition duration-[140ms] ease-out motion-reduce:transition-opacity"
			leave-active-class="transition duration-100 ease-in"
			leave-to-class="opacity-0"
		>
			<CommentPopover
				v-if="draft && mode === 'comment' && !guest"
				:key="draftKey"
				:class="shiftPick && 'invisible'"
				v-model="text"
				:x="at?.x ?? draft.x"
				:y="at?.y ?? draft.y"
				:extra="draft.extra"
				:anchor="newAnchor"
				:thread="thread"
				:avoid="ready ? barBox : null"
				:panel="panelRect"
				@created="onCreated"
				@gone="close"
				:menu-host="menuHost"
				@noted="onNoteDraft"
				@close="close"
			/>
		</Transition>

		<!-- The comments list: a floating card on the right, or a bottom sheet on a phone. It floats; the page never moves for it. -->
		<Transition
			enter-from-class="opacity-0 translate-x-2 motion-reduce:translate-x-0"
			enter-active-class="transition duration-[140ms] ease-out motion-reduce:transition-opacity"
			leave-active-class="transition-opacity duration-100"
			leave-to-class="opacity-0"
		>
			<div v-if="showPanel && !sheetMode && !canvasOpen && panelOpen" ref="panelEl" class="pointer-events-none fixed right-3 z-[2147482995]" :style="panelBox">
				<CommentsPanel :route="key" @choose="openFromList" @hide="panelOpen = false" />
			</div>
		</Transition>
		<BottomSheet v-if="showPanel && sheetMode" v-model:open="sheetOpen" title="Comments">
			<CommentsPanel embedded :route="key" @choose="openFromList" />
		</BottomSheet>

		<Transition
			:enter-from-class="panelBelow ? 'opacity-0 -translate-y-1' : 'opacity-0 translate-y-1'"
			enter-active-class="transition duration-[140ms] ease-out motion-reduce:transition-opacity"
			leave-active-class="transition-opacity duration-100"
			leave-to-class="opacity-0"
		>
			<div
				v-if="listOpen"
				data-notes-panel
				class="pointer-events-auto fixed z-[2147482995] flex max-h-96 w-80 flex-col rounded-5 bg-surface-elevation-2 shadow-lg ring-1 ring-outline-gray-2"
				:style="panelStyle"
			>
				<div class="min-h-0 flex-1 overflow-y-auto p-1.5">
					<!-- Notes -->
					<template v-if="mode === 'note'">
					<template v-for="[r, list] in groups" :key="r">
						<p v-if="groups.length > 1" class="px-2 pt-2 pb-1 text-sm text-ink-gray-5">{{ r }}</p>
						<div
							v-for="n in list"
							:key="n.id"
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
							>{{ noteNumber(n) }}</span>
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
								role="button"
								tabindex="0"
								class="group flex cursor-pointer gap-2 rounded-lg px-2 py-1.5 transition-colors duration-100 hover:bg-surface-gray-2"
								@mouseenter="highlight(t.id)"
								@mouseleave="highlight(null)"
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
										<Button variant="ghost" icon="lucide-x" aria-label="Revert tweak" @click.stop="removeTweak(t.id)" />
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
						:class="saveState === 'error' ? 'text-ink-red-7' : 'text-ink-gray-5'"
						role="status"
					>
						<span
							class="size-3.5 shrink-0"
							:class="saveState === 'saved' ? 'lucide-check' : saveState === 'error' ? 'lucide-triangle-alert' : 'lucide-loader-circle animate-spin motion-reduce:animate-none'"
							aria-hidden="true"
						/>
						{{ saveState === 'saved' ? 'Saved' : saveState === 'error' ? 'Not saved' : 'Saving…' }}
					</span>
					<Button v-if="mode === 'note' && hasSent" variant="ghost" label="Clear sent" @click="clearSent" />
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

		<!-- Above the comment box: the box's menus open here. -->
		<div ref="menuHost" data-annotate-menus class="fixed left-0 top-0 z-[2147482999] size-0" />

		<!-- Never seen: the owner's widest toolbar (Note, with a count), only to be measured.
			The count is measured at two digits, so the tabs hold still when it passes 9. -->
		<div v-if="noter" ref="ghost" aria-hidden="true" inert class="pointer-events-none invisible fixed left-0 top-0 flex w-max items-center gap-1.5 rounded-5 border p-1.5">
			<TabButtons :options="tabOptions" model-value="note">
				<template #suffix="{ button }">
					<template v-if="button.value === 'comment'">
						<template v-if="shownOpen">
							<span v-if="button.name" class="sr-only">{{ button.name }}</span>
							<span class="tabular-nums text-ink-gray-5" :aria-hidden="button.name ? 'true' : undefined">{{ Math.max(shownOpen, 10) }}</span>
						</template>
						<span v-if="unread" class="size-1.5 shrink-0 rounded-full" :class="phone && !openCount ? '' : 'ml-1.5'" />
					</template>
				</template>
			</TabButtons>
			<Button v-if="!canvasOpen" variant="ghost" label="12 notes" />
			<Button v-if="phone" variant="ghost" icon="lucide-copy" aria-label="Copy prompt" />
			<Button v-else variant="ghost" icon-left="lucide-copy" label="Copy prompt" />
			<Button v-if="!canvasOpen" variant="ghost" icon="lucide-x" aria-label="Close toolbar" />
		</div>

		<Transition
			appear
			enter-from-class="opacity-0 translate-y-2 motion-reduce:translate-y-0"
			enter-active-class="transition duration-[180ms] ease-out motion-reduce:transition-opacity"
		>
			<div
				ref="bar"
				role="toolbar"
				aria-label="Annotate"
				class="pointer-events-auto fixed z-[2147482995] flex touch-none items-center gap-1.5 rounded-5 border border-outline-gray-2 bg-surface-elevation-2 p-1.5 shadow-lg"
				:class="[barDragging ? 'cursor-grabbing' : 'cursor-grab', ready ? '' : 'opacity-0', snapping && 'transition-[left,top] duration-150 ease-out motion-reduce:transition-none']"
				:style="{ left: `${pos.left}px`, top: `${pos.top}px` }"
				@mousedown="keepFocus"
				@pointerdown="barDown"
				@pointermove="barMove"
				@pointerup="barUp"
				@pointercancel="barUp"
				@click.capture="barClick"
			>
				<!-- Tool switch. The current tab stays lit while its tool is on; Escape or close is the way off, and then no tab is lit. -->
				<Button v-if="guest" variant="subtle" icon-left="lucide-log-in" label="Sign in to comment" @click="signIn" />
				<Tooltip v-else :text="noter ? tabTip : active ? 'Stop commenting (C)' : TIPS.comment" :hover-delay="600">
					<div class="inline-flex" @pointerover="onTabHover">
						<TabButtons :options="tabOptions" :model-value="active ? mode : undefined">
							<template #suffix="{ button }">
								<template v-if="button.value === 'comment'">
									<template v-if="shownOpen">
										<span v-if="button.name" class="sr-only">{{ button.name }}</span>
										<span class="tabular-nums text-ink-gray-5" :aria-hidden="button.name ? 'true' : undefined">{{ shownOpen }}</span>
									</template>
									<span v-if="unreadDot" class="size-1.5 shrink-0 rounded-full bg-surface-blue-6" :class="phone && !openCount ? '' : 'ml-1.5'" role="img" aria-label="Unread comments" />
								</template>
							</template>
						</TabButtons>
					</div>
				</Tooltip>

				<Tooltip v-if="mode === 'comment' && !guest && (!canvasOpen || canvas.phone)" :text="panelShown ? 'Hide comments' : 'Show comments'" :hover-delay="600" :disabled="phone">
					<Button :variant="panelShown ? 'subtle' : 'ghost'" icon="lucide-panel-right" :aria-label="panelShown ? 'Hide comments' : 'Show comments'" :aria-pressed="panelShown" @click="togglePanel" />
				</Tooltip>

				<span v-if="noter && count && !canvasOpen" data-notes-trigger>
					<Tooltip :text="mode === 'tweak' ? 'Show tweaks' : 'Show notes'" :hover-delay="600">
						<Button :variant="listOpen ? 'subtle' : 'ghost'" :label="countLabel" @click="listOpen = !listOpen" />
					</Tooltip>
				</span>

				<!-- The prompt is the owner's, and never holds a comment. -->
				<template v-if="noter && mode !== 'comment'">
					<Tooltip v-if="!count" :text="`No ${noun}s yet`" :hover-delay="600">
						<span class="inline-flex" tabindex="0">
							<Button variant="ghost" :icon-left="phone ? undefined : 'lucide-copy'" :icon="phone ? 'lucide-copy' : undefined" :label="phone ? undefined : 'Copy prompt'" aria-label="Copy prompt" disabled />
						</span>
					</Tooltip>
					<Tooltip v-else text="Copy prompt for Claude" :hover-delay="600">
						<Button variant="ghost" :icon-left="phone ? undefined : 'lucide-copy'" :icon="phone ? 'lucide-copy' : undefined" :label="phone ? undefined : 'Copy prompt'" aria-label="Copy prompt" @click="copy" />
					</Tooltip>
				</template>

				<Tooltip v-if="!guest && !canvasOpen" text="Hide toolbar" :hover-delay="600">
					<Button class="ml-auto" variant="ghost" icon="lucide-x" aria-label="Close toolbar" @click="setEnabled(false)" />
				</Tooltip>
			</div>
		</Transition>
	</template>
</template>
