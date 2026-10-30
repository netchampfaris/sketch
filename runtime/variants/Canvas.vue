<script setup lang="ts">
// The canvas: one collection at a time (a variant set, a page's states, or one option's component states), picked in "Show".
// The grid is laid out once per view (see layout.ts); zoom and pan only transform it.
import { computed, onBeforeUnmount, onMounted, reactive, ref, shallowRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useElementSize, useEventListener, useMediaQuery, useResizeObserver } from '@vueuse/core'
import { Button, Dropdown, Popover, Tooltip, toast } from 'frappe-ui'
import Frame from './Frame.vue'
import Panel from './Panel.vue'
import Tile from './Tile.vue'
import { bridge, findTile, spotOf, tileExists } from './bridge'
import { landed, placeToasts } from './default'
import type { TileHit, TileSpot } from './bridge'
import { layoutPick } from './layout'
import type { PageModel, StateInfo, TileBox } from './layout'
import { lookAt } from './badges'
import { menuBind } from './menus'
import { fallbackPick, parsePick, pickItems, pickLabel, pickSummary, valueOfPick } from './picker'
import { usePanZoom } from './panzoom'
import { cache, errorSnap, nextFrames, pagesModel, session } from './snapshot'
import type { Snap } from './snapshot'
import {
  choices,
  closeCanvas,
  idOf,
  isChoice,
  mirrorSets,
  mirrorStates,
  nav,
  slugOf,
  slugOfRoute,
  stateOf,
  stateValues,
  states,
  titleOfRoute,
} from './state'
import type { Sandbox } from './state'

const props = defineProps<{ app: any }>()
const route = useRoute()
const router = useRouter()

// Tiles are drawn at the window size the canvas opened at.
const win = { w: window.innerWidth, h: window.innerHeight }
const phone = useMediaQuery('(max-width: 767px)')
// The page the canvas opened over, for the pick it falls back to.
const openedOn = route.path

// App-wide states (Role) are the lenses. There is no picker here: the tiles follow what the Demo pill has, live.
const appStates = computed(() => Object.values(states).filter((s) => s.path === ''))
const lens = () => Object.fromEntries(appStates.value.map((s) => [idOf(s.path, s.key), stateOf(s)]))
const lensStr = computed(() => Object.values(lens()).join('+'))
const keyOf = (cacheId: string) => `${cacheId}|${lensStr.value}|${win.w}x${win.h}`

const model = shallowRef<PageModel[] | null>(null)
// A set Keep only this left with one option stays in Browse while you are on it, and leaves once you pick something else.
const isLone = (s: { options: unknown[] }) => !isChoice(s.options)

// ---- The pick
const raw = computed(() => String([route.query.canvas].flat()[0] ?? ''))
const pick = computed(() => (model.value ? parsePick(raw.value, model.value) : null))
const pickValue = computed(() => (pick.value ? valueOfPick(pick.value) : ''))
watch(
  [model, raw],
  () => {
    if (!model.value) return
    if (pick.value) {
      session.pick = valueOfPick(pick.value)
      return
    }
    const next = fallbackPick(model.value, openedOn)
    if (next) router.replace({ query: { ...route.query, canvas: next } })
  },
  { immediate: true },
)
watch(raw, (r) => {
  const m = model.value
  if (!m || !m.some((p) => p.sets.some((s) => isLone(s) && r !== `set:${p.slug}/${s.key}`))) return
  const next = m.map((p) => ({ ...p, sets: p.sets.filter((s) => !isLone(s) || r === `set:${p.slug}/${s.key}`) }))
  model.value = session.model = pagesModel.value = next
})
// Opening a set is looking at all of its options: the ones a teammate made stop being new (the tiles keep their
// "New" badge until the next visit, so nothing vanishes under the pointer).
watch(
  pick,
  (p) => {
    if (p?.kind !== 'set') return
    lookAt(p.page.sets.find((s) => s.key === p.key)?.options.map((o) => o.value) ?? [])
  },
  { immediate: true },
)
const summary = computed(() => (pick.value ? pickSummary(pick.value) : ''))
// Beside the name in the top-left pill: a set's option count ("12 options"), without the page it is on; else the summary.
const countText = computed(() => {
  const p = pick.value
  if (p?.kind !== 'set') return summary.value
  const n = p.page.sets.find((s) => s.key === p.key)?.options.length ?? 0
  return `${n} ${n === 1 ? 'option' : 'options'}`
})
// One option's component states: the set, the option, and the words its states are declared with (`of`).
const optView = computed(() => {
  const p = pick.value
  if (p?.kind !== 'opt') return null
  const set = p.page.sets.find((s) => s.key === p.key)
  const opt = set?.options.find((o) => o.value === p.value)
  return set && opt ? { page: p.page, set, opt, of: `${set.label}/${opt.label}`, cacheId: `${p.page.path}|v|${set.key}|${opt.value}` } : null
})
const setViewValue = computed(() => (optView.value ? `set:${optView.value.page.slug}/${optView.value.set.key}` : ''))
const triggerLabel = computed(() => (pick.value ? pickLabel(pick.value) : model.value ? 'Choose' : 'Loading'))
const nothing = computed(() => !!model.value && !pickItems(model.value).length)
const items = computed(() => (model.value ? pickItems(model.value) : []))

