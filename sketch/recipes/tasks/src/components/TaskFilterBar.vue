<script setup lang="ts">
import {
  Avatar,
  Button,
  Divider,
  Dropdown,
  Select,
  TabButtons,
} from 'frappe-ui'
import {
  imageOf,
  labelDotClass,
  priorityColor,
  priorityIcon,
  statusIcon,
} from '../data'
import {
  activeFilterCount,
  assigneeFilterOptions,
  clearFilters,
  groupByDropdownOptions,
  groupByLabel,
  labelFilterOptions,
  priorityFilterOptions,
  sortDropdownOptions,
  sortLabel,
  statusFilterOptions,
  view,
  visibleTasks,
} from '../lib/view'
</script>

<template>
  <!-- Scope tabs, stackable attribute filters, then group and sort. -->
  <div class="flex flex-wrap items-center gap-2 pt-5">
    <!-- beta.55 TabButtons reads `value` from an option. A label alone never
         updates the model, so every option carries an explicit value. -->
    <TabButtons
      v-model="view.tab"
      :options="[
        { label: 'All', value: 'All' },
        { label: 'Assigned to me', value: 'Assigned to me' },
        { label: 'Created by me', value: 'Created by me' },
      ]"
    />

    <Divider orientation="vertical" class="mx-1" flex-item />

    <Select v-model="view.status" variant="ghost" :options="statusFilterOptions">
      <template #item-prefix="{ item }">
        <span
          v-if="item.value"
          :class="statusIcon[item.value]"
          class="size-4 text-ink-gray-6"
          aria-hidden="true"
        />
      </template>
    </Select>

    <Select
      v-model="view.priority"
      variant="ghost"
      :options="priorityFilterOptions"
    >
      <template #item-prefix="{ item }">
        <span
          v-if="item.value"
          class="size-4"
          :class="[priorityIcon[item.value], priorityColor[item.value]]"
          aria-hidden="true"
        />
      </template>
    </Select>

    <Select
      v-model="view.assignee"
      variant="ghost"
      :options="assigneeFilterOptions"
    >
      <template #item-prefix="{ item }">
        <Avatar
          v-if="item.value"
          :image="imageOf(item.value)"
          :label="item.label"
          size="xs"
        />
      </template>
    </Select>

    <Select v-model="view.label" variant="ghost" :options="labelFilterOptions">
      <template #item-prefix="{ item }">
        <span
          v-if="item.value"
          class="size-2 rounded-full"
          :class="labelDotClass(item.value)"
          aria-hidden="true"
        />
      </template>
    </Select>

    <Button
      v-if="activeFilterCount"
      variant="ghost"
      label="Clear"
      icon-left="lucide-x"
      @click="clearFilters"
    />

    <div class="ml-auto flex items-center gap-2">
      <span class="text-sm text-ink-gray-5">{{ visibleTasks.length }} tasks</span>
      <Dropdown :options="groupByDropdownOptions" align="end">
        <Button variant="ghost" icon-left="lucide-layers">
          Group: {{ groupByLabel }}
        </Button>
      </Dropdown>
      <Dropdown :options="sortDropdownOptions" align="end">
        <Button variant="ghost" icon-left="lucide-arrow-up-down">
          {{ sortLabel }}
        </Button>
      </Dropdown>
    </div>
  </div>
</template>
