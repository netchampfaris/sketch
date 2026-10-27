<script setup lang="ts">
// The canvas: one collection at a time (a variant set, a state across pages, or a page), picked in "Show".
// The grid is laid out once per view (see layout.ts); zoom and pan only transform it.
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, shallowRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useEventListener, useMediaQuery, useResizeObserver } from '@vueuse/core'
import { Button, Dropdown, Popover, Tooltip } from 'frappe-ui'
import Frame from './Frame.vue'
import LensMenu from './LensMenu.vue'
import Panel from './Panel.vue'
import Tile from './Tile.vue'
import { layoutPick } from './layout'
import type { PageModel, TileBox } from './layout'
import { fallbackPick, parsePick, pickItems, pickLabel, pickSummary, valueOfPick } from './picker'
import { usePanZoom } from './panzoom'
import { cache, errorSnap, pagesModel, session } from './snapshot'
import type { Snap } from './snapshot'
import {
  choices,
  closeCanvas,
  idOf,
  mirrorSets,
  mirrorStates,
  nav,
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

// App-wide states are the lenses.
const appStates = computed(() => Object.values(states).filter((s) => s.path === ''))
const lens = () => Object.fromEntries(appStates.value.map((s) => [idOf(s.path, s.key), stateOf(s)]))
const lensStr = computed(() => Object.values(lens()).join('+'))
const keyOf = (cacheId: string) => `${cacheId}|${lensStr.value}|${win.w}x${win.h}`

const model = shallowRef<PageModel[] | null>(null)

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
const summary = computed(() => (pick.value && model.value ? pickSummary(pick.value, model.value) : ''))
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
const fullSize = ref({ w: win.w, h: win.h - (phone.value ? 96 : 48) })
useResizeObserver(vp, ([e]) => {
  fullSize.value = { w: Math.round(e.contentRect.width), h: Math.round(e.contentRect.height) }
})
const vpSize = computed(() => ({ w: fullSize.value.w - (panelShown.value ? PANEL_W : 0), h: fullSize.value.h }))
const layout = computed(() =>
  layoutPick(pick.value, model.value ?? [], {
    win,
    vp: vpSize.value,
    phone: phone.value,
    sizeOf: (id, key) => {
      const r = cache[keyOf(id)]?.sets.find((s) => s.key === key)
      return r ? { w: r.w, h: r.h } : null
    },
  }),
)
const pz = usePanZoom(() => vp.value)
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
  for (const r of records) {
    if (!alive) return
    const snap = await runJob(r.path, makeSandbox(null))
    cache[keyOf(`${r.path}|default`)] = snap
    pages.push({
      path: r.path,
      slug: slugOfRoute(r),
      title: titleOfRoute(r),
      states: snap.reg.states.filter((s) => s.path === r.path).map((s) => ({ key: s.key, label: s.label, options: s.options })),
      sets: snap.reg.sets
        .filter((s) => s.path === r.path)
        .map((s) => ({ key: s.key, label: s.label, name: s.name, file: s.file, options: s.options, meta: snap.sets.find((m) => m.key === s.key) ?? null })),
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
    if (t.kind === 'gap') return false
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
      const snap = await runJob(t.path, makeSandbox(t), t.kind === 'set' ? t.setKey : null)
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

const drawn_ = computed(() => layout.value.tiles.filter((t) => t.kind !== 'gap'))
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

function openPage(t: TileBox) {
  nav.pushed = false
  // A new history entry on top of the canvas, so Back returns to it. The picks are set once it has landed,
  // so nothing rewrites the URL while the navigation is pending.
  router.push({ path: t.path }).then(() => {
    if (t.kind === 'state') stateValues[idOf(t.path, t.stateKey!)] = t.option!
    if (t.kind === 'set') choices[idOf(t.path, t.setKey!)] = t.option!
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
    if (pickerOpen.value || document.querySelector('.menu-content, [role="dialog"]:not([data-sketch-ui="canvas"])')) return
    if (liveId.value) liveId.value = null
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
  document.body.style.overflow = 'hidden'
  if (vp.value) detach = pz.attach(vp.value)
  root.value?.focus()
  measureDots()
  themeWatch = new MutationObserver(measureDots)
  themeWatch.observe(document.documentElement, { attributes: true })
  discover().then(() => {
    pump()
    // Desktop: the search is where you start, so ↑/↓ work straight away.
    nextTick(() => document.querySelector<HTMLElement>('[data-canvas-panel] input')?.focus())
  })
})
onBeforeUnmount(() => {
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
function activate(t: TileBox) {
  liveId.value = t.id
}
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
    <div v-if="!phone" data-ui class="flex h-12 shrink-0 items-center gap-1 border-b border-outline-gray-1 bg-surface-base px-3">
      <Tooltip text="Close (Esc)">
        <Button variant="ghost" icon="lucide-x" aria-label="Close canvas" @click="closeCanvas(router)" />
      </Tooltip>
      <div class="ml-2 flex min-w-0 items-baseline gap-2">
        <span class="truncate text-base font-medium text-ink-gray-8">{{ triggerLabel }}</span>
        <span v-if="summary" class="truncate text-p-sm text-ink-gray-5">{{ summary }}</span>
      </div>
      <div class="ml-auto flex items-center gap-3">
        <span v-if="drawing" class="text-p-sm tabular-nums text-ink-gray-5">Drawing {{ drawn }} of {{ total }}</span>
        <LensMenu v-for="s in appStates" :key="s.key" :state="s" />
        <div class="flex items-center gap-1">
          <Button variant="ghost" icon="lucide-minus" aria-label="Zoom out" @click="pz.zoomBy(1 / 1.25)" />
          <Dropdown :options="zoomOptions">
            <Button variant="ghost" class="w-14 text-p-sm tabular-nums" aria-label="Zoom">{{ pct }}%</Button>
          </Dropdown>
          <Button variant="ghost" icon="lucide-plus" aria-label="Zoom in" @click="pz.zoomBy(1.25)" />
        </div>
      </div>
    </div>

    <div v-else data-ui class="flex shrink-0 flex-col gap-1 border-b border-outline-gray-1 bg-surface-base px-2 py-1">
      <div class="flex items-center gap-1">
        <Tooltip text="Close (Esc)">
          <Button variant="ghost" icon="lucide-x" aria-label="Close canvas" @click="closeCanvas(router)" />
        </Tooltip>
        <Popover v-model:open="pickerOpen" side="bottom" align="start" :offset="4" :collision-padding="8" match-trigger-width class="min-w-0 flex-1">
          <template #trigger>
            <div class="min-w-0 flex-1">
              <Button variant="subtle" class="w-full justify-between" aria-label="Show on the canvas">
                <span class="flex w-full min-w-0 items-center justify-between gap-2">
                  <span class="flex min-w-0 items-center gap-1.5">
                    <span class="text-ink-gray-5">Show</span>
                    <span class="truncate">{{ triggerLabel }}</span>
                  </span>
                  <span class="lucide-chevron-down size-3.5 shrink-0 text-ink-gray-5" aria-hidden="true" />
                </span>
              </Button>
            </div>
          </template>
          <Panel embedded :items="items" :selected="pickValue" @choose="choose" />
        </Popover>
      </div>
      <div class="flex items-center gap-1">
        <span class="min-w-0 flex-1 truncate pl-4 text-p-sm text-ink-gray-5">{{ summary }}</span>
        <LensMenu v-for="s in appStates" :key="s.key" :state="s" />
        <Dropdown :options="zoomOptions">
          <Button variant="ghost" class="w-14 text-p-sm tabular-nums" aria-label="Zoom">{{ pct }}%</Button>
        </Dropdown>
      </div>
    </div>

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
            :narrow="t.w * view.z < 280"
            @activate="activate(t)"
            @open-page="openPage(t)"
            @near="(n: boolean) => onNear(t.id, n)"
          />
        </div>

        <div v-if="nothing" data-ui class="absolute inset-0 flex items-center justify-center text-center">
          <p class="text-base text-ink-gray-7">Nothing to show yet. Add a state or a variant set to a page.</p>
        </div>
      </div>

      <Panel v-if="panelShown" :items="items" :selected="pickValue" @choose="choose" @hide="setPanel(false)" />
      <!-- Where the hide button sits in the open panel, so the icon stays put when toggled. -->
      <div
        v-else-if="!phone"
        data-ui
        class="absolute right-5 top-5 z-10 rounded-[8px] bg-surface-elevation-2 shadow-sm ring-1 ring-outline-gray-2"
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
