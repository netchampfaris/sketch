// What the canvas and the annotate toolbar tell each other. They are two bundles in one document: annotate imports
// this through `sketch:variants`, and the canvas imports it directly, so both hold the same object. The canvas
// owns the tiles, the pan and the zoom; the toolbar owns comments and notes. Neither imports the other.
import { shallowReactive } from 'vue'
import type { Component } from 'vue'
import type { PageModel, TileBox } from './layout'
import { slugOf } from './state'

// A canvas tile in plain data: the page it belongs to (`route` sits beside it in an anchor), the variant option
// or page state it shows, and the view it was pinned in. Options are named by their slot, never by their order,
// so a tile keeps its comments whatever else joins or leaves its set.
export type TileRef = {
  kind: 'set' | 'state' | 'default'
  // The URL value of the pick the tile was pinned in: `set:overview/spend-summary`.
  view: string
  // Words for people and agents: the page title, the set or state label, the option's label.
  page: string
  group: string
  groupKey: string
  option: string
  optionLabel: string
}
// A tile and the page it sits on, as an anchor stores them.
export type TileSpot = { route: string; tile: TileRef }
// A click on a tile: the spot, where on it as a fraction, and where on the screen.
export type TileHit = TileSpot & { fx: number; fy: number; x: number; y: number }

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
  // Put a note for the agent on a tile (rejects with the reason it could not be saved), take one back, and find the one
  // on a tile that was added with these opening words and is still waiting for the agent.
  addNote: null as ((spot: TileSpot, text: string) => Promise<string>) | null,
  removeNote: null as ((id: string) => void) | null,
  pendingNote: null as ((spot: TileSpot, opening: string) => string | null) | null,
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

// The same tile, whichever view it was pinned in.
export const sameTile = (a: TileSpot, b: TileSpot) =>
  a.route === b.route && a.tile.kind === b.tile.kind && a.tile.groupKey === b.tile.groupKey && a.tile.option === b.tile.option

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
  if (page.states.find((s) => s.key === groupKey)?.options.slice(1).includes(option)) return true
  // A component state's key ends in its set and option, "state@supplier-card-compact": it stands while that option does.
  const of = groupKey.slice(groupKey.indexOf('@') + 1)
  return groupKey.includes('@') && page.sets.some((s) => s.options.some((o) => slugOf(`${s.label}/${o.label}`) === of))
}

// The tile in plain words, the way the agent reads it: "Canvas · Overview › Spend summary › option Donut".
// Mirrors sketch/comments.py `where_of`.
export function whereOf(spot: TileSpot): string {
  const { tile } = spot
  const say = (v: string) => (v || '').split(/\s+/).filter(Boolean).join(' ')
  const page = say(tile.page) || say(spot.route)
  const option = say(tile.optionLabel) || say(tile.option)
  const group = say(tile.group) || say(tile.groupKey)
  const parts =
    tile.kind === 'set'
      ? [page, group, `option ${option}`]
      : tile.kind === 'state'
        ? [page, ...(group && group.toLowerCase() !== 'state' ? [group] : []), `state ${option}`]
        : [page, 'default']
  return 'Canvas · ' + parts.filter(Boolean).join(' › ')
}

// The tile's name inside its page, for a list row: "Spend summary › Donut", or just the option when the page is clear.
export function tileLabel(tile: TileRef, short = false): string {
  if (tile.kind === 'default') return 'Default'
  if (tile.kind === 'state' || short) return tile.optionLabel || tile.option
  return `${tile.group || tile.groupKey} › ${tile.optionLabel || tile.option}`
}
