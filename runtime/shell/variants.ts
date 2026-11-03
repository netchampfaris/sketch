// `sketch:variants` as the Viewer shell builds it (frontend/vite.config.ts alias). The comment and note
// components shared with the in-frame toolbar (runtime/annotate) import what they need from that module by
// name; in the shell the Demo and the canvas are in the frame, so their answers come from what the frame
// reported (frame.ts `page`), and a change goes to the frame as a message. The canvas half (tiles, pins on
// tiles) is plan step 4: until then the shell knows no tiles.
import { ref, shallowReactive } from 'vue'
import { page, post } from './frame'
import { picksShownIn, reachableIn, type DemoPick } from '../shared/picks'
import type { TileSpot } from '../shared/tiles'

export { sameTile, tileLabel, whereOf } from '../shared/tiles'
export type { TileHit, TileRef, TileSpot } from '../shared/tiles'
export { picksWords } from '../shared/picks'
export type { DemoPick }
export { hasUnreadThreads, readThread, setUnread } from './badges'

// What the toolbar reads of the canvas. Closed, with no tiles, until the canvas moves here (plan step 4).
export const bridge = shallowReactive({
	open: false,
	phone: false,
	view: '',
	model: null as { path: string }[] | null,
	tiles: [] as unknown[],
})
export const tileExists = (_model: unknown, _spot: TileSpot): boolean | null => null
export const findTile = (_tiles: unknown[], _spot: TileSpot, _view: string) => undefined

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
