<script setup lang="ts">
// One tile: the drawing in a box, a caption under it. The drawing is a snapshot (static DOM, only while near
// the view), a gray box while undrawn, an error box, or a live render. Sizes that stay on screen at any zoom
// use `--ls`, so zooming only scales the layout.
import { computed, nextTick, ref, watch } from 'vue'
import { useIntersectionObserver } from '@vueuse/core'
import { Avatar, Badge, Button } from 'frappe-ui'
import { avatarTheme } from '../shared/avatarTheme'
import { bridge } from './bridge'
import { isNew } from './badges'
import { people, personName, shortName } from './extras'
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
const emit = defineEmits<{ activate: [e: MouseEvent | KeyboardEvent]; near: [near: boolean] }>()

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
// The live tile's ⋯: its menu (Make default, Open page, Keep only this, Delete variant) is the Viewer shell's
// (runtime/shell/TileMenu.vue), which knows who is reading and saves over the session. The ⋯ only says where it is.
function askMenu(e: MouseEvent) {
  const r = (e.currentTarget as HTMLElement).getBoundingClientRect()
  bridge.tileMenu?.(props.tile.id, { x: r.left, y: r.top, w: r.width, h: r.height })
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
  <div class="group/tile absolute" :data-tile-id="tile.id" :style="{ left: tile.x + 'px', top: tile.y + 'px', width: tile.w + 'px', height: tile.h + 'px' }">
    <!-- The labels are laid out at 1x and scaled to their on-screen size (never larger than at the fit zoom), so a row
         wraps by what the eye sees. Above the tile: number, name, Default and New on the left; on the live tile, its ⋯ on
         the right, holding Make default (owner), Open page, Keep only this, Delete variant. Under it: on a teammate's
         option, their face and "by Arohi" (the owner's own options say nothing there). Other tiles keep that row empty, so tiles line up. -->
    <div
      class="absolute bottom-full left-0 origin-bottom-left text-p-sm"
      :style="{ width: 'calc(100% / var(--ls))', transform: 'scale(var(--ls))', paddingBottom: '8px', lineHeight: '1.3' }"
    >
      <div data-tile-row="1" data-ui class="flex h-6 min-w-0 items-center gap-1.5 text-ink-gray-5">
        <span v-if="tile.n" class="shrink-0 tabular-nums text-ink-gray-4">{{ tile.n }}</span>
        <span class="truncate" :title="tile.caption">{{ tile.caption }}</span>
        <Badge v-if="tile.isDefault" class="shrink-0" label="Default" theme="gray" variant="subtle" size="sm" />
        <Badge v-if="tile.author && tile.option && isNew(tile.option)" class="shrink-0" label="New" theme="blue" variant="subtle" size="sm" />
        <Button
          v-if="live"
          class="-mr-1.5"
          variant="ghost"
          size="xs"
          icon="lucide-ellipsis"
          :loading="bridge.busyTile === tile.id"
          :data-state="bridge.menuTile === tile.id ? 'open' : 'closed'"
          :aria-expanded="bridge.menuTile === tile.id"
          aria-label="Actions for this variant"
          aria-haspopup="menu"
          @click.stop="askMenu"
        />
      </div>
    </div>
    <div
      class="absolute left-0 top-full origin-top-left text-p-sm"
      :style="{ width: 'calc(100% / var(--ls))', transform: 'scale(var(--ls))', paddingTop: '8px', lineHeight: '1.3' }"
    >
      <div data-tile-row="2" class="flex h-6 min-w-0 items-center gap-1">
        <span v-if="tile.author" class="flex min-w-0 items-center gap-1 text-p-sm text-ink-gray-5">
          <Avatar class="shrink-0" size="xs" :theme="avatarTheme(tile.author)" :image="people[tile.author]?.image || undefined" :label="personName(tile.author)" />
          <span class="truncate">by {{ shortName(tile.author) }}</span>
        </span>
      </div>
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
      :aria-label="`${tile.pageTitle} · ${tile.opt ?? tile.caption}${tile.isDefault ? ' (default)' : ''}, ${bridge.tool === 'comment' ? 'add a comment' : bridge.tool === 'note' ? 'add a note' : 'open live'}`"
      class="group relative h-full w-full overflow-hidden rounded-4 bg-surface-base"
      :class="bridge.tool ? 'cursor-crosshair' : 'cursor-pointer'"
      :style="{ contentVisibility: 'auto', containIntrinsicSize: `${tile.w}px ${tile.h}px` }"
      @click="emit('activate', $event)"
      @keydown.enter.self="emit('activate', $event)"
    >
      <!-- The ring is a counter-scaled border, so it stays visible when zoomed out. It means live. -->
      <div
        class="pointer-events-none absolute inset-0 z-10 rounded-4 border-solid"
        :class="live ? 'border-outline-blue-6' : 'border-outline-gray-2 group-hover:border-outline-gray-4'"
        :style="{ borderWidth: `calc(${live ? 2 : 1}px * var(--inv))` }"
        aria-hidden="true"
      />
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
