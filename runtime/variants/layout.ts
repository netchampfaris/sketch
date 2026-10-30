// The canvas world for one pick: one even grid of tiles in canvas units (CSS px at 100% zoom). It is computed
// once per view, window size and panel state, with the largest gaps it needs, and zoom never touches it.
import type { DGroup, Opt } from './state'
import type { Pick } from './picker'

export const GAP = 48
// The tile's labels, in on-screen px at the fit zoom. Above: the name row (24, it holds the ⋯), 8 below it. Under: 8, the author row (24).
export const LABEL = 32
export const AUTHOR = 32
export const PAD = 32
// The top keeps clear of the floating title pill (12 inset, 36 tall, 12 below it).
export const TOP = 60
// A heading over a section of tiles: its row (24) and the room under it (16), in on-screen px at the fit zoom.
export const HEAD = 40
// A set tile shows the set's own box with this much tile background around it.
export const MARGIN = 16
const MIN_Z = 0.05

export type SetMeta = { x: number; y: number; w: number; h: number }
// A state switch the canvas found: `options` is the flat list, first one the default. `of` is set on a component state
// ("Supplier card/Compact"); one with no set to belong to is shown on its page, under that name.
export type StateInfo = { key: string; label: string; options: string[]; groups?: DGroup[]; of?: string }
export type PageModel = {
  path: string
  slug: string
  title: string
  states: StateInfo[]
  sets: { key: string; label: string; name: string; file: string; options: Opt[]; meta: SetMeta | null }[]
}
export type TileBox = {
  id: string
  cacheId: string
  path: string
  slug: string
  pageTitle: string
  caption: string
  // Order of the option in its set, from 1.
  n?: number
  // The username of the teammate who made this option, absent for the owner's own.
  author?: string
  // The option this tile shows, for its accessible name.
  opt?: string
  kind: 'default' | 'state' | 'set'
  // The heading this tile sits under, when it has one.
  section?: string
  stateKey?: string
  stateLabel?: string
  setKey?: string
  setLabel?: string
  // A state tile of one option's component states: the option the page is pinned to, by value and by label. It is clipped
  // to the set's box, as a set tile is.
  setOption?: string
  setOptionLabel?: string
  // What Make default needs to rewrite the source: the tag's name, its file and the set's options in order.
  setName?: string
  setFile?: string
  setOptions?: Opt[]
  option?: string
  isDefault?: boolean
  // Set tiles: the set's box when the page was first drawn.
  meta?: SetMeta
  x: number
  y: number
  w: number
  h: number
}
export type Fit = { x: number; y: number; z: number }
export type Head = { text: string; x: number; y: number }
export type Layout = { tiles: TileBox[]; heads: Head[]; bounds: { w: number; h: number }; fit: Fit; invFit: number; sig: string }
export type LayoutCtx = {
  win: { w: number; h: number }
  // The room the grid has on screen.
  vp: { w: number; h: number }
  phone: boolean
  // The size of one option's own set box once it has been drawn.
  sizeOf: (cacheId: string, setKey: string) => { w: number; h: number } | null
  // The states a drawn page declared, by tile: null until it is drawn, 'error' when it could not be.
  statesOf: (cacheId: string) => StateInfo[] | 'error' | null
}

type Desc = Omit<TileBox, 'x' | 'y' | 'w' | 'h'>

const empty: Layout = { tiles: [], heads: [], bounds: { w: 0, h: 0 }, fit: { x: 0, y: 0, z: 1 }, invFit: 1, sig: '' }

