<script setup lang="ts">
import { Select, TextInput } from 'frappe-ui'
import { typeIcon, typeOptions } from '../data'

defineProps<{ query: string; type: string }>()

defineEmits<{
  'update:query': [value: string]
  'update:type': [value: string]
}>()
</script>

<template>
  <div class="flex items-center gap-2 pb-3">
    <TextInput
      :model-value="query"
      type="text"
      placeholder="Search files"
      class="w-64"
      @update:model-value="$emit('update:query', String($event))"
    >
      <template #prefix>
        <span class="lucide-search size-4 text-ink-gray-5" aria-hidden="true" />
      </template>
    </TextInput>
    <Select
      :model-value="type"
      :options="typeOptions"
      @update:model-value="$emit('update:type', String($event))"
    >
      <template #item-prefix="{ item }">
        <span
          :class="typeIcon[item.value]"
          class="size-4 text-ink-gray-6"
          aria-hidden="true"
        />
      </template>
    </Select>
  </div>
</template>
