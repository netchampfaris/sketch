// `sketch:variants` as the Viewer shell builds it (frontend/vite.config.ts alias). The comment and note
// components shared with the in-frame toolbar (runtime/annotate) import what they need from that module by
// name; in the shell the Demo and the canvas are in the frame, so their answers come from what the frame
// reported (frame.ts `page`, and the `canvas` message here), and a change goes to the frame as a message.
//
// The canvas's tiles, pan and zoom are the frame's; the shell draws the panel, the toolbar and the pins on the
// tiles over it (CanvasLayer.vue), from the tiles' boxes in the canvas's own coordinates and the pan and zoom.
import { ref, shallowReactive, type Component } from 'vue'
import { onFrame, onGone, page, post } from './frame'
import { picksShownIn, reachableIn, type DemoPick } from '../shared/picks'
import { sameTile, type TileSpot } from '../shared/tiles'
import type { CanvasPage, PickItem } from '../shared/protocol'

export { sameTile, tileLabel, whereOf } from '../shared/tiles'
export type { TileHit, TileRef, TileSpot } from '../shared/tiles'
export { picksWords } from '../shared/picks'
export type { DemoPick }
export { hasUnreadThreads, readThread, setUnread } from './badges'

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

export const bridge = shallowReactive({
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
	const was = bridge.open
	Object.assign(bridge, { open: d.open, phone: d.phone, view: d.view, zoom: d.zoom, pan: d.pan, corner: d.corner })
	if (d.tiles)
		bridge.tiles = d.tiles.map(({ rect, route, tile, ...t }) => ({ ...t, ...rect, spot: { route, tile } }))
	if (d.pages) bridge.model = d.pages
	if (d.items) bridge.items = d.items
	// Closed, the canvas has no tiles: a pin list or a count must not read the last ones.
	if (was && !d.open) Object.assign(bridge, { tiles: [], model: null, items: [], view: '' })
})
// A reloaded frame says everything again.
onGone(() => Object.assign(bridge, { open: false, phone: false, view: '', tiles: [], model: null, items: [], corner: 0 }))

// ---- Tiles as data
export const spotOf = (t: ShellTile, _view?: string): TileSpot => t.spot
export const findTile = (tiles: ShellTile[], spot: TileSpot, _view?: string) => tiles.find((t) => sameTile(t.spot, spot))

// Whether the canvas still has this tile: null until the pages are known.
export function tileExists(model: CanvasPage[] | null, spot: TileSpot): boolean | null {
	if (!model) return null
	const p = model.find((x) => x.path === spot.route)
	if (!p) return false
	const { kind, groupKey, option } = spot.tile
	if (kind === 'default') return true
	if (kind === 'set') return !!p.sets.find((s) => s.key === groupKey)?.options.includes(option)
	return !!p.states.find((s) => s.key === groupKey)?.options.slice(1).includes(option)
}

// A spot on a tile on the screen now: pan + its place on the tile * zoom. Null when the canvas does not show the tile.
export function pointOf(spot: TileSpot, at: { fx: number; fy: number }) {
	const t = findTile(bridge.tiles, spot)
	if (!t) return null
	return { x: bridge.pan.x + (t.x + at.fx * t.w) * bridge.zoom, y: bridge.pan.y + (t.y + at.fy * t.h) * bridge.zoom }
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
export function applyPicks(picks: DemoPick[] | undefined, _router?: unknown) {
	post('picks:apply', { picks: (picks ?? []).map(({ kind, path, key, option }) => ({ kind, path, key, option })) })
}

// One dropdown open at a time across the shell's toolbar, comment box and panel (runtime/variants/menus.ts).
const current = ref<string | null>(null)
export function menuBind(key: string, onOpen?: () => void) {
	return {
		open: current.value === key,
		'onUpdate:open': (o: boolean) => {
			if (o) {
				current.value = key
				onOpen?.()
			} else if (current.value === key) current.value = null
		},
	}
}
