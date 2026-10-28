<script setup lang="ts">
// One "Demo" pill at the bottom right. It opens a card with the app-wide states (Role), this page's
// states and this page's Variants sets, one row each. The owner's rows also carry Make default and Keep.
import { computed, nextTick, ref, shallowRef, watch, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { createReusableTemplate, onClickOutside, useElementSize, useEventListener } from '@vueuse/core'
import { Avatar, Button, Dropdown, Tooltip, toast } from 'frappe-ui'
import { avatarTheme } from '../shared/avatarTheme'
import { badges, freshIn, lookAt, pageHasNew } from './badges'
import { bridge } from './bridge'
import { canKeepOnly, canMakeDefault, credential, keepFailure, keepOnly, makeDefault, makeFailure } from './default'
import { people, personName, shortName } from './extras'
import LensMenu from './LensMenu.vue'
import { hasItems } from './picker'
import { pagesModel } from './snapshot'
import { choices, currentOf, idOf, isChoice, nav, onPage, openCanvas, setId, sets, slugOfRoute, states } from './state'
import type { DState, VSet } from './state'

const [DefineRow, Row] = createReusableTemplate<{ s: VSet | DState; role?: boolean }>({
  inheritAttrs: false,
  props: { s: { type: Object, required: true }, role: Boolean },
})
const route = useRoute()
const router = useRouter()

// Variants rows in page order (top to bottom, then left to right), worked out when the card opens.
const order = ref<string[]>([])
const here = computed(() => sets.filter((s) => onPage(route, s.path) && isChoice(s.options())))
const setRows = computed(() => {
  const o = order.value
  return [...here.value].sort((a, b) => (o.indexOf(setId(a)) + 1 || 99) - (o.indexOf(setId(b)) + 1 || 99))
})
const rectOf = (s: VSet) => {
  const rs = s.elements().map((e) => e.getBoundingClientRect()).filter((r) => r.width || r.height)
  if (!rs.length) return null
  const x = Math.min(...rs.map((r) => r.left)), y = Math.min(...rs.map((r) => r.top))
  return { x, y, w: Math.max(...rs.map((r) => r.right)) - x, h: Math.max(...rs.map((r) => r.bottom)) - y }
}
function sort() {
  const at = (s: VSet) => rectOf(s) ?? { x: 0, y: 1e9 }
  order.value = [...here.value].sort((a, b) => at(a).y - at(b).y || at(a).x - at(b).x).map(setId)
}
watch(() => [route.path, here.value.length], () => nextTick(sort), { flush: 'post' })

const appRows = computed(() => Object.values(states).filter((s) => s.path === ''))
const pageStateRows = computed(() => Object.values(states).filter((s) => s.path !== '' && onPage(route, s.path)))
const count = computed(() => appRows.value.length + pageStateRows.value.length + setRows.value.length)

// What is new for this person on this page: options teammates made that nobody here has looked at. Unread threads mark the Comment tool instead.
const optionsOf = (s: VSet) => s.options().map((o) => o.value)
const freshOf = (s: VSet | DState) => (isState(s) ? 0 : freshIn(optionsOf(s)))
const dot = computed(() => pageHasNew(route.path, setRows.value.flatMap(optionsOf)))

const open = ref(false)
const pill = ref<HTMLElement | null>(null)
const toggle = () => {
  open.value = !open.value
  if (open.value) {
    // Opening the card is looking at the page's news: the pill's dot clears. The rows keep theirs until opened.
    badges.opened[route.path] = true
    sort()
    // Tab then runs down the rows from the first dropdown.
    nextTick(() => document.querySelector<HTMLElement>('#sketch-demo-card button')?.focus())
  }
}
watch(count, (n) => !n && (open.value = false))
watch(() => route.path, () => (open.value = false))
const close = (refocus = false) => {
  if (!open.value) return
  open.value = false
  if (refocus) pill.value?.querySelector('button')?.focus()
}
useEventListener(document, 'keydown', (e: KeyboardEvent) => {
  if (e.key !== 'Escape' || !open.value) return
  // An open menu takes the Esc first.
  if (document.querySelector('.menu-content')) return
  close(true)
})

const stack = ref<HTMLElement | null>(null)
// A menu opened from a row is portalled out of the stack; picking from it must not close the card.
onClickOutside(stack, () => close(), { ignore: ['.menu-content'] })
const { height } = useElementSize(stack, { width: 0, height: 0 }, { box: 'border-box' })
const { width: pillW } = useElementSize(pill, { width: 0, height: 0 }, { box: 'border-box' })
// On a phone the stack sits above the page's MobileNav bar, when it has one, so the annotate button and the toasts rise with it.
const navH = ref(0)
// With a bar the stack sits 4.75rem (76px) from the bottom, as the original did; a taller bar lifts it further.
const lift = computed(() => {
  const bar = navH.value ? Math.max(navH.value + 6, 64) : 0
  // The open toolbar on a phone sits at the bottom edge; the pill rides above it (the stack is 0.75rem, 12px, up already).
  const inTheWay = bridge.toolbarLift > 0 && bridge.toolbarRight + 8 > window.innerWidth - 12 - pillW.value
  return Math.max(bar, inTheWay ? bridge.toolbarLift - 12 : 0)
})
function measureNav() {
  const bar = window.matchMedia('(max-width: 767px)').matches ? document.querySelector<HTMLElement>('[data-slot="mobile-nav"]') : null
  navH.value = bar ? Math.floor(bar.getBoundingClientRect().height) : 0
}
measureNav()
useEventListener(window, 'resize', measureNav)
watch(() => route.path, () => nextTick(measureNav), { flush: 'post' })
watch(
  [height, count, lift],
  ([h, n, bar]) => (n && h ? document.documentElement.style.setProperty('--sketch-variants-h', `${h + bar}px`) : document.documentElement.style.removeProperty('--sketch-variants-h')),
  { immediate: true },
)
onBeforeUnmount(() => document.documentElement.style.removeProperty('--sketch-variants-h'))

// Hovering a Variants row outlines the set on the page.
const hovered = ref<string | null>(null)
const box = shallowRef<{ x: number; y: number; w: number; h: number } | null>(null)
function hover(s: VSet | null) {
  hovered.value = s ? setId(s) : null
  box.value = s ? rectOf(s) : null
}
watch([() => route.path, open], () => hover(null))
watch(choices, () => nextTick(() => hovered.value && hover(setRows.value.find((s) => setId(s) === hovered.value) ?? null)), { deep: true })

const isState = (s: VSet | DState): s is DState => 'count' in s
const labelOf = (s: VSet) => s.options().find((o) => o.value === currentOf(s))?.label ?? ''
// Who made the picked option, when a teammate did: the closed row says so, not only the open menu.
const authorOf = (s: VSet) => s.options().find((o) => o.value === currentOf(s))?.author
const menuOf = (s: VSet) =>
  s.options().map((o) => ({
    label: o.label,
    author: o.author,
    selected: o.value === currentOf(s),
    onClick: () => (choices[idOf(s.path, s.key)] = o.value),
  }))

function go(id: string) {
  close()
  const opener = pill.value?.querySelector('button') ?? null
  openCanvas(router, id)
  // The card is gone by now; Esc should land back on the Demo pill.
  nav.opener = opener
}
// The page slug a set is filed under in the canvas's picks.
const pageSlug = (path: string) => {
  const record = (router.options.routes as any[]).find((r) => r.path === path)
  return record ? slugOfRoute(record) : ''
}
// A State row opens the page's states; a Variants row opens that set.
function compare(s: VSet | DState) {
  go(isState(s) ? `page:${s.path}` : `set:${pageSlug(s.path)}/${s.key}`)
}
// The foot of the card: this page's first set, else its states, else the first thing the canvas has.
const hereStates = computed(() => pageStateRows.value.length > 0)
const canOpen = computed(() => setRows.value.some((s) => s.path !== '') || hereStates.value || !pagesModel.value || pagesModel.value.some(hasItems))
function openHere() {
  const first = setRows.value.find((s) => s.path !== '')
  go(first ? `set:${pageSlug(first.path)}/${first.key}` : hereStates.value ? `page:${pageStateRows.value[0].path}` : 'auto')
}
const off = (s: VSet) => currentOf(s) !== s.options()[0]?.value
// The owner's rows carry two more actions (only the owner's page has the credential).
const actions = computed(() => Boolean(credential.value))
// The column is only there while a row is off its default; otherwise the card is as narrow as a commenter's.
const actionsShown = computed(() => actions.value && setRows.value.some(off))
// Make default: the pick becomes the first slot in the source. The page reloads once it is saved.
const saving = ref<string | null>(null)
const held = ref(0)
async function makeIt(s: VSet, e: MouseEvent) {
  const option = currentOf(s)
  if (!option || saving.value) return
  held.value = (e.currentTarget as HTMLElement).offsetWidth
  saving.value = setId(s)
  try {
    await makeDefault(s, option)
  } catch (err) {
    saving.value = null
    toast.error(makeFailure(err as Error))
  }
}
// Keep only this: the same server action as the canvas tile's menu. The page reloads with "Kept …" and Undo.
async function keepIt(s: VSet) {
  const option = currentOf(s)
  if (!option || saving.value) return
  saving.value = setId(s)
  hover(null)
  try {
    await keepOnly(s, option, labelOf(s))
  } catch (err) {
    saving.value = null
    toast.error(keepFailure(err as Error))
  }
}
const rowLabel = (s: VSet | DState) => (isState(s) && !role(s) ? 'State' : s.label)
const role = (s: VSet | DState) => isState(s) && s.path === ''
const rowName = (s: VSet | DState) => (isState(s) ? `${s.label} states` : s.label)
</script>

<template>
  <DefineRow v-slot="{ s, role }">
    <!-- Each row is a subgrid of the card, so labels, controls and Compare line up across rows. -->
    <div
      class="col-span-full grid grid-cols-subgrid items-center py-0.5"
      @mouseenter="hover(isState(s) ? null : (s as VSet))"
      @mouseleave="hover(null)"
    >
      <span class="flex min-w-0 items-center pl-2 text-p-sm text-ink-gray-5 max-md:max-w-[7rem]">
        <span class="whitespace-nowrap max-md:whitespace-normal">{{ rowLabel(s) }}</span>
        <span
          v-if="freshOf(s)"
          class="ml-1.5 size-1.5 shrink-0 rounded-full bg-surface-blue-6"
          role="img"
          :title="`${freshOf(s)} new since you last looked`"
          :aria-label="`${freshOf(s)} new since you last looked`"
        />
      </span>
      <div v-if="isState(s)" class="justify-self-start"><LensMenu :state="s" :show-name="false" /></div>
      <div v-else class="min-w-0 justify-self-start">
        <Dropdown :options="menuOf(s as VSet)" @update:open="(o: boolean) => o && lookAt(optionsOf(s as VSet))">
          <Button variant="ghost" :aria-label="`${s.label}: ${labelOf(s as VSet)}`">
            <span class="flex items-center gap-1.5">
              <span class="max-w-[16rem] truncate text-p-sm text-ink-gray-8 max-md:max-w-[9rem]" :title="labelOf(s as VSet)">{{ labelOf(s as VSet) }}</span>
              <Tooltip v-if="authorOf(s as VSet)" :text="`Made by ${personName(authorOf(s as VSet)!)}`">
                <Avatar
                  class="shrink-0 ring-1 ring-outline-gray-2"
                  size="xs"
                  :theme="avatarTheme(authorOf(s as VSet)!)"
                  :image="people[authorOf(s as VSet)!]?.image || undefined"
                  :label="personName(authorOf(s as VSet)!)"
                />
              </Tooltip>
              <span class="lucide-chevron-down size-3.5 shrink-0 text-ink-gray-5" aria-hidden="true" />
            </span>
          </Button>
          <template #item-prefix="{ item }">
            <span class="size-4 shrink-0" :class="item.selected ? 'lucide-check' : ''" aria-hidden="true" />
          </template>
          <template #item-label="{ item }">
            <span class="flex min-w-0 max-w-[20rem] items-center gap-2">
              <span class="truncate" :title="item.label">{{ item.label }}</span>
              <span v-if="item.author" class="flex h-4 shrink-0 items-center gap-1 text-p-sm leading-4 text-ink-gray-5" :title="`Made by ${personName(item.author)}`">
                <Avatar size="xs" :theme="avatarTheme(item.author)" :image="people[item.author]?.image || undefined" :label="personName(item.author)" />Made by {{ shortName(item.author) }}
              </span>
            </span>
          </template>
        </Dropdown>
      </div>
      <template v-if="actionsShown">
        <!-- On a phone the actions sit on their own line under the dropdown, and only a row that has something to do shows one. -->
        <span
          v-if="!isState(s)"
          class="flex shrink-0 items-center justify-end gap-1 max-md:col-span-2 max-md:col-start-2 max-md:row-start-2 max-md:justify-start"
          :class="!off(s as VSet) ? 'max-md:hidden' : ''"
        >
          <Button
            v-if="canMakeDefault(s as VSet)"
            :class="off(s as VSet) ? '' : 'invisible max-md:hidden'"
            variant="ghost"
            :loading="saving === setId(s as VSet)"
            :disabled="!!saving"
            :style="saving === setId(s as VSet) && held ? { width: `${held}px` } : undefined"
            :tabindex="off(s as VSet) ? undefined : -1"
            :aria-label="`Make ${labelOf(s as VSet)} the default for ${s.label}`"
            @click="makeIt(s as VSet, $event)"
          ><span class="text-p-sm" :class="saving === setId(s as VSet) ? 'sr-only' : ''">Make default</span></Button>
          <Button
            v-if="canKeepOnly(s as VSet)"
            :class="off(s as VSet) || hovered === setId(s as VSet) ? '' : 'invisible max-md:hidden'"
            variant="ghost"
            :loading="saving === setId(s as VSet)"
            :disabled="!!saving"
            :tabindex="off(s as VSet) || hovered === setId(s as VSet) ? undefined : -1"
            :aria-label="`Keep only ${labelOf(s as VSet)} for ${s.label}`"
            @click="keepIt(s as VSet)"
          ><span class="text-p-sm" :class="saving === setId(s as VSet) ? 'sr-only' : ''">Keep only this</span></Button>
        </span>
        <span v-else class="max-md:hidden" />
      </template>
      <span class="flex shrink-0 items-center justify-end gap-1 max-md:col-start-3 max-md:row-start-1">
        <Tooltip v-if="!role && (isState(s) || s.path !== '')" text="Compare on canvas">
          <Button variant="ghost" icon="lucide-columns-2" :aria-label="`Compare ${rowName(s)} on the canvas`" @click="compare(s)" />
        </Tooltip>
      </span>
    </div>
  </DefineRow>

  <div
    v-if="count"
    ref="stack"
    data-sketch-ui="variants"
    class="pointer-events-none fixed inset-x-3 z-50 flex flex-col items-end gap-2"
    :style="{ bottom: `calc(0.75rem + ${lift}px)` }"
  >
    <div
      v-if="open"
      id="sketch-demo-card"
      class="pointer-events-auto max-h-[60vh] w-max max-w-full overflow-y-auto rounded-[16px] bg-surface-elevation-2 p-2 shadow-lg ring-1 ring-outline-gray-2"
    >
      <div
        class="grid grid-cols-[auto_minmax(0,max-content)_auto] items-center gap-x-2"
        :class="actionsShown ? 'md:grid-cols-[auto_minmax(0,max-content)_auto_auto]' : ''"
      >
        <Row v-for="s in appRows" :key="'a' + s.key" :s="s" role />
        <Row v-for="s in pageStateRows" :key="'s' + s.key" :s="s" />
        <Row v-for="s in setRows" :key="setId(s)" :s="s" />
      </div>
      <Button v-if="canOpen" class="mt-0.5 w-full !justify-start" variant="ghost" icon-left="lucide-columns-2" label="Open canvas" @click="openHere" />
    </div>
    <div ref="pill" data-pill="demo" class="pointer-events-auto rounded-5 bg-surface-elevation-2 p-1 shadow-lg ring-1 ring-outline-gray-2">
      <Button variant="ghost" aria-controls="sketch-demo-card" :aria-expanded="open" :class="open ? 'bg-surface-gray-3' : ''" @click="toggle">
        <span class="flex items-center gap-1.5">
          <span class="text-p-sm text-ink-gray-8">Demo</span>
          <span v-if="dot && !open" class="size-1.5 shrink-0 rounded-full bg-surface-blue-6" role="img" aria-label="New on this page" />
          <span class="size-3.5 text-ink-gray-5" :class="open ? 'lucide-chevron-up' : 'lucide-chevron-down'" aria-hidden="true" />
        </span>
      </Button>
    </div>
  </div>

  <!-- The outline over the hovered set's rect. -->
  <div
    v-if="box && hovered"
    data-sketch-ui="variants"
    class="pointer-events-none fixed z-50 rounded-4 border-2 border-outline-blue-6"
    :style="{ left: `${box.x - 4}px`, top: `${box.y - 4}px`, width: `${box.w + 8}px`, height: `${box.h + 8}px` }"
    aria-hidden="true"
  />
</template>