// Desktop: a panel on the right, open or not for the whole session. Phone: the Show dropdown.
const PANEL_W = 312
const panelOpen = ref(session.panel)
const panelShown = computed(() => !phone.value && panelOpen.value)
const setPanel = (o: boolean) => (panelOpen.value = session.panel = o)
const pickerOpen = ref(false)
function choose(v: string) {
  pickerOpen.value = false
  if (!v || v === pickValue.value) return
  router.replace({ query: { ...route.query, canvas: v } })
}

// ---- The layout: computed from the view, the window and the panel, never from the zoom.
const vp = ref<HTMLElement | null>(null)
const root = ref<HTMLElement | null>(null)
// The canvas fills the window and the panel floats over it. Fit and columns use only the room left of the
// panel, so at fit nothing sits under it; panned or zoomed, tiles slide under it whole.
const fullSize = ref({ w: win.w, h: win.h })
useResizeObserver(vp, ([e]) => {
  fullSize.value = { w: Math.round(e.contentRect.width), h: Math.round(e.contentRect.height) }
})
const vpSize = computed(() => ({ w: fullSize.value.w - (panelShown.value ? PANEL_W : 0), h: fullSize.value.h }))
// The states a drawn option declared with `of` naming it: null until it is drawn.
function statesOfOption(cacheId: string): StateInfo[] | 'error' | null {
  const v = optView.value
  const snap = cache[keyOf(cacheId)]
  if (!v || !snap) return null
  if (snap.error) return 'error'
  return snap.reg.states.filter((s) => s.path === v.page.path && !!s.of && slugOf(s.of) === slugOf(v.of))
}
const layout = computed(() =>
  layoutPick(pick.value, model.value ?? [], {
    win,
    vp: vpSize.value,
    phone: phone.value,
    sizeOf: (id, key) => {
      const r = cache[keyOf(id)]?.sets.find((s) => s.key === key)
      return r ? { w: r.w, h: r.h } : null
    },
    statesOf: (id) => statesOfOption(id),
  }),
)
const pz = usePanZoom(() => vp.value)
// The zoom pill's width, so the toolbar parked bottom right stands left of it (Annotate.vue).
const zoomPill = ref<HTMLElement | null>(null)
const { width: zoomW } = useElementSize(zoomPill, { width: 0, height: 0 }, { box: 'border-box' })
watch(zoomW, (w) => (bridge.corner = w ? w + 8 : 0), { immediate: true })
const { view } = pz
// Captions never grow past their size at the fit zoom, so the room the layout gave them always holds.
const ls = computed(() => Math.min(1 / view.z, layout.value.invFit))

// ---- Drawing: one offscreen render at a time, in idle time, tiles in view first.
type Job = { n: number; path: string; sandbox: Sandbox; targetSet?: string | null }
const job = shallowRef<Job | null>(null)
let seq = 0
let pending: ((s: Snap) => void) | null = null
let alive = true

const makeSandbox = (t: Partial<TileBox> | null, live = false): Sandbox => {
  const sb = {
    states: lens() as Record<string, string>,
    variants: {} as Record<string, string>,
    reg: { states: [], sets: [] },
    live,
  }
  if (t?.kind === 'state') sb.states[idOf(t.path!, t.stateKey!)] = t.option!
  if (t?.kind === 'set') sb.variants[idOf(t.path!, t.setKey!)] = t.option!
  // A component state: the page with that option showing, and then the state.
  if (t?.setOption) sb.variants[idOf(t.path!, t.setKey!)] = t.setOption
  return reactive({ ...sb, reg: sb.reg as any })
}

