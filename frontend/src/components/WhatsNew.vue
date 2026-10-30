<script setup lang="ts">
/**
 * What's new (decision 72): one Dialog, mounted once by `App.vue`, and a small card in the corner of the gallery.
 *
 * The Dialog opens by itself on the gallery, for a signed-in person, when this browser has not seen the newest entry.
 * Anyone can open it by hand from anywhere (`openWhatsNew`): the corner card, the avatar menu, the signed-out hero. It
 * is a carousel of one feature per slide. The slide moves on when its clip ends, never on a timer, so with no clip, or
 * with reduced motion, it stays where it is. A dot or an arrow key moves it and stops that for this open. After the last
 * clip it stays on the last slide. Every way out writes the seen id, so the release shows once.
 *
 * The corner card is what is left of it: signed in, on the gallery, while the Dialog is closed, until it is clicked or
 * its × is pressed. A phone has no room for it, so it is hidden under 640px.
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Button, Dialog } from 'frappe-ui'
import WhatsNewClip from './WhatsNewClip.vue'
import { signedIn } from '../store'
import { cardGone, dismissCard, markSeen, openWhatsNew, seenRelease, slides, whatsNew, whatsNewOpen } from '../whatsnew'

const route = useRoute()

const index = ref(0)
/** True until a dot or an arrow is used: the clip's end moves to the next slide only while it is. */
const advance = ref(true)

const entry = computed(() => slides[index.value])
const last = slides.length - 1

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

watch(whatsNewOpen, (isOpen) => {
  if (isOpen) {
    index.value = 0
    advance.value = true
    window.addEventListener('keydown', onKey)
  } else {
    window.removeEventListener('keydown', onKey)
    markSeen()
  }
})

/** The gallery is where it opens by itself, once the session read says who is here. A Guest never gets it unasked. */
const onGallery = computed(() => route.path === '/')
watch(
  [signedIn, onGallery],
  ([yes, home]) => {
    if (yes && home && !seenRelease()) whatsNewOpen.value = true
  },
  { immediate: true },
)

onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <!--
    A title row with the close button, the clip, the title and the line, the dots, then Got it on the right. `bare`
    drops the Dialog's own padding (24px sides, 24px under the header, 28px under the actions), so this one can sit on a
    tighter 16px all round. Esc and a click outside still close it.
  -->
  <Dialog v-model:open="whatsNewOpen" size="xl" bare>
    <template #default="{ close }">
      <div class="p-4">
        <div class="mb-3 flex items-center justify-between">
          <h2 class="text-base-medium text-ink-gray-8">What's new</h2>
          <Button variant="ghost" icon="lucide-x" aria-label="Close" @click="close" />
        </div>
        <WhatsNewClip :key="entry.id" class="rounded-6" :entry="entry" play="now" @ended="clipEnded" />
        <h3 class="mt-3 text-lg-semibold text-ink-gray-8">{{ entry.title }}</h3>
        <p class="mt-1 text-p-base text-ink-gray-6">{{ entry.line }}</p>
        <div class="mt-4 flex items-center justify-between gap-3">
          <!-- An 8px dot in a 24px button, so a thumb can hit it; the buttons touch, so the dots sit 16px apart. -->
          <div class="-ml-2 flex items-center">
            <button
              v-for="(one, at) in slides"
              :key="one.id"
              type="button"
              :aria-label="`Show ${one.title}`"
              :aria-current="at === index"
              class="grid size-6 place-items-center rounded-full focus-visible:ring-0 focus-visible:focus-ring"
              :class="at === index ? 'text-ink-gray-8' : 'text-ink-gray-3 hover:text-ink-gray-5'"
              @click="pick(at)"
            >
              <span class="size-2 rounded-full bg-current transition-colors" aria-hidden="true" />
            </button>
          </div>
          <Button label="Got it" variant="solid" @click="close" />
        </div>
      </div>
    </template>
  </Dialog>

  <!--
    Fixed to the bottom-left and over the page, below dialogs and menus (z-30). A real button, so the whole card is
    keyboard reachable; the × is its own button beside it, not inside it.
  -->
  <div
    v-if="signedIn && onGallery && !whatsNewOpen && !cardGone"
    class="fixed bottom-4 left-4 z-30 hidden w-64 rounded-6 bg-surface-elevation-1 shadow-xl ring-1 ring-outline-gray-2 sm:block"
  >
    <button type="button" class="block w-full rounded-6 px-3 py-2.5 pr-10 text-left" @click="openWhatsNew">
      <span class="block text-xs text-ink-gray-5">What's new</span>
      <span class="block truncate text-sm-medium text-ink-gray-8">{{ whatsNew[0].title }}</span>
    </button>
    <Button
      class="absolute right-1.5 top-1.5"
      aria-label="Dismiss"
      icon="lucide-x"
      size="xs"
      variant="ghost"
      @click="dismissCard"
    />
  </div>
</template>
