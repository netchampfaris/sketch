// A canvas tile in words: the pure half of runtime/variants/bridge.ts, shared with the Viewer shell, which
// names tiles in its lists and prompts but never holds the canvas.
import type { CanvasPage, TileRef, TileSpot } from './protocol'

export type { TileRef, TileSpot }
// A click on a tile: the spot, where on it as a fraction, and where on the screen.
export type TileHit = TileSpot & { fx: number; fy: number; x: number; y: number }

// The same tile, whichever view it was pinned in.
export const sameTile = (a: TileSpot, b: TileSpot) =>
  a.route === b.route && a.tile.kind === b.tile.kind && a.tile.groupKey === b.tile.groupKey && a.tile.option === b.tile.option

// The `of` a state's key ends in, as a slug, or '' for a page state.
export const ofOfKey = (key: string) => (key.includes('@') ? key.slice(key.indexOf('@') + 1) : '')

// Whether the canvas still has this tile, by the pages it found: null until they are known.
export function tileExists(pages: CanvasPage[] | null, spot: TileSpot): boolean | null {
  if (!pages) return null
  const p = pages.find((x) => x.path === spot.route)
  if (!p) return false
  const { kind, groupKey, option } = spot.tile
  if (kind === 'default') return true
  if (kind === 'set') return !!p.sets.find((s) => s.key === groupKey)?.options.includes(option)
  if (p.states.find((s) => s.key === groupKey)?.options.slice(1).includes(option)) return true
  // A component state's key ends in its set and option, "state@supplier-card-compact": it stands while that option does.
  const of = ofOfKey(groupKey)
  return !!of && p.ofs.includes(of)
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
