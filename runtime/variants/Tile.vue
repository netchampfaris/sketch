<script setup lang="ts">
// One tile: the drawing in a box, a caption under it. The drawing is a snapshot (static DOM, only while near
// the view), a gray box while undrawn, an error box, or a live render. Sizes that stay on screen at any zoom
// use `--ls`, so zooming only scales the layout.
import { computed, nextTick, ref, watch } from 'vue'
import { useIntersectionObserver } from '@vueuse/core'
import { Badge, Button, toast } from 'frappe-ui'
import { canMakeDefault, makeDefault } from './default'
import Frame from './Frame.vue'
import { MARGIN } from './layout'
import { restoreScrolls } from './snapshot'
import type { Snap } from './snapshot'
import type { Sandbox } from './state'
import type { TileBox } from './layout'

const props = defineProps<{
  tile: TileBox
  snap?: Snap
  live: boolean
  app: any
  win: { w: number; h: number }
  sandbox?: Sandbox
}>()
const emit = defineEmits<{ activate: []; openPage: []; near: [near: boolean] }>()

const box = ref<HTMLElement | null>(null)
const snapEl = ref<HTMLElement | null>(null)
const near = ref(false)
useIntersectionObserver(
  box,
  ([e]) => {
    near.value = e.isIntersecting
    emit('near', e.isIntersecting)
  },
  { rootMargin: `${window.innerHeight}px ${window.innerWidth}px` },
)

const isSet = computed(() => props.tile.kind === 'set')
// The part of the page this tile shows: the set's own box, or the whole window.
const rect = computed(() => {
  if (!isSet.value) return { x: 0, y: 0, w: props.win.w, h: props.win.h }
  const own = props.snap && !props.snap.error ? props.snap.sets.find((s) => s.key === props.tile.setKey) : null
  return own ?? props.tile.meta ?? { x: 0, y: 0, w: props.tile.w - MARGIN * 2, h: props.tile.h - MARGIN * 2 }
})
// Make default: the owner's page only, on an option that is not first. The page reloads once it is saved, so the
// Default badge is on the new first tile when it comes back.
const defaultable = computed(() => {
  const t = props.tile
  return t.kind === 'set' && !t.isDefault && t.setFile && t.setName && t.setOptions
    ? { name: t.setName, file: t.setFile, options: () => t.setOptions! }
    : null
})
const canDefault = computed(() => !!defaultable.value && canMakeDefault(defaultable.value))
const saving = ref(false)
async function makeIt() {
  if (!defaultable.value || saving.value) return
  saving.value = true
  try {
    await makeDefault(defaultable.value, props.tile.option!)
  } catch (e) {
    saving.value = false
    toast.error(`Couldn't change the default. ${(e as Error).message}`)
  }
}

const margin = computed(() => (isSet.value ? MARGIN : 0))
const clip = computed(() => ({ left: margin.value + 'px', top: margin.value + 'px', width: rect.value.w + 'px', height: rect.value.h + 'px' }))
const shift = computed(() => ({ transform: `translate(${-rect.value.x}px, ${-rect.value.y}px)` }))

watch(
  [snapEl, () => props.snap],
  () => nextTick(() => snapEl.value && props.snap && restoreScrolls(snapEl.value, props.snap.scrolls)),
  { flush: 'post' },
)
</script>

