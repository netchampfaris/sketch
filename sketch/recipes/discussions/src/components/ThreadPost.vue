<script setup lang="ts">
import { Avatar, Button, Dropdown } from 'frappe-ui'

defineProps<{
  author: string
  image: string
  time: string
  lead?: boolean
}>()

const postActions = [
  { label: 'Copy link', icon: 'lucide-link' },
  { label: 'Quote reply', icon: 'lucide-quote' },
  { label: 'Report', icon: 'lucide-flag' },
]
</script>

<template>
  <article class="flex gap-3">
    <Avatar :image="image" :label="author" :size="lead ? '2xl' : 'xl'" />
    <div class="min-w-0 flex-1">
      <div class="flex items-center gap-2">
        <span class="text-base-medium text-ink-gray-8">{{ author }}</span>
        <span class="text-sm text-ink-gray-5">{{ time }}</span>
        <Dropdown :options="postActions" class="ml-auto">
          <Button variant="ghost" size="sm" icon="lucide-ellipsis" label="Post actions" />
        </Dropdown>
      </div>
      <div class="mt-2 space-y-3">
        <slot />
      </div>
    </div>
  </article>
</template>
