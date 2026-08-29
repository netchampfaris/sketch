<script setup lang="ts">
/**
 * The picture on a gallery card.
 *
 * It is a PNG, not a live Viewer. A card used to draw a same-origin iframe of
 * the Prototype, and every frame booted a whole Runtime: about 4.5 MB of
 * assets for the first one, then a Vue app, a Tailwind compile and an SFC
 * compile for each one after it. Twelve cards meant twelve of those, and the
 * feed could not afford a single one, so /feed printed text rows instead
 * (`sketch/www/feed.html`). One image is one request, so both surfaces now
 * draw the same card.
 *
 * `sketch/thumbnails.py` takes the picture, during the `check` the agent runs
 * at the end of every request. It is therefore as old as the last check, not
 * as old as the last file write. The card already prints "Updated ...", which
 * is the honest reading of that gap, and the server asks for a fresh capture
 * in the background whenever it hands out a stale one.
 *
 * One picture per theme, because a light screenshot in a dark gallery reads as
 * a broken card. A theme the capture could not take is absent from
 * `thumbnail`, so the fallback below is to the other one and never to a
 * request that is known to 404.
 *
 * The whole preview is a link to `href`. See the shield in the template.
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useColorScheme } from 'frappe-ui'
import type { PrototypeThumbnail } from '../types'

const props = defineProps<{
  /** One same-origin path per captured theme. Null before the first check. */
  thumbnail: PrototypeThumbnail | null
  /** Where the picture leads. The Viewer path for this Prototype. */
  href: string
}>()

const { colorScheme } = useColorScheme()

/**
 * `system`, resolved.
 *
 * `colorScheme` carries the preference, which can be `system`, and a file name
 * cannot. The media query is watched rather than read once, because a preference
 * of `system` changes what the page is painted in without `colorScheme` moving.
 */
const systemDark = ref(false)
let media: MediaQueryList | null = null
const followSystem = () => (systemDark.value = media?.matches ?? false)

onMounted(() => {
  media = window.matchMedia('(prefers-color-scheme: dark)')
  followSystem()
  media.addEventListener('change', followSystem)
})

onBeforeUnmount(() => media?.removeEventListener('change', followSystem))

const scheme = computed(() =>
  colorScheme.value === 'system' ? (systemDark.value ? 'dark' : 'light') : colorScheme.value,
)

const src = computed(() => {
  const shots = props.thumbnail
  if (!shots) return null
  return shots[scheme.value] ?? shots.light ?? shots.dark ?? null
})

// A picture that 404s or decodes badly falls back to the placeholder, so a
// broken image glyph never lands on the artwork. The flag has to start over on
// a new `src`: a dark capture that failed must not hide a light one that works.
const failed = ref(false)
const loaded = ref(false)
watch(src, () => {
  failed.value = false
  loaded.value = false
})

const showImage = computed(() => !!src.value && !failed.value)
</script>

<template>
  <div
    class="relative aspect-[16/10] w-full overflow-hidden rounded-6 border border-outline-gray-1 bg-surface-gray-2"
  >
    <!--
      1280x800 is the Viewer frame `check` screenshots, which is this box's own
      16:10, so `object-cover` scales and never crops. `object-top` is the
      fallback that matters if a Runtime ever changes that frame: the top of a
      page is the part worth keeping.

      The fade is on opacity only. The box holds its size from the first paint,
      so nothing on the card moves when the picture arrives.
    -->
    <img
      v-if="showImage"
      alt=""
      class="absolute inset-0 size-full object-cover object-top transition-opacity duration-200"
      :class="loaded ? 'opacity-100' : 'opacity-0'"
      decoding="async"
      loading="lazy"
      :src="src!"
      @error="failed = true"
      @load="loaded = true"
    />

    <!--
      The state of a Prototype whose agent has not run `check` with
      `screenshot: true` yet, which every brand new Prototype is. It says what
      is missing and what fills it, because "no preview" alone reads as a
      failure and this is not one.

      Quieter than the empty-state recipe on purpose: that recipe is for a
      whole screen, and this is one tile in a grid of them. The glyph is the
      `size-6` step the recipe uses, without its 48px container.
    -->
    <div
      v-else
      class="absolute inset-0 flex flex-col items-center justify-center gap-2 px-4 text-center"
    >
      <span aria-hidden="true" class="lucide-image size-6 text-ink-gray-4" />
      <p class="text-xs text-ink-gray-5">The next check draws this</p>
    </div>

    <!-- The shield is the card's big click target. `href` is the page the
         picture shows, so opening it is the one honest destination.

         It opens in a new tab, like the title and the Open button, so the
         gallery survives the click. `noopener` matters more here than usual:
         the Viewer runs code the user's own agent wrote.

         Out of the tab order and out of the accessibility tree on purpose:
         the card title carries the same link with the prototype's name on it,
         and two links to one page would be announced twice. The image is
         `alt=""` for the same reason. -->
    <a
      aria-hidden="true"
      class="absolute inset-0"
      :href="href"
      rel="noopener"
      tabindex="-1"
      target="_blank"
    />
  </div>
</template>