function runJob(path: string, sandbox: Sandbox, targetSet?: string | null) {
  return new Promise<Snap>((resolve) => {
    const timer = setTimeout(() => finish(errorSnap('Timed out while drawing')), 6000)
    const finish = (s: Snap) => {
      clearTimeout(timer)
      pending = null
      job.value = null
      resolve(s)
    }
    pending = finish
    job.value = { n: ++seq, path, sandbox, targetSet }
  })
}
const onReady = (s: Snap) => pending?.(s)
const onError = (msg: string) => pending?.(errorSnap(msg))
const idle = () =>
  new Promise<void>((r) => ('requestIdleCallback' in window ? (window as any).requestIdleCallback(() => r(), { timeout: 250 }) : setTimeout(r, 16)))

async function discover() {
  const key = `${win.w}x${win.h}`
  if (session.model && session.modelKey === key) {
    model.value = session.model
    pagesModel.value = session.model
    return
  }
  const records = (router.options.routes as any[]).filter((r) => r.component && !r.path.includes(':'))
  const pages: PageModel[] = []
  const here = raw.value
  for (const r of records) {
    if (!alive) return
    const snap = await runJob(r.path, makeSandbox(null))
    cache[keyOf(`${r.path}|default`)] = snap
    const sets = snap.reg.sets
      .filter((s) => s.path === r.path && (isChoice(s.options) || here === `set:${slugOfRoute(r)}/${s.key}`))
      .map((s) => ({ key: s.key, label: s.label, name: s.name, file: s.file, options: s.options, meta: snap.sets.find((m) => m.key === s.key) ?? null }))
    // A component state belongs to its set option, and shows there. One whose option is no longer in a set (after Keep only
    // this) shows on its page.
    const lives = (of: string) => sets.some((s) => s.options.some((o) => slugOf(`${s.label}/${o.label}`) === slugOf(of)))
    pages.push({
      path: r.path,
      slug: slugOfRoute(r),
      title: titleOfRoute(r),
      states: snap.reg.states
        .filter((s) => s.path === r.path && (!s.of || !lives(s.of)))
        .map((s) => ({ key: s.key, label: s.label, options: s.options, groups: s.groups, of: s.of })),
      sets,
    })
    // Page order for sets: top to bottom, then left to right.
    const last = pages[pages.length - 1]
    last.sets.sort((a, b) => (a.meta?.y ?? 1e9) - (b.meta?.y ?? 1e9) || (a.meta?.x ?? 0) - (b.meta?.x ?? 0))
  }
  session.model = pages
  session.modelKey = key
  pagesModel.value = pages
  model.value = pages
}

const visible = new Set<string>()
let pumping = false
const missing = () => {
  const seen = new Set<string>()
  return layout.value.tiles.filter((t) => {
    const k = keyOf(t.cacheId)
    if (cache[k] || seen.has(k)) return false
    seen.add(k)
    return true
  })
}
async function pump() {
  if (pumping || !model.value) return
  pumping = true
  try {
    while (alive) {
      const todo = missing()
      const t = todo.find((x) => visible.has(x.id)) ?? todo[0]
      if (!t) break
      const k = keyOf(t.cacheId)
      const snap = await runJob(t.path, makeSandbox(t), t.setKey ?? null)
      if (!alive) return
      cache[k] = snap
      await idle()
    }
  } finally {
    pumping = false
  }
}
const onNear = (id: string, near: boolean) => {
  if (near) {
    visible.add(id)
    pump()
  } else visible.delete(id)
}

const drawn_ = computed(() => layout.value.tiles)
const total = computed(() => new Set(drawn_.value.map((t) => keyOf(t.cacheId))).size)
const drawn = computed(() => {
  const keys = new Set(drawn_.value.map((t) => keyOf(t.cacheId)))
  let n = 0
  keys.forEach((k) => cache[k] && n++)
  return n
})
const drawing = computed(() => !!model.value && drawn.value < total.value)


watch([() => layout.value.tiles.length, lensStr, pickValue], () => pump())



