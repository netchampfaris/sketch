<script setup lang="ts">
/**
 * What's new, on the gallery (decision 72): a Dialog once per release, then a small card in the corner.
 *
 * The Dialog opens when this browser has not seen the newest entry. It is a carousel of one feature per slide. The slide
 * moves on when its clip ends, never on a timer, so with no clip, or with reduced motion, it stays where it is. A dot or
 * an arrow key moves it and stops that for this open. After the last clip it stays on the last slide. Every way out
 * writes the seen id, so the release shows once.
 *
 * The corner card is what is left of it: it appears when the Dialog is closed and goes when it is clicked or its × is
 * pressed. A phone has no room for it, so it is hidden under 640px.
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Button, Dialog } from 'frappe-ui'
import WhatsNewClip from './WhatsNewClip.vue'
import { signedIn } from '../store'
import { cardDismissed, dismissCard, markSeen, seenRelease, whatsNew } from '../whatsnew'

const router = useRouter()

const open = ref(false)
const index = ref(0)
/** True until a dot or an arrow is used: the clip's end moves to the next slide only while it is. */
const advance = ref(true)
const cardGone = ref(cardDismissed())

const entry = computed(() => whatsNew[index.value])
const last = whatsNew.length - 1

function go(to: number): void {
  index.value = Math.min(Math.max(to, 0), last)
}

function pick(to: number): void {
  advance.value = false
  go(to)
}

function clipEnded(): void {
  if (advance.value) go(index.value + 1)
}

function onKey(event: KeyboardEvent): void {
  if (event.key === 'ArrowLeft') pick(index.value - 1)
  else if (event.key === 'ArrowRight') pick(index.value + 1)
}

watch(open, (isOpen) => {
  if (isOpen) {
    index.value = 0
    advance.value = true
    window.addEventListener('keydown', onKey)
  } else {
    window.removeEventListener('keydown', onKey)
    markSeen()
  }
})

// The session read lands after this screen mounts, so the Dialog waits for it.
watch(
  signedIn,
  (yes) => {
    if (yes && !seenRelease()) open.value = true
  },
  { immediate: true },
)

onBeforeUnmount(() => window.removeEventListener('keydown', onKey))

function seeAll(): void {
  open.value = false
  router.push('/whats-new')
}

function openCard(): void {
  dismissCard()
  cardGone.value = true
  router.push('/whats-new')
}

function closeCard(): void {
  dismissCard()
  cardGone.value = true
}
</script>

<template>
  <Dialog v-if="signedIn" v-model:open="open" size="xl">
    <template #title><span class="text-base-medium text-ink-gray-8">What's new</span></template>

    <div>
      <WhatsNewClip :key="entry.id" :entry="entry" play="now" @ended="clipEnded" />
      <h3 class="mt-4 text-lg-semibold text-ink-gray-8">{{ entry.title }}</h3>
      <p class="mt-1 text-p-base text-ink-gray-6">{{ entry.line }}</p>
      <div class="mt-4 flex items-center gap-2">
        <button
          v-for="(one, at) in whatsNew"
          :key="one.id"
          type="button"
          :aria-label="`Show ${one.title}`"
          :aria-current="at === index"
          class="size-2 rounded-full bg-current transition-colors focus-visible:ring-0 focus-visible:focus-ring"
          :class="at === index ? 'text-ink-gray-8' : 'text-ink-gray-3'"
          @click="pick(at)"
        />
      </div>
    </div>

    <template #actions="{ close }">
      <div class="flex items-center justify-between gap-2">
        <Button label="See all updates" variant="ghost" @click="seeAll" />
        <Button label="Got it" variant="solid" @click="close" />
      </div>
    </template>
  </Dialog>

  <!--
    Fixed to the bottom-left and over the page, below dialogs and menus (z-30). A real button, so the whole card is
    keyboard reachable; the × is its own button beside it, not inside it.
  -->
  <div
    v-if="signedIn && !open && !cardGone"
    class="fixed bottom-4 left-4 z-30 hidden w-64 rounded-6 bg-surface-elevation-1 shadow-xl ring-1 ring-outline-gray-2 sm:block"
  >
    <button type="button" class="block w-full rounded-6 px-3 py-2.5 pr-10 text-left" @click="openCard">
      <span class="block text-xs text-ink-gray-5">What's new</span>
      <span class="block truncate text-sm-medium text-ink-gray-8">{{ whatsNew[0].title }}</span>
    </button>
    <Button
      class="absolute right-1.5 top-1.5"
      aria-label="Dismiss"
      icon="lucide-x"
      size="xs"
      variant="ghost"
      @click="closeCard"
    />
  </div>
</template>
