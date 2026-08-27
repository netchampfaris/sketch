<script setup lang="ts">
import { ref } from 'vue'
import {
  Avatar,
  Badge,
  Button,
  Combobox,
  DatePicker,
  MultiSelect,
  ScrollArea,
  Select,
  Textarea,
} from 'frappe-ui'
import {
  imageOf,
  labelDotClass,
  me,
  people,
  priorities,
  priorityColor,
  priorityIcon,
  projects,
  statusIcon,
  statuses,
} from '../data'

const props = defineProps<{ task: any }>()

const statusSelectOptions = statuses.map((s: string) => ({ label: s, value: s }))
const prioritySelectOptions = priorities.map((p: string) => ({
  label: p,
  value: p,
}))
const assigneeOptions = people.map((p: any) => ({
  label: p.name,
  value: p.name,
}))
// Combobox picks up `icon` for both the option rows and the button trigger.
const projectOptions = projects.map((p: any) => ({
  label: p.name,
  value: p.name,
  icon: p.icon,
}))

const newComment = ref('')
function addComment() {
  if (!newComment.value.trim()) return
  props.task.comments.push({
    author: me,
    time: 'Just now',
    text: newComment.value.trim(),
  })
  newComment.value = ''
}
</script>

<template>
  <div class="flex h-full flex-1">
    <ScrollArea class="min-h-0 w-full flex-1">
      <div class="p-6">
        <h1 class="text-2xl-semibold text-ink-gray-8">{{ task.title }}</h1>
        <p class="mt-3 text-p-base text-ink-gray-7">{{ task.description }}</p>

        <div class="mt-10 border-t pt-6">
          <h2 class="text-base-semibold text-ink-gray-8">
            Comments
            <span
              v-if="task.comments.length"
              class="ml-1 font-normal text-ink-gray-5"
            >
              {{ task.comments.length }}
            </span>
          </h2>

          <div class="mt-5 space-y-6">
            <div
              v-for="(comment, i) in task.comments"
              :key="i"
              class="flex gap-3"
            >
              <Avatar
                :image="imageOf(comment.author)"
                :label="comment.author"
                size="lg"
              />
              <div class="min-w-0 flex-1">
                <div class="flex items-baseline gap-2">
                  <span class="text-base-medium text-ink-gray-8">
                    {{ comment.author }}
                  </span>
                  <span class="text-sm text-ink-gray-5">
                    {{ comment.time }}
                  </span>
                </div>
                <p class="mt-1 text-p-base text-ink-gray-7">
                  {{ comment.text }}
                </p>
              </div>
            </div>
          </div>

          <!-- No comments yet is a real state here: most fixtures have none. -->
          <p
            v-if="!task.comments.length"
            class="mt-5 text-p-base text-ink-gray-5"
          >
            No comments yet. Start the thread below.
          </p>

          <div class="mt-6 flex gap-3">
            <Avatar :image="imageOf(me)" :label="me" size="lg" />
            <div class="flex-1">
              <Textarea
                v-model="newComment"
                placeholder="Add a comment"
                class="w-full"
              />
              <div class="mt-2 flex justify-end">
                <Button
                  variant="solid"
                  label="Comment"
                  :disabled="!newComment.trim()"
                  @click="addComment"
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </ScrollArea>

    <!-- Meta panel: a two-column grid of label and control pairs. -->
    <div class="hidden w-[20rem] shrink-0 border-l sm:block">
      <div
        class="grid grid-cols-[5rem_minmax(0,1fr)] items-center gap-y-6 p-6 text-base text-ink-gray-6"
      >
        <div>Status</div>
        <Select v-model="task.status" :options="statusSelectOptions">
          <template #item-prefix="{ item }">
            <span
              :class="statusIcon[item.value]"
              class="size-4 text-ink-gray-6"
              aria-hidden="true"
            />
          </template>
        </Select>

        <div>Assignee</div>
        <MultiSelect
          v-model="task.assignees"
          :options="assigneeOptions"
          placeholder="Assign users"
        >
          <template #item-prefix="{ item }">
            <Avatar :image="imageOf(item.value)" :label="item.label" size="xs" />
          </template>
        </MultiSelect>

        <div>Priority</div>
        <Select v-model="task.priority" :options="prioritySelectOptions">
          <template #item-prefix="{ item }">
            <span
              class="size-4"
              :class="[priorityIcon[item.value], priorityColor[item.value]]"
              aria-hidden="true"
            />
          </template>
        </Select>

        <div>Due date</div>
        <DatePicker v-model="task.due" placeholder="Set due date" format="MMM D">
          <template #prefix>
            <span
              class="lucide-calendar size-4 text-ink-gray-6"
              aria-hidden="true"
            />
          </template>
        </DatePicker>

        <div>Project</div>
        <Combobox
          v-model="task.project"
          trigger="button"
          :options="projectOptions"
          placeholder="Select project"
        />

        <div>Labels</div>
        <div class="flex flex-wrap gap-1.5">
          <Badge
            v-for="label in task.labels"
            :key="label"
            variant="outline"
            theme="gray"
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
        </div>
      </div>
    </div>
  </div>
</template>