// ---- Live tile
const liveId = ref<string | null>(null)
const liveTile = computed(() => layout.value.tiles.find((t) => t.id === liveId.value) ?? null)
const liveSandbox = computed(() => (liveTile.value ? makeSandbox(liveTile.value, true) : undefined))
watch([lensStr, () => pickValue.value], () => (liveId.value = null))
// A write that reloaded the page (Make default, Keep only this, Undo) leaves the option it landed on ringed once it is drawn.
// Only once its own frame has measured it: until then the live tile shows the slice the default option measured, which on
// another option is the wrong part of the page.
const landedTile = computed(() => {
  const l = landed.value
  const t = l && layout.value.tiles.find((x) => x.kind === 'set' && x.setName === l.set && x.option === l.option)
  return t && cache[keyOf(t.cacheId)] ? t : null
})
watch(
  [landedTile, pickValue],
  () => {
    const t = landedTile.value
    if (!t) return
    liveId.value = t.id
    landed.value = null
  },
  { immediate: true },
)

// ---- One option's component states: the tile menu's States opens them, ← and the set crumb go back up.
function openStates(t: TileBox) {
  const page = model.value?.find((p) => p.path === t.path)
  if (!page || !t.setKey || !t.option) return
  // A new history entry, so the browser's Back goes up one level.
  router.push({ query: { ...route.query, canvas: `opt:${page.slug}/${t.setKey}/${t.option}` } })
}
function goUp() {
  const target = setViewValue.value
  if (!target) return
  // Reached by States from that set: step back through history, so Back and Forward still mean something.
  if (decodeURIComponent(String(history.state?.back ?? '')).includes(`canvas=${target}`)) router.back()
  else router.replace({ query: { ...route.query, canvas: target } })
}

// Nothing declared for the option: the view is one line and a way to ask the agent for it. The note is the one the Note
// tool makes, on the option's own tile of its set; while it waits for the agent the view says so.
const OPENING = 'Build the states for'
const emptyView = computed(() => !!optView.value && Array.isArray(statesOfOption(optView.value.cacheId)) && !layout.value.tiles.length)
const optSpot = computed<TileSpot | null>(() => {
  const v = optView.value
  const tile = { kind: 'set' as const, view: setViewValue.value, page: v?.page.title ?? '', group: v?.set.label ?? '', groupKey: v?.set.key ?? '', option: v?.opt.value ?? '', optionLabel: v?.opt.label ?? '' }
  return v ? { route: v.page.path, tile } : null
})
const pendingNote = computed(() => (optSpot.value ? (bridge.pendingNote?.(optSpot.value, OPENING) ?? null) : null))
const asking = ref(false)
async function askAgent() {
  const v = optView.value
  if (!v || !optSpot.value || !bridge.addNote || asking.value) return
  asking.value = true
  try {
    await bridge.addNote(optSpot.value, `${OPENING} ${v.set.label} · ${v.opt.label}${v.set.file ? ` (${v.set.file})` : ''}. Follow the States section of the Sketch skill.`)
  } catch (e) {
    toast.error(`Could not add the note: ${(e as Error).message}. Try again.`)
  } finally {
    asking.value = false
  }
}
const undoAsk = () => pendingNote.value && bridge.removeNote?.(pendingNote.value)

function openPage(t: TileBox) {
  nav.pushed = false
  // A new history entry on top of the canvas, so Back returns to it. The picks are set once it has landed,
  // so nothing rewrites the URL while the navigation is pending.
  router.push({ path: t.path }).then(() => {
    if (t.kind === 'state') stateValues[idOf(t.path, t.stateKey!)] = t.option!
    if (t.kind === 'set') choices[idOf(t.path, t.setKey!)] = t.option!
    if (t.setOption) choices[idOf(t.path, t.setKey!)] = t.setOption
    mirrorStates(router)
    mirrorSets(router)
  })
}

// ---- View: fit when the pick, the window or the panel changes (or the layout settles and nobody has moved).
const viewKey = computed(() => `${pickValue.value}|${vpSize.value.w}x${vpSize.value.h}|${phone.value}`)
function applyFit() {
  Object.assign(view, layout.value.fit)
  pz.flags.touched = false
}
watch(
  [viewKey, () => layout.value.sig],
  ([k], old) => {
    if (!layout.value.tiles.length) return
    if (!old || k !== old[0] || !pz.flags.touched) applyFit()
  },
  { immediate: true, flush: 'post' },
)

