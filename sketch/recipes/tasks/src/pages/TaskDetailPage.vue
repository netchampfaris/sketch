<script setup lang="ts">
import { computed } from 'vue'
import { Breadcrumbs, Button, PageHeader } from 'frappe-ui'
import TaskDetail from '../components/TaskDetail.vue'
import { tasks } from '../data'
import { view } from '../lib/view'

// The route hands the id in as a string prop.
const props = defineProps<{ id: string }>()

const task = computed(() => tasks.find((t: any) => String(t.id) === props.id))
</script>

<template>
  <PageHeader>
    <Breadcrumbs
      :items="[
        { label: view.active, route: { path: '/' } },
        { label: task ? task.title : 'Not found' },
      ]"
    />
  </PageHeader>

  <TaskDetail v-if="task" :task="task" />

  <div
    v-else
    class="flex flex-col items-center justify-center gap-3 py-16 text-center"
  >
    <div class="rounded-full bg-surface-gray-2 p-3 text-ink-gray-5">
      <span class="lucide-search-x size-6" aria-hidden="true" />
    </div>
    <p class="text-base text-ink-gray-7">No task with id {{ id }}</p>
    <p class="text-sm text-ink-gray-5">It may have been deleted.</p>
    <Button
      label="Back to tasks"
      icon-left="lucide-arrow-left"
      class="mt-2"
      :route="{ path: '/' }"
    />
  </div>
</template>
