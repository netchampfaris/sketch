// Snapshots: a rendered frame turned into a static HTML string plus the scroll positions to restore.
import { shallowReactive, shallowRef } from 'vue'
import { boxIn, lift } from './lift'
import type { DGroup, Opt, Reg, VSet } from './state'

export type Crop = { x: number; y: number; w: number; h: number }
export type SetMeta = { key: string; x: number; y: number; w: number; h: number }
export type RegInfo = {
  states: { key: string; label: string; path: string; options: string[]; groups?: DGroup[]; of?: string }[]
  sets: { key: string; label: string; name: string; file: string; path: string; options: Opt[] }[]
}
export type Snap = {
  html: string
  // The target set was lifted out of the page (lift.ts): `html` carries its marks, and its entry in `sets` is where it
  // sits in the lifted page.
  lifted?: boolean
  scrolls: [number, number, number][]
  sets: SetMeta[]
  reg: RegInfo
  error?: string
}

// Per (tile, lens values, window size), for the session.
export const cache = shallowReactive<Record<string, Snap>>({})
// What the canvas learned about the pages, and the last pan and zoom.
export const session = {
  model: null as any[] | null,
  modelKey: '',
  // Whether the Show panel is open on desktop.
  panel: true,
}
// The pages the canvas found, once it has looked (reactive, so the Demo card's Open canvas can follow it).
export const pagesModel = shallowRef<any[] | null>(null)

export const nextFrames = (n = 2) =>
  new Promise<void>((res) => {
    const step = (i: number) => requestAnimationFrame(() => (i <= 1 ? res() : step(i - 1)))
    step(n)
  })

export const errorSnap = (error: string): Snap => ({
  html: '',
  scrolls: [],
  sets: [],
  reg: { states: [], sets: [] },
  error,
})

// Measure every set as the page lays it out, then lift the target set out of the page (lift.ts) and serialise. A set that
// is the page keeps the whole window. `grow`: a state tile, where the set shows at its full content height (lift.ts).
export function capture(frame: HTMLElement, reg: Reg, target: VSet | null, grow = false): Snap {
  frame.scrollTop = 0
  frame.scrollLeft = 0
  const whole = { x: 0, y: 0, w: frame.offsetWidth, h: frame.offsetHeight }

  const sets: SetMeta[] = []
  for (const s of reg.sets) {
    const c = s.page() ? whole : boxIn(frame, s.elements())
    if (c) sets.push({ key: s.key, ...c })
  }
  let lifted = false
  if (target && !target.page()) {
    const els = target.elements()
    if (els.length) {
      lift(frame, els, grow)
      const c = boxIn(frame, els)
      if (c) {
        const at = sets.findIndex((m) => m.key === target.key)
        if (at >= 0) sets[at] = { key: target.key, ...c }
        else sets.push({ key: target.key, ...c })
        lifted = true
      }
    }
  }

  // Typed text lives in a property, not the markup, so copy it over.
  frame.querySelectorAll('input').forEach((el) => el.setAttribute('value', el.value))
  frame.querySelectorAll('textarea').forEach((el) => (el.textContent = el.value))
  const scrolls: [number, number, number][] = []
  frame.querySelectorAll('*').forEach((el, i) => {
    if (el.scrollTop || el.scrollLeft) scrolls.push([i, el.scrollTop, el.scrollLeft])
  })

  return {
    html: frame.innerHTML,
    lifted,
    scrolls,
    sets,
    reg: {
      states: reg.states.map((s) => ({ key: s.key, label: s.label, path: s.path, options: s.options, groups: s.groups, of: s.of })),
      sets: reg.sets.map((s) => ({ key: s.key, label: s.label, name: s.name, file: s.file, path: s.path, options: s.options() })),
    },
  }
}

export function restoreScrolls(root: HTMLElement, scrolls: [number, number, number][]) {
  if (!scrolls.length) return
  const all = root.querySelectorAll('*')
  for (const [i, t, l] of scrolls) {
    const el = all[i]
    if (el) {
      el.scrollTop = t
      el.scrollLeft = l
    }
  }
}
