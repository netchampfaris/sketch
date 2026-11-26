<script setup lang="ts">
// One render of the whole app in a given page, state and variant. Offscreen, it is drawn, captured and
// dropped. Live, it stays in a tile. `app` is App.vue's own component, handed over so there is no cycle.
import { nextTick, onBeforeUnmount, onErrorCaptured, onMounted, provide, ref, shallowRef } from 'vue'
import { routeLocationKey, routerKey, routerViewLocationKey, useRouter } from 'vue-router'
import { Alert } from 'frappe-ui'
import { sandboxKey } from './state'
import type { Sandbox } from './state'
import { frameDialogs } from './dialogs'
import { follow } from './lift'
import { capture, errorSnap, nextFrames } from './snapshot'
import type { Crop, Snap } from './snapshot'

const props = defineProps<{
  app: any
  path: string
  w: number
  h: number
  sandbox: Sandbox
  mode: 'offscreen' | 'live'
  targetSet?: string | null
  // A state tile: the set grows to its full content height (lift.ts).
  grow?: boolean
}>()
// `anchor`, live only: where the lifted set sits in the page each time it moves or resizes.
// `painted`, live only: the frame may show now. Until then the page inside is not lifted to its set, so the tile keeps its
// snapshot over it: it is emitted once the set has a box, or at once for a tile that shows the whole page.
const emit = defineEmits<{ ready: [snap: Snap]; error: [message: string]; anchor: [box: Crop | null]; painted: [] }>()

const router = useRouter()
const resolved = router.resolve(props.path)
// App's RouterView and RouterLink follow this page, not the live one.
provide(routerViewLocationKey, shallowRef(resolved))
provide(routeLocationKey, resolved as any)
// A tile never moves the live page: a page that redirects as it mounts would drop `?canvas=` and close the canvas.
// Navigating from a tile does nothing.
const stay = () => Promise.resolve()
const still = Object.assign(Object.create(router), { push: stay, replace: stay, go: () => {}, back: () => {}, forward: () => {} })
provide(routerKey, still)
provide(sandboxKey, props.sandbox)

const el = ref<HTMLElement | null>(null)
// A page dialog draws in this frame, never over the canvas, and the target set's dialogs show open (dialogs.ts).
frameDialogs(() => el.value, () => props.targetSet)
const failed = ref('')
let reported = false
const firstLine = (e: unknown) => String((e as any)?.message ?? e).split('\n')[0]

onErrorCaptured((err) => {
  failed.value = firstLine(err)
  if (!reported) {
    reported = true
    emit('error', failed.value)
  }
  return false
})

const target = () => (props.targetSet ? props.sandbox.reg.sets.find((s) => s.key === props.targetSet) ?? null : null)

let stop = () => {}
let gone = false
// A live tile never takes focus by itself: a field that autofocuses as its dialog opens would outline itself beside the
// live ring. Focus moves in only after the person clicks inside the frame or tabs.
let invited = false
const onInput = (e: Event) => {
  if (e.type === 'pointerdown') invited = !!el.value?.contains(e.target as Node)
  else if ((e as KeyboardEvent).key === 'Tab') invited = true
}
const onFocusIn = (e: FocusEvent) => {
  if (invited || !el.value?.contains(e.target as Node)) return
  ;(e.target as HTMLElement).blur?.()
  if (before?.isConnected) before.focus({ preventScroll: true })
}
// Where focus was as the tile went live (the tile itself, once clicked), and goes back to.
const before = props.mode === 'live' ? (document.activeElement as HTMLElement | null) : null
if (props.mode === 'live') {
  document.addEventListener('pointerdown', onInput, true)
  document.addEventListener('keydown', onInput, true)
  document.addEventListener('focusin', onFocusIn, true)
}
onBeforeUnmount(() => {
  gone = true
  stop()
  document.removeEventListener('pointerdown', onInput, true)
  document.removeEventListener('keydown', onInput, true)
  document.removeEventListener('focusin', onFocusIn, true)
})
onMounted(async () => {
  await nextFrames(2)
  await nextTick()
  // A live tile closed during those frames must not start following a page that is already gone.
  if (gone || !el.value || reported) return
  if (props.mode === 'live') {
    // The set lifted out of the page, as the snapshot drew it, and kept there while the page changes. A set that is the
    // page shows the whole window.
    const t = target()
    if (!t || t.page()) return emit('painted')
    let shown = false
    const show = () => {
      if (shown || gone) return
      shown = true
      emit('painted')
    }
    stop = follow(el.value, () => t.elements(), (box) => {
      emit('anchor', box)
      if (box) show()
    }, props.grow)
    // A set with no box of its own shows the whole page, as its snapshot does: shown once it has had time to find one.
    setTimeout(show, 600)
    return
  }
  try {
    reported = true
    emit('ready', capture(el.value, props.sandbox.reg, target(), props.grow))
  } catch (e) {
    emit('error', firstLine(e))
  }
})
</script>

<template>
  <Teleport to="body" :disabled="mode === 'live'">
    <div
      ref="el"
      :data-sketch-ui="mode === 'offscreen' ? 'canvas-frame' : undefined"
      :data-tile-drawing="mode === 'live' ? '' : undefined"
      :aria-hidden="mode === 'offscreen' ? 'true' : undefined"
      :inert="mode === 'offscreen' ? true : undefined"
      :style="
        mode === 'offscreen'
          ? { position: 'fixed', left: '-100000px', top: '0', width: w + 'px', height: h + 'px', overflow: 'hidden', contain: 'strict' }
          : { position: 'relative', width: w + 'px', height: h + 'px', overflow: 'hidden', contain: 'layout paint' }
      "
    >
      <div v-if="failed" class="p-4">
        <Alert theme="red" title="Could not render this page" :description="failed" />
      </div>
      <component :is="app" v-else />
    </div>
  </Teleport>
</template>
