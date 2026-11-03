// What the canvas and the annotate toolbar tell each other. They are two bundles in one document: annotate imports
// this through `sketch:variants`, and the canvas imports it directly, so both hold the same object. The canvas
// owns the tiles, the pan and the zoom; the toolbar owns comments and notes. Neither imports the other.
import { shallowReactive } from 'vue'
import type { Component } from 'vue'
import type { PageModel, TileBox } from './layout'
import type { PickItem } from './picker'

// A canvas tile in plain data, the tile's words (whereOf, tileLabel) and sameTile live in runtime/shared/tiles.ts,
// which the Viewer shell shares.
import { sameTile, type TileHit, type TileRef, type TileSpot } from '../shared/tiles'

export { sameTile, tileLabel, whereOf } from '../shared/tiles'
export type { TileHit, TileRef, TileSpot }

export type Tab = 'browse' | 'comments' | 'notes'

export const bridge = shallowReactive({
  // ---- Set by the canvas
  open: false,
  phone: false,
  // The pick on show, the zoom, and whether the right panel is open and how much room it takes.
  view: '',
  zoom: 1,
  panelOpen: true,
  reserve: 0,
  // How much of the bottom-right corner the zoom pill takes, with its gap.
  corner: 0,
  model: null as PageModel[] | null,
  tiles: [] as TileBox[],
  // The pan (the zoom is above), and the Show list's rows, for the Viewer shell, which draws the pins and the panel.
  pan: { x: 0, y: 0 },
  items: [] as PickItem[],
  // Asked of the canvas: bring a tile into view and give its point on the screen; leave the canvas.
  reveal: null as ((spot: TileSpot, at?: { fx: number; fy: number }) => Promise<{ x: number; y: number } | null>) | null,
  pointOf: null as ((spot: TileSpot, at: { fx: number; fy: number }) => { x: number; y: number } | null) | null,
  // ---- Set by the toolbar
  // On a phone, how far from the bottom the open toolbar's top edge (plus a gap) is: the Demo pill rides above it.
  toolbarLift: 0,
  // Where that toolbar ends sideways, so the pill lifts only when it is really in the way.
  toolbarRight: 0,
  // What a person may do here, and the tool picking tiles ('' while browsing).
  canComment: false,
  canNote: false,
  tool: '' as '' | 'comment' | 'note',
  // The panel's tab. The tab and the tool follow each other.
  tab: 'browse' as Tab,
  counts: { comments: 0, notes: 0 },
  pick: null as ((hit: TileHit) => void) | null,
  // The pins drawn on the tiles, and the content of each extra tab.
  Pins: null as Component | null,
  tabs: {} as { comments?: Component; notes?: Component },
  // ---- Set by the Viewer shell's agent (runtime/agent): the panel and the toolbar are the shell's, drawn over the
  // canvas. `shellReserve` is the room the shell's panel takes on the right; `onEmptyClick` hears a click on the
  // canvas off every tile while a tool is in hand.
  shell: false,
  shellReserve: 312,
  onEmptyClick: null as (() => void) | null,
  // The live tile's ⋯ asks the shell for its menu, at the button's box; the shell draws it and does what is picked.
  // `busyTile` is the tile whose action the shell is saving (its ⋯ spins), `menuTile` the one whose menu is open (its ⋯
  // looks pressed); `openTile` is the menu's Open page.
  tileMenu: null as ((tileId: string, rect: { x: number; y: number; w: number; h: number }) => void) | null,
  busyTile: '',
  menuTile: '',
  openTile: null as ((tileId: string) => void) | null,
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

// Whether the canvas still has this tile: null until the pages are known.
export function tileExists(model: PageModel[] | null, spot: TileSpot): boolean | null {
  if (!model) return null
  const page = model.find((p) => p.path === spot.route)
  if (!page) return false
  const { kind, groupKey, option } = spot.tile
  if (kind === 'default') return true
  if (kind === 'set') return !!page.sets.find((s) => s.key === groupKey)?.options.some((o) => o.value === option)
  return !!page.states.find((s) => s.key === groupKey)?.options.slice(1).includes(option)
}
