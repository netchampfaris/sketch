<script setup lang="ts">
/**
 * One entry's silent clip in a 16:9 frame (decision 72). With no clip, or a clip that fails to load, the frame holds the
 * entry's icon instead, so a missing file reads as a quiet placeholder and never as a broken player.
 *
 * It plays once and says when it ended (the modal moves on then). With reduced motion nothing plays by itself.
 */
import { ref } from 'vue'
import type { WhatsNewEntry } from '../whatsnew'

defineProps<{ entry: WhatsNewEntry }>()
const emit = defineEmits<{ ended: []; progress: [part: number] }>()

const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
const failed = ref(false)
const video = ref<HTMLVideoElement | null>(null)
</script>

<template>
  <div class="relative aspect-video w-full overflow-hidden bg-surface-gray-2">
    <video
      v-if="entry.video && !failed"
      ref="video"
      class="size-full object-cover"
      :src="entry.video"
      muted
      playsinline
      :autoplay="!reduced"
      :aria-label="entry.title"
      @error="failed = true"
      @timeupdate="video && video.duration && emit('progress', video.currentTime / video.duration)"
      @ended="emit('ended')"
    />
    <div v-else class="absolute inset-0 grid place-items-center">
      <span :class="entry.icon" class="size-8 text-ink-gray-5" aria-hidden="true" />
    </div>
  </div>
</template>
