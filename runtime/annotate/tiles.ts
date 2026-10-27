// What the toolbar keeps for the canvas: the hands the pins call back into, and the anchor a tile click makes.
// Annotate.vue fills `handlers` in; the pins live in the canvas's own tree, so they cannot emit to it.
import { reactive } from 'vue'
import type { TileSpot } from 'sketch:variants'
import type { Note } from './annotate'
import type { Anchor, Thread } from './comments'

export const handlers = {
	thread: null as ((t: Thread, x: number, y: number) => void) | null,
	note: null as ((n: Note, x: number, y: number) => void) | null,
}
// The note whose box is open, so its pin can wear a ring.
export const canvasUi = reactive({ noteId: '' })

// A spot on a tile, as a note or a comment stores it: the page in `route`, the element fields empty, and the
// click as a fraction of the tile. The server checks it again (sketch/comments.py clean_tile_anchor).
export function tileAnchor(spot: TileSpot, at: { fx: number; fy: number }): Anchor {
	return {
		route: spot.route,
		viewport: `${window.innerWidth}x${window.innerHeight}`,
		selector: '',
		component: '',
		componentChain: [],
		file: '',
		element: '',
		text: '',
		offset: { x: at.fx, y: at.fy },
		rect: { x: 0, y: 0, w: 0, h: 0 },
		tile: spot.tile,
	}
}
