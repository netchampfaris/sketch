<script setup lang="ts">
/**
 * The rendered-preview area of a gallery item.
 *
 * A Prototype renders in a same-origin iframe: its own document, its own
 * global fetch, its own stylesheet (spec 6.6). The frame is the Viewer's own
 * 1280x800, scaled down to the card width, so the preview matches what
 * `check` screenshots.
 *
 * The frame remounts when the theme changes, because the Viewer reads
 * localStorage["theme"] once, at boot (spec 12).
 *
 * The whole preview is a link to `src`. See the shield in the template.
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useColorScheme } from 'frappe-ui'

const props = defineProps<{ src: string; title: string }>()

/** The Viewer frame `check` uses. Fixed, so every preview crops the same. */
const FRAME_WIDTH = 1280
const FRAME_HEIGHT = 800

const { colorScheme } = useColorScheme()

const box = ref<HTMLElement | null>(null)
const boxWidth = ref(0)
let observer: ResizeObserver | null = null

onMounted(() => {
  if (!box.value) return
  observer = new ResizeObserver((entries) => {
    boxWidth.value = entries[0].contentRect.width
  })
  observer.observe(box.value)
})

onBeforeUnmount(() => observer?.disconnect())

const frameStyle = computed(() => ({
  width: `${FRAME_WIDTH}px`,
  height: `${FRAME_HEIGHT}px`,
  transform: `scale(${boxWidth.value ? boxWidth.value / FRAME_WIDTH : 0})`,
}))

const loaded = ref(false)
const frameKey = computed(() => `${props.src}:${colorScheme.value}`)

// A new key mounts a fresh iframe, so the load flag has to start over.
watch(frameKey, () => (loaded.value = false))
</script>

<template>
  <div
    ref="box"
    class="relative aspect-[16/10] w-full overflow-hidden rounded-6 border border-outline-gray-1 bg-surface-gray-2"
  >
    <iframe
      :key="frameKey"
      class="absolute left-0 top-0 origin-top-left border-0 transition-opacity duration-200"
      :class="loaded ? 'opacity-100' : 'opacity-0'"
      loading="lazy"
      scrolling="no"
      :src="src"
      :style="frameStyle"
      tabindex="-1"
      :title="title"
      @load="loaded = true"
    />
    <!-- The shield keeps clicks and scrolls off the iframe: the preview is a
         picture of the prototype, not the prototype. It is also the card's
         big click target, and on a touch device the only one that always
         works, because the hover-only "Open prototype" button never appears
         there. `src` is the page the picture shows, so opening it is the one
         honest destination.

         Out of the tab order and out of the accessibility tree on purpose:
         the card title carries the same link with the prototype's name on it,
         and two links to one page would be announced twice. -->
    <a aria-hidden="true" class="absolute inset-0" :href="src" tabindex="-1" />
  </div>
</template>
