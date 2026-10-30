<script setup lang="ts">
/**
 * What's new (decision 72): one Dialog, mounted once by `App.vue`, and a small card in the corner of the gallery.
 *
 * The Dialog opens by itself on the gallery, for a signed-in person, when this browser has not seen the newest entry.
 * Anyone can open it by hand from anywhere (`openWhatsNew`): the corner card, the avatar menu, the signed-out hero. It
 * is a carousel of one feature per slide. The slide moves on when its clip ends, never on a timer, so with no clip, or
 * with reduced motion, it stays where it is. A row of pills under the clip says where you are: the ones before are
 * full, the current one fills as its clip plays (so you can see it is about to move on), and it is simply full when
 * nothing will move it. A pill or an arrow key moves it and stops the moving on for this open. After the last clip it
 * stays on the last slide. Every way out writes the seen id, so the release shows once.
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

/** How far the current clip has played, 0 to 1; null until it reports, and whenever no clip is playing. */
const played = ref<number | null>(null)

function go(to: number): void {
  index.value = Math.min(Math.max(to, 0), last)
  played.value = null
}

/** A pill's fill: the ones before are full, the ones after empty, the current one follows its clip while it moves on. */
function fill(at: number): string {
  if (at !== index.value) return at < index.value ? '100%' : '0%'
  return advance.value && played.value !== null ? `${played.value * 100}%` : '100%'
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
    go(0)
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
    A title row with the close button, the clip with its pills right under it, the title and the line, then Got it. `bare`
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
        <WhatsNewClip :key="entry.id" class="rounded-6" :entry="entry" @progress="played = $event" @ended="clipEnded" />
        <!--
          The progress row right under the clip, centred, 4px gaps. Clips not on screen are 8px dots; the current one
          grows to a 32px capsule and fills as it plays. Clips already seen stay filled, so the row shows how many
          are left. Every part and its fill are fully round. Each part is a 24px-tall button, so it is easy to hit.
          Filled parts use the ink colour through its variable: Tailwind has no `bg-ink-*`.
        -->
        <div class="mx-auto mt-1 flex w-fit gap-1">
          <button
            v-for="(one, at) in slides"
            :key="one.id"
            type="button"
            :aria-label="`Show ${one.title}`"
            :aria-current="at === index"
            class="group h-6 transition-[width] duration-300 ease-out focus-visible:ring-0 focus-visible:focus-ring"
            :class="at === index ? 'w-8' : 'w-2'"
            @click="pick(at)"
          >
            <span class="block h-2 overflow-hidden rounded-full bg-surface-gray-3 group-hover:bg-surface-gray-4">
              <span
                class="block h-full rounded-full bg-[color:var(--ink-gray-8)]"
                :class="at === index && advance && played !== null ? 'transition-[width] duration-300 ease-linear' : ''"
                :style="{ width: fill(at) }"
              />
            </span>
          </button>
        </div>
        <h3 class="mt-2 text-lg-semibold text-ink-gray-8">{{ entry.title }}</h3>
        <p class="mt-1 text-p-base text-ink-gray-6">{{ entry.line }}</p>
        <div class="mt-4 flex justify-end">
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
