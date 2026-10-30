<script setup lang="ts">
// One tile: the drawing in a box, a caption under it. The drawing is a snapshot (static DOM, only while near
// the view), a gray box while undrawn, an error box, or a live render. Sizes that stay on screen at any zoom
// use `--ls`, so zooming only scales the layout.
import { computed, nextTick, ref, watch } from 'vue'
import { useIntersectionObserver } from '@vueuse/core'
import { Avatar, Badge, Button, Dropdown, toast } from 'frappe-ui'
import { avatarTheme } from '../shared/avatarTheme'
import { bridge } from './bridge'
import { canKeepOnly, canMakeDefault, keepFailure, keepOnly, makeDefault, makeFailure } from './default'
import { canDelete, deleteFailure, deleteVariant } from './edit'
import { isNew } from './badges'
import { menuBind } from './menus'
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
const emit = defineEmits<{ activate: [e: MouseEvent | KeyboardEvent]; openPage: []; openStates: []; near: [near: boolean] }>()

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

// A set tile, and a state tile of one option's component states, show the set's own box; the others the whole window.
const isSet = computed(() => !!props.tile.setKey)
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

// Keep only this: the owner's page only, on any option of a set that has others, a teammate's too (the server adopts
// it first). It cuts the rest from the source, so it sits above Delete variant, and the page that comes back shows
// "Kept …" with Undo (default.ts).
const keepable = computed(() => {
  const t = props.tile
  return t.kind === 'set' && !!t.option && !!t.setFile && !!t.setName && (t.setOptions?.length ?? 0) > 1 && canKeepOnly({ file: t.setFile }) && !bridge.tool
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
// Every action of the live tile sits in its one ⋯ menu. A state tile of a component only opens its page.
const menu = computed(() => [
  ...(canDefault.value && !bridge.tool ? [{ label: 'Make default', icon: 'lucide-star', onClick: makeIt }] : []),
  { label: 'Open page', icon: 'lucide-arrow-up-right', onClick: () => emit('openPage') },
  ...(props.tile.kind === 'set' && props.tile.option ? [{ label: 'States', icon: 'lucide-layers', onClick: () => emit('openStates') }] : []),
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
    <!-- The labels are laid out at 1x and scaled to their on-screen size (never larger than at the fit zoom), so a row
         wraps by what the eye sees. Above the tile: number, name, Default and New on the left; on the live tile, its ⋯ on
         the right, holding Make default (owner), Open page, States, Keep only this, Delete variant. Under it: on a teammate's
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
        <!-- The wrapper, not the Dropdown, takes ml-auto: the Dropdown does not pass a class to what it renders. -->
        <span v-if="live" class="-mr-1.5 ml-auto flex shrink-0">
          <Dropdown v-bind="menuBind(`tile:${tile.id}`)" :options="menu" placement="bottom-end">
            <Button variant="ghost" size="xs" icon="lucide-ellipsis" :loading="saving" aria-label="Actions for this variant" @click.stop />
          </Dropdown>
        </span>
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

    <div
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
