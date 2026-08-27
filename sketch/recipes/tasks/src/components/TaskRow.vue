<script setup lang="ts">
import { computed } from 'vue'
import { Avatar, Badge, Dropdown, Tooltip } from 'frappe-ui'
import { ListCell, ListRow } from 'frappe-ui/list'
import dayjs from 'dayjs'
import {
  imageOf,
  labelDotClass,
  priorityColor,
  priorityIcon,
  statusIcon,
  statuses,
} from '../data'

const props = defineProps<{ task: any; showProject: boolean }>()

// Tasks store due dates as YYYY-MM-DD, the format DatePicker's v-model speaks.
// The list renders the short display form.
const formatDue = (due: string) => (due ? dayjs(due).format('MMM D') : '')

// What the tags column shows, kept within a badge budget so nothing clips
// mid-word. The "My tasks" view spends one slot on the project, the useful
// cross-project context, and one on a label. A project view shows two labels.
// Anything past the budget collapses into a "+N" chip.
const tags = computed(() => {
  const labelBudget = props.showProject ? 1 : 2
  const shown = props.task.labels.slice(0, labelBudget)
  return {
    project: props.showProject ? props.task.project : null,
    labels: shown,
    extra: props.task.labels.length - shown.length,
  }
})

function statusDropdownOptions(task: any) {
  return statuses.map((status: string) => ({
    label: status,
    icon: statusIcon[status],
    onClick: () => (task.status = status),
  }))
}
</script>

<template>
  <ListRow class="h-10" :to="`/task/${task.id}`">
    <ListCell>
      <!-- Changing status must not open the task: stop the click before it
           reaches the row. -->
      <span @click.stop>
        <Tooltip text="Change status">
          <Dropdown :options="statusDropdownOptions(task)">
            <button
              class="flex rounded-full focus:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
            >
              <span
                :class="statusIcon[task.status]"
                class="size-4 text-ink-gray-6"
                :aria-label="task.status"
              />
            </button>
          </Dropdown>
        </Tooltip>
      </span>
    </ListCell>
    <ListCell>
      <span class="text-sm tabular-nums text-ink-gray-4">{{ task.id }}</span>
    </ListCell>
    <ListCell>
      <span class="truncate text-base-medium text-ink-gray-8">
        {{ task.title }}
      </span>
    </ListCell>
    <ListCell class="gap-1.5 overflow-hidden">
      <!-- The project is implied inside a project view. Label it only in the
           cross-project "My tasks" list. -->
      <Badge
        v-if="tags.project"
        variant="outline"
        theme="gray"
        class="shrink-0"
        :label="tags.project"
      />
      <Badge
        v-for="label in tags.labels"
        :key="label"
        variant="outline"
        theme="gray"
        class="shrink-0"
        :label="label"
      >
        <template #prefix>
          <span
            class="size-1.5 rounded-full"
            :class="labelDotClass(label)"
            aria-hidden="true"
          />
        </template>
      </Badge>
      <span v-if="tags.extra" class="shrink-0 text-xs text-ink-gray-4">
        +{{ tags.extra }}
      </span>
    </ListCell>
    <ListCell>
      <span
        v-if="task.due"
        class="flex items-center whitespace-nowrap text-sm text-ink-gray-5"
      >
        <span
          class="lucide-calendar mr-1.5 size-3.5 shrink-0"
          aria-hidden="true"
        />
        {{ formatDue(task.due) }}
      </span>
    </ListCell>
    <ListCell>
      <span
        class="flex items-center whitespace-nowrap text-sm text-ink-gray-5"
      >
        <span
          class="mr-1 size-4 shrink-0"
          :class="[priorityIcon[task.priority], priorityColor[task.priority]]"
          aria-hidden="true"
        />
        {{ task.priority }}
      </span>
    </ListCell>
    <ListCell class="justify-end">
      <Tooltip
        v-if="task.assignees.length"
        :text="task.assignees.join(', ')"
      >
        <div class="flex -space-x-1">
          <Avatar
            v-for="name in task.assignees"
            :key="name"
            :image="imageOf(name)"
            :label="name"
            size="sm"
          />
        </div>
      </Tooltip>
    </ListCell>
  </ListRow>
</template>
