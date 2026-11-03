// The shell's side of the frame's canvas (and of its Demo picks), for the toolbar, the comment and note components and
// the canvas layer. The Demo and the canvas are in the frame (runtime/variants), so the answers here come from what the
// frame reported (frame.ts `page`, and the `canvas` message here), and a change goes to the frame as a message.
//
// The canvas's tiles, pan and zoom are the frame's; the shell draws the panel, the toolbar and the pins on the
// tiles over it (CanvasLayer.vue), from the tiles' boxes in the canvas's own coordinates and the pan and zoom.
import { shallowReactive, watch, type Component } from 'vue'
import { lookAt } from './badges'
import { onFrame, onGone, page, post } from './frame'
import { picksShownIn, reachableIn, type DemoPick } from '../shared/picks'
import { sameTile, type TileSpot } from '../shared/tiles'
import type { CanvasPage, PickItem } from '../shared/protocol'

export type Tab = 'browse' | 'comments' | 'notes'
// A tile as the shell holds it: its box before pan and zoom, and the spot it is.
// A set's tile also names its `<Variants>` and how many options it has, for the tile menu (TileMenu.vue).
export type ShellTile = {
	id: string
	x: number
	y: number
	w: number
	h: number
	spot: TileSpot
	label: string
	isDefault: boolean
	author: string
	setName: string
	setFile: string
	setCount: number
}

// The panel on the right of the canvas (runtime/variants/Canvas.vue PANEL_W): 12px off the edge, 300px wide.
export const PANEL_W = 312

export const canvas = shallowReactive({
	// ---- What the frame says of the canvas
	open: false,
	phone: false,
	// The pick on show, as the URL writes it.
	view: '',
	zoom: 1,
	pan: { x: 0, y: 0 },
	// How much of the bottom-right corner the zoom pill takes, with its gap.
	corner: 0,
	model: null as CanvasPage[] | null,
	tiles: [] as ShellTile[],
	items: [] as PickItem[],
	// ---- The shell's own
	// Whether the panel is open on desktop, for the whole visit, and how much room it takes from the right edge.
	panelOpen: true,
	reserve: 0,
	// What a person may do here, and the tool picking tiles ('' while browsing).
	canComment: false,
	canNote: false,
	tool: '' as '' | 'comment' | 'note',
	// The panel's tab. The tab and the tool follow each other (Toolbar.vue).
	tab: 'browse' as Tab,
	counts: { comments: 0, notes: 0 },
	// The pins drawn on the tiles, and the content of each extra tab, registered by the toolbar.
	Pins: null as Component | null,
	tabs: {} as { comments?: Component; notes?: Component },
})

onFrame('canvas', (d) => {
	const was = canvas.open
	Object.assign(canvas, { open: d.open, phone: d.phone, view: d.view, zoom: d.zoom, pan: d.pan, corner: d.corner })
	if (d.tiles)
		canvas.tiles = d.tiles.map(({ rect, route, tile, ...t }) => ({ ...t, ...rect, spot: { route, tile } }))
	if (d.pages) canvas.model = d.pages
	if (d.items) canvas.items = d.items
	// Closed, the canvas has no tiles: a pin list or a count must not read the last ones.
	if (was && !d.open) {
		Object.assign(canvas, { tiles: [], model: null, items: [], view: '' })
		chosen = ''
	}
})
// A reloaded frame says everything again.
onGone(() => {
	Object.assign(canvas, { open: false, phone: false, view: '', tiles: [], model: null, items: [], corner: 0 })
	chosen = ''
})

// ---- Showing a view
// The view the person picked in the shell (a row of the panel, the Demo pill, a list's thread or note), until the canvas
// shows it or closes. Opening a set this way is looking at its options: the ones a teammate made stop being new (the
// rows lose their dot; the tiles keep their "New" badge until the next visit, so nothing vanishes under the pointer).
// The frame showing a view on its own is not, nor is 'auto' (whatever the canvas picks first); and the set is the key
// in the view the person picked, its options the ones the server put in it (badges.ts lookAt), not what the frame lists.
let chosen = ''
export function showView(view: string) {
	chosen = view
	post('canvas:open', { view })
}
watch(
	() => canvas.view,
	(view) => {
		if (!canvas.open || !view || view !== chosen || view === 'auto') return
		chosen = ''
		if (view.startsWith('set:')) lookAt(view.slice(view.lastIndexOf('/') + 1))
	},
)

// ---- Tiles as data
export const findTile = (tiles: ShellTile[], spot: TileSpot) => tiles.find((t) => sameTile(t.spot, spot))

// A spot on a tile on the screen now: pan + its place on the tile * zoom. Null when the canvas does not show the tile.
export function pointOf(spot: TileSpot, at: { fx: number; fy: number }) {
	const t = findTile(canvas.tiles, spot)
	if (!t) return null
	return { x: canvas.pan.x + (t.x + at.fx * t.w) * canvas.zoom, y: canvas.pan.y + (t.y + at.fy * t.h) * canvas.zoom }
}

// Bring a tile into view (the frame pans to it) and give the spot's point on the screen. Null when the canvas no longer
// has the tile, or the frame does not answer.
let req = 0
const waiting = new Map<string, (p: { x: number; y: number } | null) => void>()
onFrame('canvas:revealed', (d) => {
	waiting.get(d.req)?.(d.point)
	waiting.delete(d.req)
})
export function revealTile(spot: TileSpot, at: { fx: number; fy: number }, ms = 6000): Promise<{ x: number; y: number } | null> {
	const id = `v${++req}`
	return new Promise((done) => {
		const t = setTimeout(() => {
			waiting.delete(id)
			done(null)
		}, ms)
		waiting.set(id, (p) => {
			clearTimeout(t)
			done(p)
		})
		post('canvas:reveal', { req: id, spot, fx: at.fx, fy: at.fy })
	})
}

// A route record's name the way the canvas gives it: the frame sends each page's title (Shell's memory router).
export const titleOfRoute = (r: { meta?: { title?: string }; path: string }) => r.meta?.title ?? r.path

// The Demo picks: on show when the frame's Demo shows them; putting them back is the frame's to do.
export const picksShown = (picks: DemoPick[] | undefined) => picksShownIn(page.demo, picks)
export const picksAvailable = (picks: DemoPick[] | undefined) => (picks ?? []).every((p) => reachableIn(page.demo, p))
export function applyPicks(picks: DemoPick[] | undefined) {
	post('picks:apply', { picks: (picks ?? []).map(({ kind, path, key, option }) => ({ kind, path, key, option })) })
}
