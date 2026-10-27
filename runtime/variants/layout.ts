// The canvas world for one pick: one even grid of tiles in canvas units (CSS px at 100% zoom). It is computed
// once per view, window size and panel state, with the largest gaps it needs, and zoom never touches it.
import type { Opt } from './state'
import type { Pick } from './picker'

export const GAP = 48
// The caption (and Open page button) under a tile, in on-screen px at the fit zoom.
export const CAPTION = 36
export const PAD = 32
// A set tile shows the set's own box with this much tile background around it.
export const MARGIN = 16
const MIN_Z = 0.05

export type SetMeta = { x: number; y: number; w: number; h: number }
export type PageModel = {
  path: string
  slug: string
  title: string
  states: { key: string; label: string; options: string[] }[]
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
  // The option this tile shows, for its accessible name.
  opt?: string
  kind: 'default' | 'state' | 'set' | 'gap'
  stateKey?: string
  setKey?: string
  // What Make default needs to rewrite the source: the tag's name, its file and the set's options in order.
  setName?: string
  setFile?: string
  setOptions?: Opt[]
  option?: string
  isDefault?: boolean
  gapText?: string
  // Set tiles: the set's box when the page was first drawn.
  meta?: SetMeta
  x: number
  y: number
  w: number
  h: number
}
export type Fit = { x: number; y: number; z: number }
export type Layout = { tiles: TileBox[]; bounds: { w: number; h: number }; fit: Fit; invFit: number; sig: string }
export type LayoutCtx = {
  win: { w: number; h: number }
  // The room the grid has on screen.
  vp: { w: number; h: number }
  phone: boolean
  // The size of one option's own set box once it has been drawn.
  sizeOf: (cacheId: string, setKey: string) => { w: number; h: number } | null
}

type Desc = Omit<TileBox, 'x' | 'y' | 'w' | 'h'>

const empty: Layout = { tiles: [], bounds: { w: 0, h: 0 }, fit: { x: 0, y: 0, z: 1 }, invFit: 1, sig: '' }

function descsOf(pick: Pick, pages: PageModel[]): Desc[] {
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
      kind: 'set' as const,
      setKey: set.key,
      setName: set.name,
      setFile: set.file,
      setOptions: set.options,
      option: o.value,
      isDefault: i === 0,
      meta: set.meta ?? undefined,
    }))
  }
  if (pick.kind === 'state') {
    const name = pick.name
    const out: Desc[] = []
    for (const p of pages) {
      if (!p.states.length) continue
      const s = p.states.find((x) => x.options.slice(1).includes(name))
      if (s) {
        out.push({ id: `f:${p.path}`, cacheId: `${p.path}|s|${s.key}|${name}`, ...base(p), caption: p.title, opt: name, kind: 'state', stateKey: s.key, option: name })
      } else {
        out.push({ id: `gap:${p.path}`, cacheId: '', ...base(p), caption: p.title, kind: 'gap', gapText: 'Not designed yet' })
      }
    }
    return out
  }
  const p = pick.page
  const out: Desc[] = [{ id: `${p.path}|default`, cacheId: `${p.path}|default`, ...base(p), caption: 'Default', kind: 'default' }]
  for (const s of p.states)
    for (const o of s.options.slice(1))
      out.push({ id: `${p.path}|s|${s.key}|${o}`, cacheId: `${p.path}|s|${s.key}|${o}`, ...base(p), caption: o, kind: 'state', stateKey: s.key, option: o })
  return out
}

function build(descs: Desc[], ctx: LayoutCtx, cell: { w: number; h: number }, cols: number, inv: number) {
  const rowGap = GAP + CAPTION * inv
  const rows = Math.ceil(descs.length / cols)
  const tiles: TileBox[] = descs.map((d, i) => ({ ...d, x: (i % cols) * (cell.w + GAP), y: Math.floor(i / cols) * (cell.h + rowGap), w: cell.w, h: cell.h }))
  return { tiles, bounds: { w: cols * cell.w + (cols - 1) * GAP, h: rows * cell.h + (rows - 1) * rowGap + CAPTION * inv } }
}

function fitOf(b: { w: number; h: number }, ctx: LayoutCtx, byWidth: boolean): Fit {
  const { vp } = ctx
  if (ctx.phone) return { x: 16, y: 16, z: Math.max(MIN_Z, Math.min(1, (vp.w - 32) / b.w)) }
  let z = Math.min(1, (vp.w - PAD * 2) / b.w)
  if (!byWidth) z = Math.min(z, (vp.h - PAD * 2) / b.h)
  z = Math.max(MIN_Z, z)
  const fitsHeight = b.h * z <= vp.h - PAD * 2
  return { x: (vp.w - b.w * z) / 2, y: fitsHeight ? (vp.h - b.h * z) / 2 : PAD, z }
}

export function layoutPick(pick: Pick | null, pages: PageModel[], ctx: LayoutCtx): Layout {
  const descs = pick ? descsOf(pick, pages) : []
  if (!descs.length) return empty
  const isSet = descs[0].kind === 'set'
  // Set tiles take their real sizes only once every option has been drawn, so the grid settles once.
  const sizes = isSet ? descs.map((d) => ctx.sizeOf(d.cacheId, d.setKey!)) : []
  const known = isSet && sizes.every(Boolean)
  const dims = descs.map((d, i) => {
    if (d.kind !== 'set') return { w: ctx.win.w, h: ctx.win.h }
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
