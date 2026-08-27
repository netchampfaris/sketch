<script setup lang="ts">
import { ScrollArea, TabButtons } from 'frappe-ui'
import { List, ListCell, ListRow, ListRows } from 'frappe-ui/list'
import type { MailThread } from '../data'

// The list pane. The tabs filter the Inbox only, so a mailbox with no
// categories passes `:tabs="null"` and the strip disappears.
defineProps<{
  threads: MailThread[]
  tabs: string[] | null
  emptyTitle: string
  emptyMessage: string
}>()

// `v-model:active` makes the open thread first-class: the List draws the
// highlight and hides the dividers hugging it, so no per-row class or click.
const active = defineModel<string>('active', { default: '' })
const tab = defineModel<string>('tab', { default: 'Primary' })
</script>

<template>
  <section
    class="flex h-full min-h-0 w-[23rem] shrink-0 flex-col border-r border-outline-gray-1"
  >
    <!-- Category tabs. Pinned above the list: they filter, they do not scroll.
         frappe-ui 1.0.0-beta.55 needs an explicit `value` on every option. -->
    <div
      v-if="tabs"
      class="flex shrink-0 items-center border-b border-outline-gray-1 px-4 py-2"
    >
      <TabButtons
        v-model="tab"
        :options="tabs.map((name) => ({ label: name, value: name }))"
      />
    </div>

    <ScrollArea class="min-h-0 flex-1" viewport-class="p-1">
      <!-- A two-track content and trailing grid, with no leading media. Setting
           `columns` flips the divider default to `full`, so the rules span the
           row edge to edge. `--list-row-padding-x` widens the inline inset;
           the cells carry the vertical padding. -->
      <List
        v-if="threads.length"
        v-model:active="active"
        :columns="['minmax(0,1fr)', 'auto']"
        :style="{ '--list-row-padding-x': '1rem' }"
      >
        <ListRows :items="threads" v-slot="{ item: thread, value }">
          <ListRow :value="value">
            <ListCell>
              <div class="min-w-0 py-3">
                <div
                  class="inline-flex items-center truncate text-base text-ink-gray-8"
                  :class="thread.unread && 'font-semibold text-ink-gray-9'"
                >
                  <!-- Unread dot, inline before the subject. No reserved
                       column, so it only takes space when present. -->
                  <span
                    v-if="thread.unread"
                    class="mr-1.5 inline-block size-2 rounded-full bg-surface-blue-7 align-middle"
                    aria-hidden="true"
                  />{{ thread.subject }}
                </div>
                <p class="mt-0.5 line-clamp-2 text-p-sm text-ink-gray-5">
                  {{ thread.preview }}
                </p>
              </div>
            </ListCell>
            <ListCell class="justify-end self-start pt-3">
              <span class="shrink-0 text-xs text-ink-gray-5">
                {{ thread.time }} ago
              </span>
            </ListCell>
          </ListRow>
        </ListRows>
      </List>

      <!-- Every list gets an empty state. Drafts holds nothing, so this one is
           on screen at /drafts. -->
      <div
        v-else
        class="flex flex-col items-center justify-center gap-3 px-6 py-16 text-center"
      >
        <div class="rounded-full bg-surface-gray-2 p-3 text-ink-gray-5">
          <span class="lucide-inbox size-6" aria-hidden="true" />
        </div>
        <p class="text-base text-ink-gray-7">{{ emptyTitle }}</p>
        <p class="text-p-sm text-ink-gray-5">{{ emptyMessage }}</p>
      </div>
    </ScrollArea>
  </section>
</template>