// Dot spacing follows the zoom; zoomed out it keeps doubling (never under 14px on screen) so the dots don't bunch up.
const dot = computed(() => {
  let d = 20 * view.z
  while (d < 14) d *= 2
  return d
})
// The dots read about 1.1:1 against the canvas in light and dark alike: measure the theme and thin them out.
const dotMix = ref(100)
function measureDots() {
  if (!root.value) return
  const cv = document.createElement('canvas')
  cv.width = cv.height = 1
  const g = cv.getContext('2d', { willReadFrequently: true })
  if (!g) return
  const lum = (css: string) => {
    g.clearRect(0, 0, 1, 1)
    g.fillStyle = '#000'
    g.fillStyle = css
    g.fillRect(0, 0, 1, 1)
    const [r, gg, b] = [...g.getImageData(0, 0, 1, 1).data].map((v) => {
      const s = v / 255
      return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
    })
    return 0.2126 * r + 0.7152 * gg + 0.0722 * b
  }
  const probe = document.createElement('div')
  probe.className = 'bg-surface-gray-3'
  root.value.appendChild(probe)
  const dotL = lum(getComputedStyle(probe).backgroundColor)
  probe.remove()
  const bgL = lum(getComputedStyle(root.value).backgroundColor)
  const ratio = (Math.max(dotL, bgL) + 0.05) / (Math.min(dotL, bgL) + 0.05)
  dotMix.value = Math.round(Math.min(1, 0.1 / Math.max(ratio - 1, 0.01)) * 100)
}
const pct = computed(() => Math.round(view.z * 100))
const zoomOptions = [
  { label: 'Zoom to fit', onClick: () => applyFit() },
  ...[0.5, 1, 2].map((z) => ({ label: `${z * 100}%`, onClick: () => pz.zoomTo(z) })),
]

// ---- Keys, scroll lock, focus
useEventListener(document, 'keydown', (e: KeyboardEvent) => {
  if (e.key === 'Escape') {
    // A tool picking tiles takes its own Escape: it closes its box, then puts the tool down.
    if (e.defaultPrevented || bridge.tool) return
    if (pickerOpen.value || document.querySelector('.menu-content, [role="dialog"]:not([data-sketch-ui="canvas"])')) return
    if (liveId.value) liveId.value = null
    else if (optView.value) goUp()
    else closeCanvas(router)
    return
  }
  const t = e.target as HTMLElement
  if (t.closest?.('input, textarea, select, [contenteditable="true"]') || e.metaKey || e.ctrlKey || e.altKey) return
  if (liveId.value && t.closest?.('[data-live]')) return
  if (e.key === '+' || e.key === '=') pz.zoomBy(1.25)
  else if (e.key === '-') pz.zoomBy(1 / 1.25)
  else if (e.code === 'Digit1' && e.shiftKey) applyFit()
})

let detach = () => {}
let themeWatch: MutationObserver | null = null
const prevOverflow = document.body.style.overflow
onMounted(() => {
  bridge.open = true
  bridge.reveal = reveal
  bridge.pointOf = pointOf
  document.body.style.overflow = 'hidden'
  if (vp.value) detach = pz.attach(vp.value)
  root.value?.focus()
  measureDots()
  themeWatch = new MutationObserver(measureDots)
  themeWatch.observe(document.documentElement, { attributes: true })
  discover().then(() => pump())
})
onBeforeUnmount(() => {
  landed.value = null
  bridge.open = false
  bridge.reveal = null
  bridge.pointOf = null
  bridge.model = null
  bridge.tiles = []
  bridge.reserve = 0
  bridge.corner = 0
  document.documentElement.style.removeProperty('--sketch-panel-w')
  bridge.view = ''
  alive = false
  pending?.(errorSnap('Closed'))
  detach()
  themeWatch?.disconnect()
  document.body.style.overflow = prevOverflow
  const opener = nav.opener
  nav.pushed = false
  setTimeout(() => opener?.focus?.(), 0)
})

