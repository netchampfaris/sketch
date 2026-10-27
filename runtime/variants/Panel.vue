<script setup lang="ts">
// The "Show" list: search, then the groups of things to show. A floating card on the right on desktop; inside
// the Show dropdown on a phone (`embedded`).
import { computed, nextTick, ref, watch } from 'vue'
import { Button, ScrollArea, TextInput, Tooltip } from 'frappe-ui'
import type { PickItem } from './picker'

const props = defineProps<{ items: PickItem[]; selected: string; embedded?: boolean }>()
const emit = defineEmits<{ choose: [value: string]; hide: [] }>()

const GROUPS = [
  { key: 'sets', title: 'Variant sets' },
  { key: 'states', title: 'States across pages' },
  { key: 'pages', title: 'Pages' },
] as const

const query = ref('')
const folded = ref<Record<string, boolean>>({})
const groups = computed(() => {
  const q = query.value.trim().toLowerCase()
  return GROUPS.map((g) => ({
    ...g,
    items: props.items.filter((i) => i.group === g.key && (!q || `${i.label} ${i.sub ?? ''}`.toLowerCase().includes(q))),
  })).filter((g) => g.items.length)
})
const isFolded = (key: string) => !query.value.trim() && !!folded.value[key]
// Rows the arrow keys can reach, in order.
const rows = computed(() => groups.value.flatMap((g) => (isFolded(g.key) ? [] : g.items)))
const indexOf = (i: PickItem) => rows.value.indexOf(i)

const active = ref(-1)
watch([query, () => props.items], () => (active.value = query.value.trim() ? 0 : -1))
function move(d: number) {
  const n = rows.value.length
  if (!n) return
  const from = active.value < 0 ? rows.value.findIndex((r) => r.value === props.selected) : active.value
  active.value = (from + d + n) % n
  nextTick(() => document.querySelector(`[data-panel-row="${active.value}"]`)?.scrollIntoView({ block: 'nearest' }))
}
function enter() {
  const r = rows.value[active.value < 0 ? 0 : active.value]
  if (r) emit('choose', r.value)
}
// Incomplete states stand out; everything else is quiet.
const countClass = (i: PickItem) =>
  i.value === props.selected ? 'text-ink-gray-7' : i.group === 'states' && !i.complete ? 'text-ink-gray-8' : 'text-ink-gray-5'
</script>

<template>
  <component
    :is="embedded ? 'div' : 'aside'"
    :data-canvas-panel="embedded ? undefined : ''"
    :aria-label="embedded ? undefined : 'Show on the canvas'"
    class="flex flex-col p-2"
    :class="embedded ? '' : 'absolute right-3 top-3 z-10 max-h-[calc(100%-1.5rem)] w-72 overflow-hidden rounded-[16px] bg-surface-elevation-2 shadow-lg ring-1 ring-outline-gray-2'"
    :style="embedded ? { width: 'var(--reka-popover-trigger-width)' } : undefined"
    data-ui
  >
    <div class="flex items-center gap-1">
      <TextInput
        v-model="query"
        class="min-w-0 flex-1 [&_input]:focus:ring-outline-gray-3"
        placeholder="Search"
        aria-label="Search sets, states and pages"
        autocomplete="off"
        @keydown.down.prevent="move(1)"
        @keydown.up.prevent="move(-1)"
        @keydown.enter.prevent="enter"
      >
        <template #prefix><span class="lucide-search size-4 text-ink-gray-5" aria-hidden="true" /></template>
      </TextInput>
      <Tooltip v-if="!embedded" text="Hide panel">
        <Button variant="ghost" icon="lucide-panel-right" aria-label="Hide panel" @click="emit('hide')" />
      </Tooltip>
    </div>

    <ScrollArea class="mt-2 min-h-0 shrink" :style="embedded ? { maxHeight: 'calc(100dvh - 7.5rem)' } : undefined">
      <!-- A fixed width: the scroll area sizes its content to the widest row, which would push long names out of the card. -->
      <div :style="{ width: embedded ? 'calc(var(--reka-popover-trigger-width) - 1rem)' : '17rem' }" class="min-w-0">
        <p v-if="!groups.length" class="px-2 py-2 text-p-sm text-ink-gray-5">Nothing matches “{{ query.trim() }}”</p>
        <section v-for="(g, gi) in groups" :key="g.key" :class="gi ? 'mt-1 border-t border-outline-gray-2 pt-1' : ''">
          <button
            type="button"
            class="group flex h-7 w-full items-center gap-1 px-2 text-left text-xs font-medium text-ink-gray-5"
            :aria-expanded="!isFolded(g.key)"
            @click="folded[g.key] = !folded[g.key]"
          >
            <span class="truncate">{{ g.title }}</span>
            <span
              class="size-3 shrink-0 text-ink-gray-4 group-hover:opacity-100"
              :class="isFolded(g.key) ? 'lucide-chevron-right' : 'lucide-chevron-down opacity-0'"
              aria-hidden="true"
            />
          </button>
          <template v-if="!isFolded(g.key)">
            <button
              v-for="i in g.items"
              :key="i.value"
              type="button"
              :data-panel-row="indexOf(i)"
              :aria-current="i.value === selected ? 'true' : undefined"
              :title="i.sub ? `${i.label} · ${i.sub}` : i.label"
              class="flex h-8 w-full items-center gap-1.5 rounded-[8px] px-2 text-left text-p-sm hover:bg-surface-gray-2"
              :class="i.value === selected ? 'bg-surface-gray-3' : indexOf(i) === active ? 'bg-surface-gray-2' : ''"
              @click="emit('choose', i.value)"
            >
              <span class="min-w-0 truncate" :class="i.value === selected ? 'font-medium text-ink-gray-9' : 'text-ink-gray-8'">{{ i.label }}</span>
              <span v-if="i.sub" class="shrink-0 text-ink-gray-5">{{ i.sub }}</span>
              <span class="ml-auto shrink-0 pl-2 tabular-nums" :class="countClass(i)">{{ i.short }}</span>
            </button>
          </template>
        </section>
      </div>
    </ScrollArea>
  </component>
</template>
