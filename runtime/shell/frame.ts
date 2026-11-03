// The shell's side of the frame, for everything drawn over it: what the frame last reported about the page
// (its route, layout and Demo; the canvas is variants.ts's), the rects of the elements the shell draws on, and the asks that wait
// for an answer. Shell.vue owns the iframe and hands every validated message to `receive`.
//
// Nothing sent from here is secret (runtime/shared/protocol.ts): selectors, refs, modes and rects only.
import { reactive, shallowRef, watch } from 'vue'
import { envelope, type FromFrame, type Rect, type ToFrame } from '../shared/protocol'
import type { DemoEntry } from '../shared/picks'

const win = shallowRef<Window | null>(null)
export const setFrameWindow = (w: Window | null) => (win.value = w)

export function post<K extends keyof ToFrame>(type: K, data: ToFrame[K]) {
	// An opaque origin has no name to target. Nothing the shell sends the frame is secret. Plain data only: a
	// reactive object (a thread's anchor, say) cannot be cloned across.
	win.value?.postMessage(JSON.parse(JSON.stringify(envelope(type, data))), '*')
}

// What the frame last said about the page.
export const page = reactive({
	ready: false,
	status: '',
	routes: [] as string[],
	pages: [] as { path: string; title: string }[],
	fullPath: '/',
	path: '/',
	// The route a note belongs to (runtime/agent/dom.ts routeKey).
	key: '/',
	vw: 0,
	vh: 0,
	navBottom: 0,
	pageLayerOpen: false,
	dialogOpen: false,
	demo: [] as DemoEntry[],
})

// ---- Listeners for the messages the toolbar acts on -------------------------------------------
type Handler<K extends keyof FromFrame> = (d: FromFrame[K]) => void
const listeners: { [K in keyof FromFrame]?: Set<Handler<K>> } = {}
export function onFrame<K extends keyof FromFrame>(type: K, fn: Handler<K>): () => void {
	const set = (listeners[type] ??= new Set()) as Set<Handler<K>>
	set.add(fn)
	return () => set.delete(fn)
}

// ---- Tracked rects: id -> the element's box now, null when it is not on the page ---------------
// Each layer (the pins, the box's outline) adds its own entries; they are sent as one map, and the frame
// answers whenever any of them moves.
export type Target = { sel: string; ref?: string }
export const rects = reactive<Record<string, Rect | null>>({})
export const labels = reactive<Record<string, string>>({})
const sources = reactive(new Map<symbol, () => Record<string, Target>>())

export function track(source: () => Record<string, Target>): () => void {
	const key = Symbol()
	sources.set(key, source)
	return () => sources.delete(key)
}
function collect(): ToFrame['track'] {
	const map: Record<string, string> = {}
	const refs: Record<string, string> = {}
	for (const source of sources.values())
		for (const [id, t] of Object.entries(source())) {
			map[id] = t.sel
			if (t.ref) refs[id] = t.ref
		}
	return { map, refs }
}
watch(() => JSON.stringify(collect()), () => post('track', collect()), { flush: 'post' })
// A fresh frame knows nothing of what was tracked: tell it again.
const retrack = () => post('track', collect())

// ---- Asks with an answer ---------------------------------------------------------------------
let req = 0
const waiting = new Map<string, (map: Record<string, Rect | null>) => void>()
// Where these selectors' elements are now. Resolves to an empty map when the frame does not answer.
export function resolveRects(selectors: string[], ms = 1000): Promise<Record<string, Rect | null>> {
	const id = `r${++req}`
	return new Promise((done) => {
		const t = setTimeout(() => {
			waiting.delete(id)
			done({})
		}, ms)
		waiting.set(id, (map) => {
			clearTimeout(t)
			done(map)
		})
		post('resolve', { req: id, selectors })
	})
}
export const resolveRect = async (selector: string) => (selector ? ((await resolveRects([selector]))[selector] ?? null) : null)

// ---- One message in -------------------------------------------------------------------------
export function receive<K extends keyof FromFrame>(type: K, data: FromFrame[K]) {
	const d = data as any
	switch (type) {
		case 'ready':
			Object.assign(page, { ready: true, status: d.status, routes: d.routes, pages: d.pages })
			forgetRefs()
			retrack()
			break
		case 'route':
			Object.assign(page, { fullPath: d.fullPath, path: d.path, key: d.key })
			break
		case 'layout':
			Object.assign(page, d)
			break
		case 'demo':
			page.demo = d.entries
			break
		case 'track':
			for (const k of Object.keys(rects)) if (!(k in d.map)) delete rects[k]
			Object.assign(rects, d.map)
			Object.assign(labels, d.labels)
			break
		case 'rects':
			waiting.get(d.req)?.(d.map)
			waiting.delete(d.req)
			break
	}
	for (const fn of (listeners[type] ?? []) as Set<Handler<K>>) fn(data)
}

// The frame is being replaced (a live reload): what it said no longer holds.
const gone = new Set<() => void>()
export const onGone = (fn: () => void) => (gone.add(fn), () => gone.delete(fn))
export function frameGone() {
	page.ready = false
	for (const k of Object.keys(rects)) delete rects[k]
	forgetRefs()
	gone.forEach((fn) => fn())
}

// The element refs a frame handed out (runtime/agent/refs.ts) name elements of that load only. Whatever the shell keeps
// them in drops them when the frame goes or a new one says it is ready (it may have reloaded itself), and falls back to
// its selectors.
const refHolders = new Set<() => void>()
export const onRefsGone = (fn: () => void) => (refHolders.add(fn), () => refHolders.delete(fn))
function forgetRefs() {
	refHolders.forEach((fn) => fn())
}
