<script setup lang="ts">
import { List } from 'frappe-ui/list'
import TaskRow from './TaskRow.vue'
import { groupOpen, toggleGroup } from '../lib/view'

defineProps<{ group: any; showProject: boolean }>()

// Linear-style single-row grid. Every trailing track is a fixed width, so the
// title track (`minmax(0, 1fr)`) is the only flexible one. It alone absorbs the
// size differences, such as a row with two avatars, and every other column,
// the id and the tags included, lands at the same x on every row.
const taskColumns = [
  'auto', // status icon
  '2.5rem', // id
  'minmax(0, 1fr)', // title
  '14rem', // tags: labels, plus the project in "My tasks"
  '6.5rem', // due date
  '5.5rem', // priority
  '3.5rem', // assignees, fits a two-avatar stack, right aligned
]
</script>

<template>
  <div>
    <button
      class="group flex w-full items-baseline rounded-1 bg-surface-sidebar px-2.5 py-2 text-base transition hover:bg-surface-gray-2"
      @click="toggleGroup(group.key)"
    >
      <span class="font-medium text-ink-gray-8">{{ group.key }}</span>
      <span class="ml-2 text-sm text-ink-gray-5">{{ group.tasks.length }}</span>
      <span class="ml-auto hidden text-sm text-ink-gray-5 group-hover:inline">
        {{ groupOpen(group.key) ? 'Collapse' : 'Expand' }}
      </span>
    </button>

    <List v-if="groupOpen(group.key)" class="mt-1" :columns="taskColumns">
      <TaskRow
        v-for="task in group.tasks"
        :key="task.id"
        :task="task"
        :show-project="showProject"
      />
    </List>
  </div>
</template>
