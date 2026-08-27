<script setup lang="ts">
import { Button } from 'frappe-ui'

// Shared empty state for the nav items that have no screen of their own.
defineProps<{ label: string; icon: string }>()
</script>

<template>
  <div
    class="flex min-h-[60vh] flex-col items-center justify-center px-4 text-center"
  >
    <div
      class="flex size-11 items-center justify-center rounded-full bg-surface-gray-2"
    >
      <span :class="icon" class="size-5 text-ink-gray-5" aria-hidden="true" />
    </div>
    <div class="mt-3 text-base font-medium text-ink-gray-8">
      No {{ label.toLowerCase() }} yet
    </div>
    <p class="mt-1 max-w-xs text-p-sm text-ink-gray-5">
      This section is part of the app-shell demo. The four highlighted screens
      are fully built.
    </p>
    <Button
      class="mt-4"
      variant="subtle"
      :label="`New ${label.toLowerCase()}`"
      icon-left="lucide-plus"
    />
  </div>
</template>
