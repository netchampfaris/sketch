<script setup lang="ts">
// One render of the whole app in a given page, state and variant. Offscreen, it is drawn, captured and
// dropped. Live, it stays in a tile. `app` is App.vue's own component, handed over so there is no cycle.
import { nextTick, onBeforeUnmount, onErrorCaptured, onMounted, provide, ref, shallowRef } from 'vue'
import { routeLocationKey, routerViewLocationKey, useRouter } from 'vue-router'
import { Alert } from 'frappe-ui'
import { sandboxKey } from './state'
import type { Sandbox } from './state'
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
const emit = defineEmits<{ ready: [snap: Snap]; error: [message: string]; anchor: [box: Crop | null] }>()

const router = useRouter()
const resolved = router.resolve(props.path)
// App's RouterView and RouterLink follow this page, not the live one.
provide(routerViewLocationKey, shallowRef(resolved))
provide(routeLocationKey, resolved as any)
provide(sandboxKey, props.sandbox)

const el = ref<HTMLElement | null>(null)
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
onBeforeUnmount(() => stop())
onMounted(async () => {
  await nextFrames(2)
  await nextTick()
  if (!el.value || reported) return
  if (props.mode === 'live') {
    // The set lifted out of the page, as the snapshot drew it, and kept there while the page changes. A set that is the
    // page shows the whole window.
    const t = target()
    if (t && !t.page()) stop = follow(el.value, () => t.elements(), (box) => emit('anchor', box), props.grow)
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
      :aria-hidden="mode === 'offscreen' ? 'true' : undefined"
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
