<script setup lang="ts">
import { useTextareaAutosize } from '@vueuse/core'

const title = defineModel<string>({ required: true })
const emit = defineEmits<{ (e: 'next'): void }>()

// The box grows with the text, so the title never scrolls inside itself and
// the page below it never jumps.
const { textarea } = useTextareaAutosize({ input: title })
</script>

<template>
  <textarea
    ref="textarea"
    v-model="title"
    class="mt-1 w-full resize-none border-0 bg-transparent px-0 py-0.5 text-4xl-semibold text-ink-gray-8 placeholder-ink-gray-3 focus:ring-0"
    placeholder="Title"
    rows="1"
    wrap="soft"
    maxlength="140"
    @keydown.enter.prevent="emit('next')"
    @keydown.down.prevent="emit('next')"
  />
</template>
