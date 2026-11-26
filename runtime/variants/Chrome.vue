<script setup lang="ts">
// The canvas. The Viewer renders this beside the Prototype's App when the Prototype imports `sketch:variants`, and
// hands it that App, so a canvas frame can render the same app without an import cycle. Nothing shows inside a frame,
// or for a `check` run (`data-sketch-chrome="off"`). The Demo pill is the Viewer shell's, drawn over this page from
// what the frame agent reports (runtime/shell/DemoPill.vue). The canvas is its own chunk: it downloads when the first
// canvas opens.
//
// It also finds the sets behind the page's closed dialogs (Discover.vue), so the Demo pill lists them on every page the
// dialog opens from. Only while the page has a closed dialog, and again when the page, a pick or a state changes.
import { computed, defineAsyncComponent, getCurrentInstance, inject, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { dialogsIn } from './dialogs'
import { choices, sandboxKey, setFound, sets, stateValues, type VSet } from './state'

const props = defineProps<{ shell: any }>()

const Canvas = defineAsyncComponent(() => import('./Canvas.vue'))
const Discover = defineAsyncComponent(() => import('./Discover.vue'))
const inFrame = inject(sandboxKey, null) !== null
const route = useRoute()
const router = useRouter()
const hidden = ref(document.documentElement.dataset.sketchChrome === 'off')
const watcher = new MutationObserver(() => (hidden.value = document.documentElement.dataset.sketchChrome === 'off'))
watcher.observe(document.documentElement, { attributes: true, attributeFilter: ['data-sketch-chrome'] })

const canvasOpen = computed(() => !!route.query.canvas)

// ---- Sets behind closed dialogs
const root = getCurrentInstance()!.root
const job = ref<{ n: number; path: string; key: string } | null>(null)
let n = 0
let lookedFor = ''
let timer = 0
const look = () => {
  clearTimeout(timer)
  timer = window.setTimeout(() => {
    if (inFrame || hidden.value || canvasOpen.value || job.value) return
    const open = dialogsIn(root.subTree)
    // No dialog at all: nothing is behind one. Every dialog open: what is in them is mounted, and what was found stays.
    if (!open.length) return setFound([], router)
    if (!open.includes(false)) return
    const key = JSON.stringify([route.path, choices, stateValues])
    if (key === lookedFor) return
    job.value = { n: ++n, path: route.fullPath, key }
  }, 150)
}
function onFound(list: VSet[]) {
  const done = job.value
  job.value = null
  if (!done) return
  lookedFor = done.key
  setFound(list, router)
  // The page moved on while it looked.
  look()
}
if (!inFrame) {
  watch([() => route.path, () => JSON.stringify(choices), () => JSON.stringify(stateValues), () => sets.length, canvasOpen, hidden], look, { immediate: true })
}
onBeforeUnmount(() => {
  watcher.disconnect()
  clearTimeout(timer)
})
</script>

<template>
  <Canvas v-if="!inFrame && !hidden && canvasOpen" :app="shell" />
  <Discover v-if="job" :key="job.n" :app="props.shell" :path="job.path" @found="onFound" />
</template>