<template>
  <div class="group/tile absolute" :style="{ left: tile.x + 'px', top: tile.y + 'px', width: tile.w + 'px', height: tile.h + 'px' }">
    <!-- The caption sits under the tile, drawn at its on-screen size (never larger than at the fit zoom). -->
    <div
      class="absolute inset-x-0 top-full"
      :style="{ paddingTop: 'calc(8px * var(--ls))', paddingRight: live ? 'calc(110px * var(--ls))' : '0', fontSize: 'calc(13px * var(--ls))', lineHeight: '1.3' }"
    >
      <div class="truncate text-ink-gray-5" :title="tile.caption">
        <span v-if="tile.n" class="mr-1.5 tabular-nums text-ink-gray-4">{{ tile.n }}</span>{{ tile.caption }}
      </div>
    </div>
    <!-- Make default, above the tile's top right. It shows on hover and focus (always where there is no hover), and the
         padding under it keeps the pointer on the tile while it travels up. -->
    <div
      v-if="canDefault"
      data-ui
      data-slot="make-default"
      class="absolute bottom-full right-0 opacity-0 focus-within:opacity-100 group-hover/tile:opacity-100 [@media(hover:none)]:opacity-100"
      :class="saving ? '!opacity-100' : ''"
      :style="{ paddingBottom: 'calc(2px * var(--ls))' }"
    >
      <div style="transform: scale(var(--ls)); transform-origin: right bottom">
        <Button
          variant="subtle"
          size="sm"
          :loading="saving"
          :aria-label="`Make ${tile.opt} the default for ${tile.setName}`"
          @click.stop="makeIt"
        >
          <span :class="saving ? 'sr-only' : ''">Make default</span>
        </Button>
      </div>
    </div>
    <div
      v-if="live"
      data-ui
      class="absolute right-0 top-full"
      style="margin-top: calc(2px * var(--ls)); transform: scale(var(--ls)); transform-origin: right top"
    >
      <Button variant="ghost" size="sm" label="Open page" icon-right="lucide-arrow-up-right" @click.stop="emit('openPage')" />
    </div>

    <!-- A page that has a States set but not this state: same size, dashed, nothing to open. -->
    <div
      v-if="tile.kind === 'gap'"
      data-gap
      class="absolute inset-0 flex items-center justify-center rounded-4 border-dashed border-outline-gray-3 px-4 text-center"
      :style="{ borderWidth: 'calc(1px * var(--inv))' }"
    >
      <span class="text-ink-gray-5" :style="{ fontSize: 'calc(13px * var(--ls))' }">{{ tile.gapText }}</span>
    </div>

    <div
      v-else
      ref="box"
      data-tile
      role="button"
      tabindex="0"
      :aria-label="`${tile.pageTitle} · ${tile.opt ?? tile.caption}${tile.isDefault ? ' (default)' : ''}, open live`"
      class="group relative h-full w-full cursor-pointer overflow-hidden rounded-4 bg-surface-base"
      :style="{ contentVisibility: 'auto', containIntrinsicSize: `${tile.w}px ${tile.h}px` }"
      @click="emit('activate')"
      @keydown.enter.self="emit('activate')"
    >
      <!-- The ring is a counter-scaled border, so it stays visible when zoomed out. It means live. -->
      <div
        class="pointer-events-none absolute inset-0 z-10 rounded-4 border-solid"
        :class="live ? 'border-outline-blue-6' : 'border-outline-gray-2 group-hover:border-outline-gray-4'"
        :style="{ borderWidth: `calc(${live ? 2 : 1}px * var(--inv))` }"
        aria-hidden="true"
      />
      <div
        v-if="tile.isDefault"
        class="pointer-events-none absolute z-20"
        :style="{ left: 'calc(8px * var(--ls))', top: 'calc(8px * var(--ls))', transform: 'scale(var(--ls))', transformOrigin: 'top left' }"
      >
        <Badge label="Default" theme="gray" variant="subtle" size="sm" />
      </div>
      <!-- Only the set's own box shows; the rest of the tile is the tile background. -->
      <div class="absolute overflow-hidden" :style="clip">
        <div v-if="live && sandbox" data-live class="absolute left-0 top-0 cursor-auto" :style="shift">
          <Frame mode="live" :app="app" :path="tile.path" :w="win.w" :h="win.h" :sandbox="sandbox" :target-set="tile.setKey" />
        </div>
        <div v-else-if="snap && !snap.error && near" class="absolute left-0 top-0" :style="shift">
          <div ref="snapEl" inert class="pointer-events-none" :style="{ width: win.w + 'px', height: win.h + 'px' }" v-html="snap.html" />
        </div>
      </div>
      <template v-if="!(live && sandbox)">
        <div v-if="!snap" class="absolute inset-0 bg-surface-gray-2" />
        <div v-else-if="snap.error" class="absolute inset-0 flex items-center justify-center bg-surface-gray-2">
          <div
            class="flex flex-col items-center gap-1 px-2 text-center"
            :style="{ width: 'calc(100% * var(--z))', transform: 'scale(var(--inv))' }"
          >
            <span class="lucide-triangle-alert size-4 text-ink-gray-5" aria-hidden="true" />
            <span class="text-sm text-ink-gray-7">Could not draw this</span>
            <span class="line-clamp-2 break-all font-mono text-xs text-ink-gray-5">{{ snap.error }}</span>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>
