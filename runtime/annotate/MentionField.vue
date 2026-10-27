<script setup lang="ts">
// Wraps a words box (frappe-ui's Textarea, unchanged) and opens a small list of people when "@" is typed. Arrow keys move,
// Enter or Tab picks, Escape closes. The list is frappe-ui's Popover, which keeps the caret in the box. Only people the
// page was given can be picked (comments.ts `mentionable`); the words box holds "@Full Name" and `encode` turns it into
// the stored form when the comment is sent.
import { computed, nextTick, ref } from 'vue'
import { Avatar, Popover } from 'frappe-ui'
import type { Mentionable } from './comments'
import { labelOf, match, openMention, remember } from './mentions'

const props = defineProps<{ modelValue: string }>()
const emit = defineEmits<{ 'update:modelValue': [text: string] }>()

const root = ref<HTMLElement | null>(null)
const open = ref(false)
const query = ref('')
const index = ref(0)
let start = -1
// Escape closes the list for this "@word"; it stays closed until the words change.
let dismissed = -1

const box = () => root.value?.querySelector('textarea') ?? null
const people = computed(() => match(query.value))
const reference = computed(() => (open.value ? (box() ?? undefined) : undefined))

// Look at the caret after anything that moves it or changes the words.
function sync(e?: Event) {
  const ta = box()
  const found = ta && document.activeElement === ta ? openMention(ta.value, ta.selectionStart) : null
  if (e?.type === 'input') dismissed = -1
  if (!found || found.start === dismissed) return void (open.value = false)
  if (!open.value || found.query !== query.value) index.value = 0
  start = found.start
  query.value = found.query
  open.value = true
}

function pick(p: Mentionable) {
  const ta = box()
  if (!ta) return
  remember(p)
  const label = `${labelOf(p)} `
  const next = props.modelValue.slice(0, start) + label + props.modelValue.slice(ta.selectionStart)
  const caret = start + label.length
  open.value = false
  emit('update:modelValue', next)
  nextTick(() => {
    ta.focus()
    ta.setSelectionRange(caret, caret)
  })
}

// Before the box sees the key: while the list is open, the keys that drive it are the list's.
function onKey(e: KeyboardEvent) {
  if (!open.value || e.isComposing) return
  const n = people.value.length
  if (e.key === 'Escape') {
    e.preventDefault()
    e.stopPropagation()
    dismissed = start
    open.value = false
  } else if (n && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
    e.preventDefault()
    index.value = (index.value + (e.key === 'ArrowDown' ? 1 : -1) + n) % n
    nextTick(() => document.querySelector('[data-mention-active]')?.scrollIntoView({ block: 'nearest' }))
  } else if (n && (e.key === 'Enter' || e.key === 'Tab') && !e.shiftKey) {
    e.preventDefault()
    e.stopPropagation()
    pick(people.value[index.value] ?? people.value[0])
  }
}
</script>

<template>
  <Popover v-model:open="open" trigger="manual" side="top" align="start" :offset="6" :auto-focus="false" :reference="reference" bare>
    <template #trigger>
      <div ref="root" @input="sync" @click="sync" @keyup="sync" @keydown.capture="onKey" @focusout="open = false">
        <slot />
      </div>
    </template>
    <div
      data-annotate-ui
      class="w-60 overflow-hidden rounded-[12px] bg-surface-elevation-2 p-1 shadow-lg ring-1 ring-outline-gray-2"
      @mousedown.prevent
    >
      <ul role="listbox" aria-label="People to mention" class="flex max-h-48 flex-col gap-0.5 overflow-y-auto">
        <li v-for="(p, i) in people" :key="p.username" role="presentation">
          <button
            type="button"
            role="option"
            :aria-selected="i === index"
            :data-mention-active="i === index ? '' : undefined"
            class="flex h-8 w-full items-center gap-2 rounded-[8px] px-2 text-left text-p-sm hover:bg-surface-gray-2"
            :class="i === index && 'bg-surface-gray-2'"
            @mouseenter="index = i"
            @click="pick(p)"
          >
            <Avatar class="shrink-0" size="xs" :image="p.image || undefined" :label="p.name" />
            <span class="min-w-0 truncate text-ink-gray-8" :title="p.name">{{ p.name }}</span>
            <span class="ml-auto min-w-0 max-w-[40%] shrink-0 truncate text-ink-gray-5" :title="`@${p.username}`">@{{ p.username }}</span>
          </button>
        </li>
        <li v-if="!people.length" role="presentation" class="px-2 py-1.5 text-p-sm text-ink-gray-5">No one by that name</li>
      </ul>
    </div>
  </Popover>
</template>