// The tiles of some state switches, in sections: one per switch, or per group of a grouped switch. A switch's first option
// is the default, so it has no tile of its own. A state that belongs to a set nobody has any more is headed by that
// set and option ("Supplier card · Compact"); `byOf` is off in a set option's own view, where that is the whole view.
function sectionsOf(states: StateInfo[], byOf: boolean) {
  const out: { title: string; picks: { s: StateInfo; o: string }[] }[] = []
  for (const s of states)
    for (const g of s.groups ?? [{ title: '', options: s.options }]) {
      const title = s.of && byOf ? s.of.replace('/', ' · ') : g.title ? `${s.label} · ${g.title}` : s.label
      const picks = g.options.filter((o) => o !== s.options[0]).map((o) => ({ s, o }))
      if (!picks.length) continue
      const last = out[out.length - 1]
      if (last?.title === title) last.picks.push(...picks)
      else out.push({ title, picks })
    }
  return out
}

function descsOf(pick: Pick, pages: PageModel[], ctx: LayoutCtx): Desc[] {
  const base = (p: PageModel) => ({ path: p.path, slug: p.slug, pageTitle: p.title })
  if (pick.kind === 'set') {
    const set = pick.page.sets.find((s) => s.key === pick.key)
    if (!set) return []
    const p = pick.page
    return set.options.map((o, i) => ({
      id: `${p.path}|v|${set.key}|${o.value}`,
      cacheId: `${p.path}|v|${set.key}|${o.value}`,
      ...base(p),
      caption: o.label,
      n: i + 1,
      opt: o.label,
      author: o.author,
      kind: 'set' as const,
      setKey: set.key,
      setLabel: set.label,
      setName: set.name,
      setFile: set.file,
      setOptions: set.options,
      option: o.value,
      isDefault: i === 0,
      meta: set.meta ?? undefined,
    }))
  }
  const p = pick.page
  if (pick.kind === 'opt') {
    const set = p.sets.find((s) => s.key === pick.key)
    const opt = set?.options.find((o) => o.value === pick.value)
    if (!set || !opt) return []
    const cacheId = `${p.path}|v|${set.key}|${opt.value}`
    const pin = { setKey: set.key, setLabel: set.label, setOption: opt.value, setOptionLabel: opt.label, meta: set.meta ?? undefined }
    const found = ctx.statesOf(cacheId)
    // Declared nothing: no tiles, and the canvas says so. Until the option has been drawn once (or if it cannot be), there
    // is this one tile: the option as it is.
    if (Array.isArray(found) && !found.length) return []
    if (!Array.isArray(found)) return [{ id: `${cacheId}|probe`, cacheId, ...base(p), caption: 'Default', opt: 'Default', kind: 'default', ...pin }]
    const first = found[0]
    const out: Desc[] = [
      { id: `${cacheId}|s|${first.key}|${first.options[0]}`, cacheId, ...base(p), caption: first.options[0], opt: first.options[0], kind: 'state', stateKey: first.key, stateLabel: first.label, option: first.options[0], ...pin },
    ]
    for (const sec of sectionsOf(found, false))
      for (const { s, o } of sec.picks) {
        const id = `${cacheId}|s|${s.key}|${o}`
        out.push({ id, cacheId: id, ...base(p), caption: o, opt: o, kind: 'state', stateKey: s.key, stateLabel: s.label, option: o, section: sec.title, ...pin })
      }
    return out
  }
  const out: Desc[] = [{ id: `${p.path}|default`, cacheId: `${p.path}|default`, ...base(p), caption: 'Default', kind: 'default' }]
  for (const sec of sectionsOf(p.states, true))
    for (const { s, o } of sec.picks) {
      const id = `${p.path}|s|${s.key}|${o}`
      out.push({ id, cacheId: id, ...base(p), caption: o, kind: 'state', stateKey: s.key, stateLabel: s.label, option: o, section: sec.title })
    }
  return out
}

