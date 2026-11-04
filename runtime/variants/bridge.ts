// What the canvas and the Viewer shell's agent (runtime/agent) tell each other. They are two bundles in one document:
// the agent imports this through `sketch:variants`, and the canvas imports it directly, so both hold the same object.
// The canvas owns the tiles, the pan and the zoom; the shell, over the frame, owns the panel, the toolbar and the pins.
import { shallowReactive, shallowRef } from 'vue'
import type { PageModel, TileBox } from './layout'
import type { PickItem } from './picker'
import { ofOption, slugOf } from './state'

// A canvas tile in plain data, the tile's words (whereOf, tileLabel) and sameTile live in runtime/shared/tiles.ts,
// which the Viewer shell shares.
import { sameTile, type TileHit, type TileRef, type TileSpot } from '../shared/tiles'
import type { CanvasPage, CanvasTile, EmptyView, FromFrame, Pill, PickItem as ShownItem, ZoomTo } from '../shared/protocol'

export { sameTile, tileLabel, whereOf } from '../shared/tiles'
export type { TileHit, TileRef, TileSpot }

export const bridge = shallowReactive({
  // ---- Set by the canvas
  open: false,
  phone: false,
  // The pick on show, and the zoom.
  view: '',
  zoom: 1,
  // How much of the bottom-right corner the zoom pill takes, with its gap, and the title and zoom pills' boxes: the
  // shell's pins go under them.
  corner: 0,
  pills: [] as Pill[],
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
  // The menu's States: the option's component states.
  statesTile: null as ((tileId: string) => void) | null,
  // One option's States view with none built, for the shell's "No states built yet" and Ask agent.
  empty: null as EmptyView | null,
  // The phone's Show list is the shell's too: the title pill's name asks for it at its box (`open` false closes it),
  // and `showOpen` is whether it is open, for the name's pressed look.
  showMenu: null as ((rect: { x: number; y: number; w: number; h: number }, open: boolean) => void) | null,
  showOpen: false,
  // The zoom menu is the shell's too, so it draws over the panel: the % asks for it at its box, `zoomMenu` is whether it
  // is open, and `zoomTo` is what is picked in it.
  zoomMenu: null as ((rect: { x: number; y: number; w: number; h: number }) => void) | null,
  zoomOpen: false,
  zoomTo: null as ((to: ZoomTo) => void) | null,
})

// ---- Tiles as data

export function tileRefOf(t: TileBox, view: string): TileRef | null {
  // The one tile of an option that is still being drawn stands for no state yet, so nothing is pinned to it.
  if (t.kind === 'default' && t.setKey) return null
  if (t.kind === 'set') {
    return { kind: 'set', view, page: t.pageTitle, group: t.setLabel ?? t.setKey ?? '', groupKey: t.setKey ?? '', option: t.option ?? '', optionLabel: t.opt ?? t.option ?? '' }
  }
  if (t.kind === 'state') {
    // A component state names its set and option in its group, so the agent reads where it is; its key already carries them.
    const group = t.setKey ? `${t.setLabel} › ${t.setOptionLabel} › ${t.stateLabel}` : (t.stateLabel ?? t.stateKey ?? '')
    return { kind: 'state', view, page: t.pageTitle, group, groupKey: t.stateKey ?? '', option: t.option ?? '', optionLabel: t.option ?? '' }
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

// ---- The canvas in the protocol's words: what the frame agent (runtime/agent) sends the shell as `canvas`

// The tiles in the canvas's own coordinates, each with the spot it is; a gap is no tile.
export function tilesOf(tiles: TileBox[], view: string): CanvasTile[] {
  return tiles.flatMap((t) => {
    const spot = spotOf(t, view)
    if (!spot) return []
    const set = t.kind === 'set'
    return [
      {
        id: t.id,
        route: spot.route,
        rect: { x: t.x, y: t.y, w: t.w, h: t.h },
        tile: spot.tile,
        label: t.opt ?? t.caption ?? '',
        isDefault: !!t.isDefault,
        author: t.author ?? '',
        setName: set ? (t.setName ?? '') : '',
        setFile: set ? (t.setFile ?? '') : '',
        setCount: set ? (t.setOptions?.length ?? 0) : 0,
      },
    ]
  })
}

// The Show list's rows.
export const itemsOf = (items: PickItem[]): ShownItem[] =>
  items.map((i) => ({ value: i.value, label: i.label, sub: i.sub ?? '', short: i.short, group: i.group, options: i.options ?? [] }))

// What the canvas shows now, whole. The pages are left out until the canvas has looked: none is not an empty list.
export function canvasReport(): FromFrame['canvas'] {
  const at = { open: bridge.open, phone: bridge.phone, view: String(bridge.view ?? ''), zoom: bridge.zoom, pan: bridge.pan, corner: bridge.corner, pills: bridge.pills, empty: bridge.open ? bridge.empty : null }
  if (!bridge.open) return at
  const pages = pagesOf(bridge.model)
  return { ...at, tiles: tilesOf(bridge.tiles, bridge.view), items: itemsOf(bridge.items), ...(pages ? { pages } : {}) }
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
    // A component state stands while its set's option does: the options as `of` names them ("Supplier card/Compact").
    ofs: p.sets.flatMap((s) => s.options.map((o) => slugOf(ofOption(s.label, o.label)))),
  }))

// The option a write has just put in place (Make default, Keep only this, or their Undo, saved by the shell): the canvas
// rings its tile once it is drawn, so the option picked is still under the eye after the frame reloads. The shell
// says which (`display.landed`).
export const landed = shallowRef<{ set: string; option: string } | null>(null)
