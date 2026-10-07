<script setup lang="ts">
// The two stacked pills: the page's Variants sets above, the demo States below. Mounted lazily by
// the first <Variants> or useDemoState, in a body-level host.
import { computed, nextTick, ref, shallowRef, watch, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { createReusableTemplate, onClickOutside, useElementSize, useEventListener } from '@vueuse/core'
import { Button, TabButtons } from 'frappe-ui'
import { choices, currentOf, idOf, keepHandler, kept, mirrorStates, sets, stateOf, stateValues, states, type DState, type VSet } from './state'

const [DefineRow, Row] = createReusableTemplate<{ s: VSet | DState; solo?: boolean; plain?: boolean }>({
  inheritAttrs: false,
  // Declared, so a bare `solo` arrives as true rather than as an empty attribute.
  props: { s: { type: Object, required: true }, solo: Boolean, plain: Boolean },
})
const route = useRoute()
const router = useRouter()

// Rows in page order (top to bottom, then left to right). Worked out when the panel opens and when
// the page's sets change, not continuously.
const order = ref<string[]>([])
const here = computed(() => sets.filter((s) => s.path === route.path))
const rows = computed(() => {
  const o = order.value
  return [...here.value].sort((a, b) => (o.indexOf(a.key) + 1 || 99) - (o.indexOf(b.key) + 1 || 99))
})
const rectOf = (s: VSet) => {
  const rs = s.elements().map((e) => e.getBoundingClientRect()).filter((r) => r.width || r.height)
  if (!rs.length) return null
  const x = Math.min(...rs.map((r) => r.left)), y = Math.min(...rs.map((r) => r.top))
  return { x, y, w: Math.max(...rs.map((r) => r.right)) - x, h: Math.max(...rs.map((r) => r.bottom)) - y }
}
function sort() {
  const at = (s: VSet) => rectOf(s) ?? { x: 0, y: 1e9 }
  order.value = [...here.value].sort((a, b) => at(a).y - at(b).y || at(a).x - at(b).x).map((s) => s.key)
}
watch(() => [route.path, here.value.length], () => nextTick(sort), { flush: 'post' })

const open = ref<'variants' | 'states' | null>(null)
const toggle = (which: 'variants' | 'states') => {
  open.value = open.value === which ? null : which
  if (open.value === 'variants') sort()
}
const multi = computed(() => rows.value.length > 1)
const stateRows = computed(() => Object.values(states))
const statesMulti = computed(() => stateRows.value.length > 1)
watch(multi, (m) => !m && open.value === 'variants' && (open.value = null))
watch(statesMulti, (m) => !m && open.value === 'states' && (open.value = null))
useEventListener(document, 'keydown', (e: KeyboardEvent) => {
  if (e.key !== 'Escape' || !open.value) return
  const which = open.value
  open.value = null
  ;(document.querySelector(`[data-pill="${which}"]`) as HTMLElement | null)?.querySelector('button')?.focus()
})

// The launcher in annotate reads this to sit above the pill, and above the panel while it is open.
const stack = ref<HTMLElement | null>(null)
onClickOutside(stack, () => (open.value = null))
const { height } = useElementSize(stack, { width: 0, height: 0 }, { box: 'border-box' })
watch(
  [height, () => rows.value.length + stateRows.value.length],
  ([h, n]) => (n && h ? document.documentElement.style.setProperty('--sketch-variants-h', `${h}px`) : document.documentElement.style.removeProperty('--sketch-variants-h')),
  { immediate: true },
)
onBeforeUnmount(() => document.documentElement.style.removeProperty('--sketch-variants-h'))

// Hovering a row outlines the set on the page.
const hovered = ref<string | null>(null)
const box = shallowRef<{ x: number; y: number; w: number; h: number } | null>(null)
function hover(s: VSet | null) {
  hovered.value = s?.key ?? null
  box.value = s ? rectOf(s) : null
}

// A switch changes the set's size, so the outline is measured again.
watch(choices, () => nextTick(() => hovered.value && hover(rows.value.find((s) => s.key === hovered.value) ?? null)), { deep: true })

const isState = (s: VSet | DState): s is DState => 'count' in s
const opts = (s: VSet | DState) => (isState(s) ? s.options.map((o) => ({ value: o, label: o })) : s.options())
const cur = (s: VSet | DState) => (isState(s) ? stateOf(s) : currentOf(s))
const pick = (s: VSet | DState, v: string) => {
  if (isState(s)) {
    stateValues[s.key] = v
    mirrorStates(router, route)
  } else choices[idOf(s)] = v
}
const off = (s: VSet) => currentOf(s) !== s.options()[0]?.value
const anyOff = computed(() => rows.value.some(off))
const label = (s: VSet) => s.options().find((o) => o.value === currentOf(s))?.label ?? ''
const isKept = (s: VSet) => kept[idOf(s)] === currentOf(s)
const keep = (s: VSet) => {
  const el = s.elements()[0]
  if (!el) return
  keepHandler.value?.(el, `Keep "${label(s)}" for ${s.label}. Remove the other variants and the <Variants> wrapper.`)
  kept[idOf(s)] = currentOf(s)!
}
</script>

<template>
  <DefineRow v-slot="{ s, solo, plain }">
    <!-- In a panel each row is a subgrid, so names, options and Keep line up in columns across rows. -->
    <div
      class="items-center"
      :class="solo ? 'flex gap-2' : 'col-span-full grid grid-cols-subgrid'"
      @mouseenter="hover(plain ? null : (s as VSet))"
      @mouseleave="hover(null)"
    >
      <span class="flex min-w-0 items-center gap-2 text-p-sm" :class="solo ? 'text-ink-gray-5' : 'text-ink-gray-8'">
        <span v-if="!plain && off(s as VSet)" class="size-1.5 shrink-0 rounded-full bg-surface-blue-7" aria-hidden="true" />
        {{ s.label }}
      </span>
      <TabButtons
        class="justify-self-start"
        :options="opts(s)"
        :model-value="cur(s)"
        @update:model-value="(v: string) => pick(s, v)"
      />
      <template v-if="keepHandler && !plain">
        <span class="flex shrink-0 justify-end">
          <span v-if="isKept(s)" class="flex items-center gap-1 text-p-sm text-ink-gray-5">
            <span class="lucide-check size-4" aria-hidden="true" />Kept
          </span>
          <Button
            v-else
            :class="solo || off(s) || hovered === s.key ? '' : 'invisible'"
            variant="ghost"
            :aria-label="`Keep ${label(s)} for ${s.label}`"
            @click="keep(s)"
          >Keep</Button>
        </span>
      </template>
    </div>
  </DefineRow>

  <div v-if="rows.length || stateRows.length" ref="stack" class="pointer-events-none fixed inset-x-3 bottom-3 z-50 flex flex-col items-end gap-2">
    <template v-for="g in (['variants', 'states'] as const)" :key="g">
      <template v-if="(g === 'variants' ? rows : stateRows).length">
        <div
          v-if="(g === 'variants' ? multi : statesMulti) && open === g"
          :id="`sketch-${g}-panel`"
          class="pointer-events-auto max-h-[60vh] w-max max-w-full overflow-y-auto rounded-5 bg-surface-elevation-2 p-3 shadow-lg ring-1 ring-outline-gray-1"
        >
          <div class="grid items-center gap-x-4 gap-y-3" :class="g === 'variants' && keepHandler ? 'grid-cols-[auto_auto_auto]' : 'grid-cols-[auto_auto]'">
            <template v-if="g === 'variants'"><Row v-for="s in rows" :key="idOf(s)" :s="s" /></template>
            <template v-else><Row v-for="s in stateRows" :key="s.key" :s="s" plain /></template>
          </div>
        </div>
        <div :data-pill="g" class="pointer-events-auto rounded-5 bg-surface-elevation-2 shadow-lg ring-1 ring-outline-gray-1" :class="(g === 'variants' ? multi : statesMulti) ? 'p-1' : 'px-3 py-2'">
          <Button
            v-if="g === 'variants' ? multi : statesMulti"
            variant="ghost"
            :icon-left="g === 'variants' ? 'lucide-layers' : 'lucide-sliders-horizontal'"
            :aria-label="g === 'variants' ? 'Variants' : 'States'"
            :aria-controls="`sketch-${g}-panel`"
            :aria-expanded="open === g"
            @click="toggle(g)"
          >
            <span class="flex items-center gap-1.5">
              <span class="text-p-sm text-ink-gray-8">{{ g === 'variants' ? 'Variants' : 'States' }}</span>
              <span class="text-p-sm tabular-nums text-ink-gray-5">{{ (g === 'variants' ? rows : stateRows).length }}</span>
              <span v-if="g === 'variants' && anyOff" class="size-1.5 rounded-full bg-surface-blue-7" aria-hidden="true" />
            </span>
          </Button>
          <Row v-else-if="g === 'variants'" :s="rows[0]" solo />
          <Row v-else :s="stateRows[0]" solo plain />
        </div>
      </template>
    </template>
  </div>

  <!-- The outline over the hovered set's rect. -->
  <div
    v-if="box && hovered"
    class="pointer-events-none fixed z-50 rounded-4 border-2 border-outline-blue-6"
    :style="{ left: `${box.x - 4}px`, top: `${box.y - 4}px`, width: `${box.w + 8}px`, height: `${box.h + 8}px` }"
    aria-hidden="true"
  />
</template>
