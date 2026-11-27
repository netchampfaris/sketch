<script setup lang="ts">
// The canvas. The Viewer renders this beside the Prototype's App when the Prototype imports `sketch:variants`, and
// hands it that App, so a canvas frame can render the same app without an import cycle. Nothing shows inside a frame,
// or for a `check` run (`data-sketch-chrome="off"`). The Demo pill is the Viewer shell's, drawn over this page from
// what the frame agent reports (runtime/shell/DemoPill.vue). The canvas is its own chunk: it downloads when the first
// canvas opens.
//
// It also finds the sets behind the page's closed dialogs (discover.ts), so the Demo pill lists them.
import { computed, defineAsyncComponent, inject, onBeforeUnmount, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useDialogSets } from './discover'
import { sandboxKey } from './state'

const props = defineProps<{ shell: any }>()

const Canvas = defineAsyncComponent(() => import('./Canvas.vue'))
const Discover = defineAsyncComponent(() => import('./Discover.vue'))
const inFrame = inject(sandboxKey, null) !== null
const route = useRoute()
const hidden = ref(document.documentElement.dataset.sketchChrome === 'off')
const watcher = new MutationObserver(() => (hidden.value = document.documentElement.dataset.sketchChrome === 'off'))
watcher.observe(document.documentElement, { attributes: true, attributeFilter: ['data-sketch-chrome'] })
onBeforeUnmount(() => watcher.disconnect())

const canvasOpen = computed(() => !!route.query.canvas)
const { job, onFound } = useDialogSets(() => hidden.value || canvasOpen.value)
</script>

<template>
  <Canvas v-if="!inFrame && !hidden && canvasOpen" :app="shell" />
  <Discover v-if="job" :key="job.n" :app="props.shell" :path="job.path" @found="onFound" />
</template>