// The grid: sections one under another, a heading over each that has one, the same columns in all of them.
function build(descs: Desc[], ctx: LayoutCtx, cell: { w: number; h: number }, cols: number, inv: number) {
  const rowGap = GAP + (LABEL + AUTHOR) * inv
  const sections: Desc[][] = []
  descs.forEach((d, i) => (i && d.section === descs[i - 1].section ? sections[sections.length - 1].push(d) : sections.push([d])))
  const tiles: TileBox[] = []
  const heads: Head[] = []
  let y = 0
  sections.forEach((sec, si) => {
    if (si) y += GAP
    if (sec[0].section) {
      heads.push({ text: sec[0].section, x: 0, y })
      y += HEAD * inv
    }
    y += LABEL * inv
    sec.forEach((d, i) => tiles.push({ ...d, x: (i % cols) * (cell.w + GAP), y: y + Math.floor(i / cols) * (cell.h + rowGap), w: cell.w, h: cell.h }))
    const rows = Math.ceil(sec.length / cols)
    y += rows * cell.h + (rows - 1) * rowGap + AUTHOR * inv
  })
  return { tiles, heads, bounds: { w: cols * cell.w + (cols - 1) * GAP, h: y } }
}

function fitOf(b: { w: number; h: number }, ctx: LayoutCtx, byWidth: boolean): Fit {
  const { vp } = ctx
  if (ctx.phone) return { x: 16, y: TOP, z: Math.max(MIN_Z, Math.min(1, (vp.w - 32) / b.w)) }
  const room = vp.h - TOP - PAD
  let z = Math.min(1, (vp.w - PAD * 2) / b.w)
  if (!byWidth) z = Math.min(z, room / b.h)
  z = Math.max(MIN_Z, z)
  const fitsHeight = b.h * z <= room
  return { x: (vp.w - b.w * z) / 2, y: fitsHeight ? TOP + (room - b.h * z) / 2 : TOP, z }
}

export function layoutPick(pick: Pick | null, pages: PageModel[], ctx: LayoutCtx): Layout {
  const descs = pick ? descsOf(pick, pages, ctx) : []
  if (!descs.length) return empty
  const isSet = !!descs[0].setKey
  // Set tiles take their real sizes only once every option has been drawn, so the grid settles once.
  const sizes = isSet ? descs.map((d) => ctx.sizeOf(d.cacheId, d.setKey!)) : []
  const known = isSet && sizes.every(Boolean)
  const dims = descs.map((d, i) => {
    if (!d.setKey) return { w: ctx.win.w, h: ctx.win.h }
    const s = known ? sizes[i]! : d.meta ?? { w: 480, h: 320 }
    return { w: s.w + MARGIN * 2, h: s.h + MARGIN * 2 }
  })
  const cell = { w: Math.max(...dims.map((d) => d.w)), h: Math.max(...dims.map((d) => d.h)) }
  const n = descs.length

  let cols = 1
  if (!ctx.phone) {
    if (isSet) cols = Math.max(1, Math.min(n, Math.round(ctx.vp.w / 400)))
    else {
      // The column count that lets the whole grid fit at the largest zoom.
      let bestZ = -1
      for (let c = 1; c <= n; c++) {
        const z = fitOf(build(descs, ctx, cell, c, 1).bounds, ctx, false).z
        if (z >= bestZ - 0.005) {
          bestZ = Math.max(bestZ, z)
          cols = c
        }
      }
    }
  }

  // Captions keep their on-screen size at the fit zoom, so the room under a tile is sized for it: the
  // largest the layout needs. Zoom afterwards only scales this layout.
  let inv = 1
  let out = build(descs, ctx, cell, cols, inv)
  for (let i = 0; i < 4; i++) {
    inv = Math.max(1, 1 / fitOf(out.bounds, ctx, isSet).z)
    out = build(descs, ctx, cell, cols, inv)
  }
  const fit = fitOf(out.bounds, ctx, isSet)
  inv = Math.max(inv, 1 / fit.z)
  return { ...out, fit, invFit: inv, sig: `${cols}|${cell.w}x${cell.h}|${n}|${ctx.vp.w}x${ctx.vp.h}|${ctx.phone}|${pick ? n : 0}|${descs.map((d) => d.id).join(',')}` }
}