function onViewportClick(e: MouseEvent) {
  if (pz.moved()) return
  // The clicked element may already be gone (an error box is replaced by the live render), so look at the path.
  const path = e.composedPath() as HTMLElement[]
  if (!path.some((n) => n.hasAttribute?.('data-tile') || n.hasAttribute?.('data-live'))) liveId.value = null
}
function activate(t: TileBox, e?: MouseEvent | KeyboardEvent) {
  const tool = bridge.tool
  if (!tool || !e) {
    liveId.value = t.id
    return
  }
  // Comment or Note: a click drops a pin on the tile, where the pointer is as a fraction of the tile.
  if (pz.moved() || !bridge.pick) return
  const spot = spotOf(t, pickValue.value)
  if (!spot) return
  const r = (e.currentTarget as HTMLElement).getBoundingClientRect()
  const pointer = e instanceof MouseEvent && e.detail > 0
  const x = pointer ? e.clientX : r.left + r.width / 2
  const y = pointer ? e.clientY : r.top + r.height / 2
  const clamp01 = (n: number) => Math.min(1, Math.max(0, n))
  bridge.pick({ ...spot, fx: clamp01((x - r.left) / (r.width || 1)), fy: clamp01((y - r.top) / (r.height || 1)), x, y } satisfies TileHit)
}

// ---- Comments and notes: what the toolbar asks of the canvas
const until = (ok: () => boolean, ms = 4000) =>
  new Promise<boolean>((resolve) => {
    const t0 = Date.now()
    const tick = () => (ok() ? resolve(true) : Date.now() - t0 > ms ? resolve(false) : setTimeout(tick, 50))
    tick()
  })
const tileBox = (spot: TileSpot) => findTile(layout.value.tiles, spot, pickValue.value)
function pointOf(spot: TileSpot, at: { fx: number; fy: number }) {
  const t = tileBox(spot)
  const el = t ? [...(root.value?.querySelectorAll<HTMLElement>('[data-tile-id]') ?? [])].find((n) => n.dataset.tileId === t.id) : null
  if (!el) return null
  const r = el.getBoundingClientRect()
  return { x: r.left + at.fx * r.width, y: r.top + at.fy * r.height }
}
// The view a tile can be found in: its set, else the view it was pinned in, else its page.
function viewFor(spot: TileSpot): string {
  const pages = model.value ?? []
  const page = pages.find((p) => p.path === spot.route)
  if (spot.tile.kind === 'set' && page) return `set:${page.slug}/${spot.tile.groupKey}`
  if (spot.tile.view && parsePick(spot.tile.view, pages)) return spot.tile.view
  return `page:${spot.route}`
}
// Bring a tile into view and give the screen point of a spot on it. Null when the canvas no longer has the tile.
async function reveal(spot: TileSpot, at = { fx: 0.5, fy: 0.5 }) {
  if (!(await until(() => !!model.value))) return null
  if (tileExists(model.value, spot) === false) return null
  if (!tileBox(spot)) {
    const v = viewFor(spot)
    if (v !== pickValue.value) router.replace({ query: { ...route.query, canvas: v } })
    if (!(await until(() => !!tileBox(spot)))) return null
  }
  const t = tileBox(spot)!
  // The tile in the middle of what the panel leaves open; a tile bigger than that is centred on the spot instead.
  const w = fullSize.value.w - (panelShown.value ? PANEL_W : 0)
  const h = fullSize.value.h
  const fits = t.w * view.z <= w && t.h * view.z <= h
  const cx = fits ? t.x + t.w / 2 : t.x + at.fx * t.w
  const cy = fits ? t.y + t.h / 2 : t.y + at.fy * t.h
  view.x = w / 2 - cx * view.z
  view.y = h / 2 - cy * view.z
  pz.flags.touched = true
  await nextFrames(2)
  return pointOf(spot, at)
}

watch(pickValue, (v) => (bridge.view = v), { immediate: true })
watch(() => view.z, (z) => (bridge.zoom = z), { immediate: true })
watch(model, (m) => (bridge.model = m), { immediate: true })
watch(phone, (p) => (bridge.phone = p), { immediate: true })
watch(() => layout.value.tiles, (t) => (bridge.tiles = t), { immediate: true })
watch(
  panelShown,
  (open) => {
    bridge.panelOpen = open
    bridge.reserve = open ? PANEL_W : 0
    // Toasts stand left of the panel (default.ts): it is 12px off the right edge and PANEL_W - 24 wide.
    placeToasts()
    if (open) document.documentElement.style.setProperty('--sketch-panel-w', `${PANEL_W - 12}px`)
    else document.documentElement.style.removeProperty('--sketch-panel-w')
  },
  { immediate: true },
)
// A tool in hand means clicks on tiles are for pins, not for opening a tile live.
watch(
  () => bridge.tool,
  (tool) => tool && (liveId.value = null),
)
</script>

