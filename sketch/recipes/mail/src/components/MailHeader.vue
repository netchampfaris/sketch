<script setup lang="ts">
import { Button, Dropdown, PageHeaderBase, PageHeaderTitle } from 'frappe-ui'
import { moreActions } from '../data'

// One split header, not two. PageHeaderBase teleports its content to the
// shell's pinned header target, so the bar never scrolls with the panes. The
// padding-free base lines the divider up with the column border below.
defineProps<{
  title: string
  subject: string
  showList: boolean
  hasThread: boolean
}>()

defineEmits<{ (event: 'toggle-list'): void; (event: 'compose'): void }>()
</script>

<template>
  <PageHeaderBase
    class="z-10 flex h-12 border-b border-outline-gray-1 bg-surface-base"
  >
    <!-- List half. Width and right border track the list pane below. -->
    <div
      v-show="showList"
      class="flex w-[23rem] shrink-0 items-center justify-between border-r border-outline-gray-1 px-4"
    >
      <PageHeaderTitle :title="title" />
      <Button
        variant="ghost"
        icon="lucide-pen-line"
        label="Compose"
        @click="$emit('compose')"
      />
    </div>

    <!-- Reading half. Fills the rest. -->
    <div class="flex min-w-0 flex-1 items-center justify-between gap-3 px-5">
      <div class="flex min-w-0 items-center gap-2">
        <Button
          variant="ghost"
          :icon="showList ? 'lucide-panel-left-close' : 'lucide-panel-left'"
          label="Toggle list"
          @click="$emit('toggle-list')"
        />
        <PageHeaderTitle>{{ subject }}</PageHeaderTitle>
      </div>

      <!-- Mail actions: archive, snooze, delete, mark unread, and more. -->
      <div class="flex shrink-0 items-center gap-1">
        <Button
          variant="ghost"
          icon="lucide-archive"
          label="Archive"
          :disabled="!hasThread"
        />
        <Button
          variant="ghost"
          icon="lucide-alarm-clock"
          label="Snooze"
          :disabled="!hasThread"
        />
        <Button
          variant="ghost"
          icon="lucide-trash-2"
          label="Delete"
          :disabled="!hasThread"
        />
        <Button
          variant="ghost"
          icon="lucide-mail"
          label="Mark as unread"
          :disabled="!hasThread"
        />
        <Dropdown :options="moreActions" align="end">
          <Button
            variant="ghost"
            icon="lucide-ellipsis"
            label="More"
            :disabled="!hasThread"
          />
        </Dropdown>
      </div>
    </div>
  </PageHeaderBase>
</template>
