<script setup lang="ts">
// The Demo pill and the canvas. The Viewer renders this beside the Prototype's App when the Prototype imports
// `sketch:variants`, and hands it that App, so a canvas frame can render the same app without an import cycle.
// Nothing shows inside a frame, or while Sketch captures a thumbnail (`data-sketch-chrome="off"`). The canvas
// is its own chunk: it downloads when the first canvas opens.
import { computed, defineAsyncComponent, inject, onBeforeUnmount, ref } from 'vue'
import { useRoute } from 'vue-router'
import Pills from './Pills.vue'
import { sandboxKey } from './state'

defineProps<{ shell: any }>()

const Canvas = defineAsyncComponent(() => import('./Canvas.vue'))
const inFrame = inject(sandboxKey, null) !== null
const route = useRoute()
const hidden = ref(document.documentElement.dataset.sketchChrome === 'off')
const watcher = new MutationObserver(() => (hidden.value = document.documentElement.dataset.sketchChrome === 'off'))
watcher.observe(document.documentElement, { attributes: true, attributeFilter: ['data-sketch-chrome'] })
onBeforeUnmount(() => watcher.disconnect())

const canvasOpen = computed(() => !!route.query.canvas)
</script>

<template>
  <template v-if="!inFrame && !hidden">
    <Pills />
    <Canvas v-if="canvasOpen" :app="shell" />
  </template>
</template>
