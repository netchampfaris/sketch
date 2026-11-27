<script setup lang="ts">
// The sets a page holds behind its closed dialogs. A closed frappe-ui Dialog does not mount its content, so the sets
// inside it never register, and the Demo pill could not list them. This renders the page once more, offscreen and inert,
// with every Dialog open (dialogs.ts), with the picks and states the page has now, reports the sets it found and is
// dropped (Chrome.vue). Only the options picked now are drawn, so a set inside another set's unpicked option stays
// unfound. Nothing here reaches the live registry, the URL or the router.
import { nextTick, onErrorCaptured, onMounted, reactive, ref } from 'vue'
import { offscreen, useFrame } from './frame'
import { nextFrames } from './snapshot'
import { choices, stateValues, type Sandbox, type VSet } from './state'

const props = defineProps<{ app: any; path: string }>()
const emit = defineEmits<{ found: [sets: VSet[]] }>()

const sandbox: Sandbox = reactive({ states: { ...stateValues }, variants: { ...choices }, reg: { states: [], sets: [] }, live: false }) as Sandbox
const el = ref<HTMLElement | null>(null)
useFrame({ path: props.path, sandbox, root: () => el.value, open: 'all' })
// A page that throws here throws on the page too, where it is reported.
onErrorCaptured(() => false)

onMounted(async () => {
  await nextFrames(2)
  await nextTick()
  // Each set still drawn: a copy that unmounted (a dialog that closed itself as it mounted) leaves none.
  emit('found', sandbox.reg.sets.filter((s) => s.copies.length))
})
</script>

<template>
  <Teleport to="body">
    <div
      ref="el"
      data-sketch-ui="canvas-frame"
      aria-hidden="true"
      inert
      :style="offscreen(1280, 800)"
    >
      <component :is="app" />
    </div>
  </Teleport>
</template>
