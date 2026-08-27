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
    <!-- The preview is a picture, not a control. The shield keeps clicks and
         scrolls on the card. -->
    <div class="absolute inset-0" />
  </div>
</template>
