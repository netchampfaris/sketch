// Snapshots: a rendered frame turned into a static HTML string plus the scroll positions to restore.
import { shallowReactive, shallowRef } from 'vue'
import type { Opt, Reg, VSet } from './state'

export type Crop = { x: number; y: number; w: number; h: number }
export type SetMeta = { key: string; x: number; y: number; w: number; h: number }
export type RegInfo = {
  states: { key: string; label: string; path: string; options: string[] }[]
  sets: { key: string; label: string; name: string; file: string; path: string; options: Opt[] }[]
}
export type Snap = {
  html: string
  crop: Crop
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
  // The last thing shown, as it is written in the URL.
  pick: null as string | null,
  // Whether the Show panel is open on desktop.
  panel: true,
}
// The pages the canvas found, once it has looked (reactive, so the canvas button can follow it).
export const pagesModel = shallowRef<any[] | null>(null)

export const nextFrames = (n = 2) =>
  new Promise<void>((res) => {
    const step = (i: number) => requestAnimationFrame(() => (i <= 1 ? res() : step(i - 1)))
    step(n)
  })

export const errorSnap = (error: string): Snap => ({
  html: '',
  crop: { x: 0, y: 0, w: 0, h: 0 },
  scrolls: [],
  sets: [],
  reg: { states: [], sets: [] },
  error,
})

function union(els: Element[], frame: DOMRect, scrollTop: number): Crop | null {
  const rs = els.map((e) => e.getBoundingClientRect()).filter((r) => r.width || r.height)
  if (!rs.length) return null
  const x = Math.min(...rs.map((r) => r.left)), y = Math.min(...rs.map((r) => r.top))
  return { x: x - frame.left, y: y - frame.top + scrollTop, w: Math.max(...rs.map((r) => r.right)) - x, h: Math.max(...rs.map((r) => r.bottom)) - y }
}

// Scroll the set into view inside its scroll container first, then measure and serialise.
export function capture(frame: HTMLElement, reg: Reg, target: VSet | null): Snap {
  if (target) target.elements()[0]?.scrollIntoView({ block: 'center', inline: 'center' })
  const top = frame.scrollTop
  frame.scrollTop = 0
  frame.scrollLeft = 0
  const fr = frame.getBoundingClientRect()

  const sets: SetMeta[] = []
  for (const s of reg.sets) {
    const c = union(s.elements(), fr, top)
    if (c) sets.push({ key: s.key, ...c })
  }
  let crop: Crop = { x: 0, y: 0, w: fr.width, h: fr.height }
  if (target) {
    const c = union(target.elements(), fr, top)
    if (c) crop = { x: c.x - 24, y: c.y - 24, w: c.w + 48, h: c.h + 48 }
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
    crop,
    scrolls,
    sets,
    reg: {
      states: reg.states.map((s) => ({ key: s.key, label: s.label, path: s.path, options: s.options })),
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