<template>
  <div
    ref="root"
    data-sketch-ui="canvas"
    role="dialog"
    aria-modal="true"
    aria-label="Canvas"
    tabindex="-1"
    class="fixed inset-0 z-[60] flex flex-col bg-surface-gray-1 outline-none"
  >
    <div class="relative min-h-0 flex-1">
      <div
        ref="vp"
        class="absolute inset-y-0 left-0 cursor-grab touch-none overflow-hidden"
        :style="{
          right: '0',
          '--z': view.z,
          '--inv': 1 / view.z,
          '--ls': ls,
          backgroundImage: `radial-gradient(circle, color-mix(in srgb, var(--surface-gray-3) ${dotMix}%, transparent) 1px, transparent 1.5px)`,
          backgroundSize: `${dot}px ${dot}px`,
          backgroundPosition: `${view.x}px ${view.y}px`,
        }"
        @click="onViewportClick"
      >
        <div class="absolute left-0 top-0 origin-top-left" :style="{ transform: `translate(${view.x}px, ${view.y}px) scale(${view.z})` }">
          <Tile
            v-for="t in layout.tiles"
            :key="t.id"
            :tile="t"
            :snap="cache[keyOf(t.cacheId)]"
            :live="liveId === t.id"
            :sandbox="liveId === t.id ? liveSandbox : undefined"
            :app="app"
            :win="win"
            @activate="(e) => activate(t, e)"
            @open-page="openPage(t)"
            @open-states="openStates(t)"
            @near="(n: boolean) => onNear(t.id, n)"
          />
          <!-- The headings over the sections of tiles, laid out at 1x and scaled like the captions. -->
          <div
            v-for="h in layout.heads"
            :key="h.text"
            role="heading"
            aria-level="2"
            class="pointer-events-none absolute origin-top-left select-none truncate text-base font-medium text-ink-gray-8"
            :style="{ left: h.x + 'px', top: h.y + 'px', width: `calc(${layout.bounds.w}px / var(--ls))`, transform: 'scale(var(--ls))', lineHeight: '24px' }"
          >
            {{ h.text }}
          </div>
          <!-- Comment or note pins, drawn by the toolbar in the world's own coordinates, so they stay on their tile. -->
          <component :is="bridge.Pins" v-if="bridge.Pins" :tiles="layout.tiles" :zoom="view.z" :view="pickValue" />
        </div>

        <div v-if="nothing" data-ui class="absolute inset-0 flex items-center justify-center text-center">
          <p class="text-base text-ink-gray-7">Nothing to show yet. Add a state or a variant set to a page.</p>
        </div>
      </div>

      <!-- An option with no states built: say so, and offer the agent. -->
      <div v-if="emptyView" data-ui class="pointer-events-none absolute inset-y-0 left-0 flex flex-col items-center justify-center gap-2 px-6 text-center" :style="{ right: panelShown ? `${PANEL_W}px` : '0' }">
        <template v-if="pendingNote">
          <p class="text-base text-ink-gray-8">Added to your notes for the agent.</p>
          <p class="text-p-sm text-ink-gray-5">Tell your agent to apply your notes.</p>
          <Button class="pointer-events-auto" variant="ghost" label="Undo" @click="undoAsk" />
        </template>
        <template v-else>
          <p class="text-base text-ink-gray-8">No states built yet</p>
          <Button v-if="bridge.canNote && bridge.addNote" class="pointer-events-auto" variant="subtle" theme="gray" label="Ask agent" :loading="asking" @click="askAgent" />
        </template>
      </div>

      <!-- Top left: the way back, and what the canvas shows. On a phone the name opens the Show list. It sits above the
           tiles and pins (z-10 is the panel's; a box or menu opens in a layer above the canvas). -->
      <div
        data-ui
        data-canvas-title
        class="absolute left-3 top-3 z-10 flex h-9 min-w-0 items-center gap-1 rounded-6 border border-outline-gray-2 bg-surface-base p-1"
        :style="{ maxWidth: `calc(100% - ${panelShown ? PANEL_W + 12 : 24}px)` }"
      >
        <Tooltip text="Back (Esc)">
          <Button class="shrink-0" variant="ghost" icon="lucide-arrow-left" aria-label="Back" @click="optView ? goUp() : closeCanvas(router)" />
        </Tooltip>
        <!-- One option's states: "Supplier card › Compact › States". The set goes back up; on a phone only the option and what it shows. -->
        <div v-if="optView" data-canvas-crumbs class="flex min-w-0 items-center gap-1 pl-1 pr-2 text-base">
          <template v-if="!phone">
            <button type="button" class="min-w-0 truncate text-ink-gray-5 hover:text-ink-gray-8" :title="optView.set.label" @click="goUp">{{ optView.set.label }}</button>
            <span class="lucide-chevron-right size-3.5 shrink-0 text-ink-gray-4" aria-hidden="true" />
          </template>
          <span class="min-w-0 truncate text-ink-gray-8" :title="optView.opt.label">{{ optView.opt.label }}</span>
          <span class="lucide-chevron-right size-3.5 shrink-0 text-ink-gray-4" aria-hidden="true" />
          <span class="shrink-0 text-ink-gray-8">States</span>
        </div>
        <Popover v-else-if="phone" v-model:open="pickerOpen" side="bottom" align="start" :offset="8" :collision-padding="12" class="min-w-0 flex-1">
          <template #trigger>
            <div class="min-w-0">
            <Button variant="ghost" class="w-full max-w-full justify-start" aria-label="Show on the canvas">
              <span class="flex w-full min-w-0 items-center gap-1.5">
                <span class="truncate text-ink-gray-8">{{ triggerLabel }}</span>
                <span v-if="countText" class="shrink-0 text-p-sm text-ink-gray-5">{{ countText }}</span>
                <span class="lucide-chevron-down size-3.5 shrink-0 text-ink-gray-5" aria-hidden="true" />
              </span>
            </Button>
            </div>
          </template>
          <Panel embedded :items="items" :selected="pickValue" style="width: calc(100vw - 24px)" @choose="choose" />
        </Popover>
        <div v-else class="flex min-w-0 items-center gap-1.5 pl-1 pr-2">
          <span class="truncate text-base text-ink-gray-8">{{ triggerLabel }}</span>
          <span v-if="countText" class="shrink-0 text-p-sm text-ink-gray-5">{{ countText }}</span>
          <span v-if="drawing" class="shrink-0 pl-1.5 text-p-sm tabular-nums text-ink-gray-5">Drawing {{ drawn }} of {{ total }}</span>
        </div>
      </div>

      <!-- Bottom right: zoom, left of the panel when it is open. -->
      <div
        ref="zoomPill"
        data-ui
        data-canvas-zoom
        class="absolute bottom-3 z-10 flex h-9 items-center rounded-6 border border-outline-gray-2 bg-surface-base p-1"
        :style="{ right: `${panelShown ? PANEL_W : 12}px` }"
      >
        <Button variant="ghost" icon="lucide-minus" aria-label="Zoom out" @click="pz.zoomBy(1 / 1.25)" />
        <Dropdown v-bind="menuBind('zoom')" :options="zoomOptions">
          <Button variant="ghost" class="w-14 text-p-sm tabular-nums" aria-label="Zoom">{{ pct }}%</Button>
        </Dropdown>
        <Button variant="ghost" icon="lucide-plus" aria-label="Zoom in" @click="pz.zoomBy(1.25)" />
      </div>

      <Panel v-if="panelShown" :items="items" :selected="pickValue" @choose="choose" @hide="setPanel(false)" />
      <!-- Where the hide button sits in the open panel, so the icon stays put when toggled. -->
      <div
        v-else-if="!phone"
        data-ui
        class="absolute right-6 top-6 z-10 rounded-[8px] bg-surface-elevation-2 shadow-sm ring-1 ring-outline-gray-2"
      >
        <Tooltip text="Show panel">
          <Button variant="ghost" icon="lucide-panel-right" aria-label="Show panel" @click="setPanel(true)" />
        </Tooltip>
      </div>
    </div>
  </div>

  <Frame
    v-if="job"
    :key="job.n"
    mode="offscreen"
    :app="app"
    :path="job.path"
    :w="win.w"
    :h="win.h"
    :sandbox="job.sandbox"
    :target-set="job.targetSet"
    @ready="onReady"
    @error="onError"
  />
</template>
