<script setup lang="ts">
import { computed } from 'vue'
import { Breadcrumbs, Button, PageHeader } from 'frappe-ui'
import TaskFilterBar from '../components/TaskFilterBar.vue'
import TaskGroup from '../components/TaskGroup.vue'
import { MY_TASKS } from '../data'
import { activeFilterCount, clearFilters, groupedTasks, view } from '../lib/view'

// The project is implied inside a project view. Show it only in "My tasks".
const showProject = computed(() => view.active === MY_TASKS)
</script>

<template>
  <PageHeader>
    <Breadcrumbs :items="[{ label: view.active }]" />
    <div class="flex items-center gap-2">
      <Button variant="solid" label="Add task" icon-left="lucide-plus" />
    </div>
  </PageHeader>

  <div class="w-full px-3 pb-10 sm:px-6">
    <TaskFilterBar />

    <div class="mt-4 space-y-4">
      <TaskGroup
        v-for="group in groupedTasks"
        :key="group.key"
        :group="group"
        :show-project="showProject"
      />
    </div>

    <!-- Filters can empty the list, so the empty state is a real state. -->
    <div
      v-if="!groupedTasks.length"
      class="flex flex-col items-center justify-center gap-3 py-16 text-center"
    >
      <div class="rounded-full bg-surface-gray-2 p-3 text-ink-gray-5">
        <span class="lucide-list-checks size-6" aria-hidden="true" />
      </div>
      <p class="text-base text-ink-gray-7">No tasks here</p>
      <p class="text-sm text-ink-gray-5">
        {{
          activeFilterCount
            ? 'No task matches the filters you set.'
            : 'Add the first task for this view.'
        }}
      </p>
      <Button
        v-if="activeFilterCount"
        label="Clear filters"
        icon-left="lucide-x"
        class="mt-2"
        @click="clearFilters"
      />
      <Button
        v-else
        variant="solid"
        theme="gray"
        icon-left="lucide-plus"
        label="Add task"
        class="mt-2"
      />
    </div>
  </div>
</template>
