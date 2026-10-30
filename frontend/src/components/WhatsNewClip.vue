<script setup lang="ts">
/**
 * One entry's silent clip in a 16:9 frame (decision 72). With no clip, or a clip that fails to load, the frame holds the
 * entry's icon instead, so a missing file reads as a quiet placeholder and never as a broken player.
 *
 * `play` decides what the clip does on its own. 'now' plays once and says when it ended (the modal moves on then).
 * 'visible' loops while it is on screen and holds still off it (the page). With reduced motion nothing plays by itself
 * and the page's clips show controls.
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'
import type { WhatsNewEntry } from '../whatsnew'

const props = defineProps<{ entry: WhatsNewEntry; play: 'now' | 'visible' }>()
const emit = defineEmits<{ ended: [] }>()

const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
const failed = ref(false)
const frame = ref<HTMLElement | null>(null)
const video = ref<HTMLVideoElement | null>(null)
let watcher: IntersectionObserver | null = null

onMounted(() => {
  if (props.play !== 'visible' || reduced || !frame.value) return
  watcher = new IntersectionObserver(([seen]) => {
    if (seen.isIntersecting) video.value?.play().catch(() => {})
    else video.value?.pause()
  })
  watcher.observe(frame.value)
})

onBeforeUnmount(() => watcher?.disconnect())
</script>

<template>
  <div ref="frame" class="relative aspect-video w-full overflow-hidden rounded-6 bg-surface-gray-2">
    <video
      v-if="entry.video && !failed"
      ref="video"
      class="size-full object-cover"
      :src="entry.video"
      muted
      playsinline
      :autoplay="play === 'now' && !reduced"
      :loop="play === 'visible'"
      :controls="play === 'visible' && reduced"
      :aria-label="entry.title"
      @error="failed = true"
      @ended="emit('ended')"
    />
    <div v-else class="absolute inset-0 grid place-items-center">
      <span :class="entry.icon" class="size-8 text-ink-gray-5" aria-hidden="true" />
    </div>
  </div>
</template>
