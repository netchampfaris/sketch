<script setup lang="ts">
// One tile: the drawing in a box, a caption under it. The drawing is a snapshot (static DOM, only while near
// the view), a gray box while undrawn, an error box, or a live render. Sizes that stay on screen at any zoom
// use `--ls`, so zooming only scales the layout.
import { computed, nextTick, ref, watch } from 'vue'
import { useIntersectionObserver } from '@vueuse/core'
import { Avatar, Badge, Button, Dropdown, toast } from 'frappe-ui'
import { bridge } from './bridge'
import { canKeepOnly, canMakeDefault, keepFailure, keepOnly, makeDefault, makeFailure } from './default'
import { canDelete, deleteFailure, deleteVariant } from './edit'
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
  // The tile is under ~280px on screen: its actions go on a second line under the label.
  narrow?: boolean
}>()
const emit = defineEmits<{ activate: [e: MouseEvent | KeyboardEvent]; openPage: []; near: [near: boolean] }>()

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

// The label row wraps its actions under the name when the tile is narrow, and on a live tile that also says who made it:
// there is no room for the name, the author and three actions on one line.
const stacked = computed(() => !!props.narrow || (props.live && !!props.tile.author))
const isSet = computed(() => props.tile.kind === 'set')
// The part of the page this tile shows: the set's own box, or the whole window.
const rect = computed(() => {
  if (!isSet.value) return { x: 0, y: 0, w: props.win.w, h: props.win.h }
  const own = props.snap && !props.snap.error ? props.snap.sets.find((s) => s.key === props.tile.setKey) : null
  return own ?? props.tile.meta ?? { x: 0, y: 0, w: props.tile.w - MARGIN * 2, h: props.tile.h - MARGIN * 2 }
})
// Make default: the owner's page only, on the live tile, on an option that is not first. The page reloads once it is
// saved, so the Default badge is on the new first tile when it comes back.
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
    toast.error(makeFailure(e as Error))
  }
}

// Delete variant: on the live tile of an option a teammate made. The page reloads once the file is gone, and the
// Undo toast is shown by the page that comes back (edit.ts).
const deletable = computed(() => !!props.tile.author && !!props.tile.option && canDelete(props.tile.option))
async function deleteIt() {
  if (!deletable.value || saving.value) return
  try {
    await deleteVariant(props.tile.option!, props.tile.opt ?? props.tile.caption)
  } catch (e) {
    toast.error(deleteFailure(e as Error))
  }
}

// Keep only this: the owner's page only, on one of the owner's own options of a set that has others (their own, or a
// teammate's). It cuts the rest from the source, so it sits above Delete variant, and the page that comes back shows
// "Kept …" with Undo (default.ts).
const keepable = computed(() => {
  const t = props.tile
  return t.kind === 'set' && !t.author && !!t.option && !!t.setFile && !!t.setName && (t.setOptions?.length ?? 0) > 1 && canKeepOnly({ file: t.setFile }) && !bridge.tool
})
async function keepIt() {
  if (!keepable.value || saving.value) return
  saving.value = true
  try {
    await keepOnly({ name: props.tile.setName!, file: props.tile.setFile! }, props.tile.option!, props.tile.opt ?? props.tile.caption)
  } catch (e) {
    saving.value = false
    toast.error(keepFailure(e as Error))
  }
}
const menu = computed(() => [
  ...(keepable.value ? [{ label: 'Keep only this', icon: 'lucide-check', onClick: keepIt }] : []),
  ...(deletable.value ? [{ label: 'Delete variant', icon: 'lucide-trash-2', onClick: deleteIt }] : []),
])

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
    <!-- The caption sits under the tile. It is laid out at 1x and scaled to its on-screen size (never larger than at the
         fit zoom), so the row wraps by what the eye sees. Number, name and Default badge on one line; the live tile adds
         Make default (owner) and Open page at the right end. On a stacked tile the badge and the buttons go under the
         name, so the name never truncates away (there is room for one button a line). -->
    <div
      class="absolute left-0 top-full origin-top-left text-p-sm"
      :style="{ width: 'calc(100% / var(--ls))', transform: 'scale(var(--ls))', paddingTop: '8px', lineHeight: '1.3' }"
    >
      <div class="flex items-center gap-x-1.5" :class="stacked ? 'flex-wrap gap-y-0.5' : ''">
        <div class="flex min-w-0 items-center gap-1.5 text-ink-gray-5" :class="stacked ? 'w-full' : ''">
          <span v-if="tile.n" class="tabular-nums text-ink-gray-4">{{ tile.n }}</span>
          <span class="truncate" :title="tile.caption">{{ tile.caption }}</span>
          <span v-if="tile.author" class="flex min-w-0 shrink-[3] items-center gap-1 text-ink-gray-4" :title="`Made by ${personName(tile.author)}`">
            <Avatar class="shrink-0" size="xs" :image="people[tile.author]?.image || undefined" :label="personName(tile.author)" />
            <span class="truncate">Made by {{ shortName(tile.author) }}</span>
          </span>
          <Badge v-if="tile.isDefault && !stacked" class="shrink-0" label="Default" theme="gray" variant="subtle" size="sm" />
        </div>
        <Badge v-if="tile.isDefault && stacked" label="Default" theme="gray" variant="subtle" size="sm" />
        <div v-if="live" data-ui class="flex shrink-0 items-center gap-1" :class="stacked ? '-ml-1.5 max-w-full flex-wrap gap-y-0.5' : '-my-1.5 ml-auto'">
          <Button
            v-if="canDefault && !bridge.tool"
            variant="ghost"
            size="xs"
            :loading="saving"
            :aria-label="`Make ${tile.opt} the default for ${tile.setName}`"
            @click.stop="makeIt"
          >
            <span :class="saving ? 'sr-only' : ''">Make default</span>
          </Button>
          <Button :class="stacked ? '-ml-0.5' : ''" variant="ghost" size="sm" label="Open page" icon-right="lucide-arrow-up-right" @click.stop="emit('openPage')" />
          <Dropdown v-if="menu.length" :options="menu" placement="bottom-end">
            <Button variant="ghost" size="sm" icon="lucide-ellipsis" aria-label="More actions for this variant" @click.stop />
          </Dropdown>
        </div>
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
