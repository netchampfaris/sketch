// What the canvas and the Viewer shell's agent (runtime/agent) tell each other. They are two bundles in one document:
// the agent imports this through `sketch:variants`, and the canvas imports it directly, so both hold the same object.
// The canvas owns the tiles, the pan and the zoom; the shell, over the frame, owns the panel, the toolbar and the pins.
import { shallowReactive, shallowRef } from 'vue'
import type { PageModel, TileBox } from './layout'
import type { PickItem } from './picker'

// A canvas tile in plain data, the tile's words (whereOf, tileLabel) and sameTile live in runtime/shared/tiles.ts,
// which the Viewer shell shares.
import { sameTile, type TileHit, type TileRef, type TileSpot } from '../shared/tiles'
import type { CanvasPage } from '../shared/protocol'

export { sameTile, tileLabel, whereOf } from '../shared/tiles'
export type { TileHit, TileRef, TileSpot }

export const bridge = shallowReactive({
  // ---- Set by the canvas
  open: false,
  phone: false,
  // The pick on show, and the zoom.
  view: '',
  zoom: 1,
  // How much of the bottom-right corner the zoom pill takes, with its gap.
  corner: 0,
  model: null as PageModel[] | null,
  tiles: [] as TileBox[],
  // The pan (the zoom is above), and the Show list's rows, for the Viewer shell, which draws the pins and the panel.
  pan: { x: 0, y: 0 },
  items: [] as PickItem[],
  // Asked of the canvas: bring a tile into view and give its point on the screen.
  reveal: null as ((spot: TileSpot, at?: { fx: number; fy: number }) => Promise<{ x: number; y: number } | null>) | null,
  // ---- Set by the Viewer shell's agent (runtime/agent): the panel, the toolbar and the pins are the shell's, drawn
  // over the canvas. The tool picking tiles ('' while browsing), and where a tile clicked with it is sent.
  tool: '' as '' | 'comment' | 'note',
  pick: null as ((hit: TileHit) => void) | null,
  // `shellReserve` is the room the shell's panel takes on the right; `onEmptyClick` hears a click on the canvas off
  // every tile while a tool is in hand.
  shellReserve: 312,
  onEmptyClick: null as (() => void) | null,
  // The live tile's ⋯ asks the shell for its menu, at the button's box; the shell draws it and does what is picked.
  // `busyTile` is the tile whose action the shell is saving (its ⋯ spins), `menuTile` the one whose menu is open (its ⋯
  // looks pressed); `openTile` is the menu's Open page.
  tileMenu: null as ((tileId: string, rect: { x: number; y: number; w: number; h: number }) => void) | null,
  busyTile: '',
  menuTile: '',
  openTile: null as ((tileId: string) => void) | null,
  // The phone's Show list is the shell's too: the title pill's name asks for it at its box (`open` false closes it),
  // and `showOpen` is whether it is open, for the name's pressed look.
  showMenu: null as ((rect: { x: number; y: number; w: number; h: number }, open: boolean) => void) | null,
  showOpen: false,
})

// ---- Tiles as data

export function tileRefOf(t: TileBox, view: string): TileRef | null {
  if (t.kind === 'gap') return null
  if (t.kind === 'set') {
    return { kind: 'set', view, page: t.pageTitle, group: t.setLabel ?? t.setKey ?? '', groupKey: t.setKey ?? '', option: t.option ?? '', optionLabel: t.opt ?? t.option ?? '' }
  }
  if (t.kind === 'state') {
    return { kind: 'state', view, page: t.pageTitle, group: t.stateLabel ?? t.stateKey ?? '', groupKey: t.stateKey ?? '', option: t.option ?? '', optionLabel: t.option ?? '' }
  }
  return { kind: 'default', view, page: t.pageTitle, group: '', groupKey: '', option: '', optionLabel: 'Default' }
}

export const spotOf = (t: TileBox, view: string): TileSpot | null => {
  const tile = tileRefOf(t, view)
  return tile ? { route: t.path, tile } : null
}

export function findTile(tiles: TileBox[], spot: TileSpot, view: string): TileBox | undefined {
  return tiles.find((t) => {
    const s = spotOf(t, view)
    return !!s && sameTile(s, spot)
  })
}

// What the canvas found on its pages, in the protocol's words (sets by key with their option values, states by key with
// their options): what the shell is told, and what runtime/shared/tiles.ts tileExists reads on both sides.
export const pagesOf = (model: PageModel[] | null): CanvasPage[] | null =>
  model &&
  model.map((p) => ({
    path: p.path,
    title: p.title,
    sets: p.sets.map((s) => ({ key: s.key, options: s.options.map((o) => o.value) })),
    states: p.states.map((s) => ({ key: s.key, options: s.options })),
  }))

// The option a write has just put in place (Make default, Keep only this, or their Undo, saved by the shell): the canvas
// rings its tile once it is drawn, so the option picked is still under the eye after the frame reloads. The shell
// says which (`display.landed`).
export const landed = shallowRef<{ set: string; option: string } | null>(null)
