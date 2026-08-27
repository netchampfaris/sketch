<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  Avatar,
  Badge,
  Button,
  PageHeader,
  PageHeaderTitle,
  TabButtons,
} from 'frappe-ui'
import {
  List,
  ListCell,
  ListHeader,
  ListHeaderCell,
  ListHeaderCellSort,
  ListRow,
  ListRows,
} from 'frappe-ui/list'
import EmptyState from '../components/EmptyState.vue'
import {
  priorityDot,
  slaTextClass,
  statusTheme,
  tickets,
  viewFilter,
  viewLabel,
} from '../data'

// One page serves the ticket list and the four saved views. The path picks the
// filter, so every route is parameterless.
const route = useRoute()
const isMainList = computed(() => route.path === '/')
const title = computed(() => viewLabel[route.path] ?? 'Tickets')

const filterTab = ref('Open')

// The Open / All tabs belong to the main list. A saved view brings its own
// filter, so the tabs are hidden there.
const filteredTickets = computed(() => {
  const filter = viewFilter[route.path]
  if (filter) return tickets.filter(filter)
  if (filterTab.value === 'Open') {
    return tickets.filter((t) => ['Open', 'Replied'].includes(t.status))
  }
  return tickets
})

// Sort state, the toggle rules, and the comparator are app code. The header
// cells only draw chrome for the `direction` they are given.
const sortField = ref('modified')
const sortDirection = ref<'asc' | 'desc'>('asc')

function toggleSort(field: string) {
  if (sortField.value === field) {
    sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortField.value = field
    sortDirection.value = 'asc'
  }
}

function directionFor(field: string) {
  return sortField.value === field ? sortDirection.value : null
}

const priorityRank: Record<string, number> = {
  Urgent: 0,
  High: 1,
  Medium: 2,
  Low: 3,
}
const sortedTickets = computed(() => {
  const factor = sortDirection.value === 'desc' ? -1 : 1
  return [...filteredTickets.value].sort((a, b) => {
    if (sortField.value === 'priority') {
      return factor * (priorityRank[a.priority] - priorityRank[b.priority])
    }
    return factor * (a.modified - b.modified)
  })
})

const selection = ref([])

// A row selected on one view must not stay selected on the next.
watch(() => route.path, () => (selection.value = []))

// frappe-ui 1.0.0-beta.55 reads `value` off every TabButtons option, so the
// label alone is no longer enough.
const filterOptions = [
  { label: 'Open', value: 'Open' },
  { label: 'All', value: 'All' },
]
</script>

<template>
  <PageHeader>
    <div class="flex items-center gap-2">
      <PageHeaderTitle :title="title" />
      <span v-if="selection.length" class="text-sm text-ink-gray-5">
        {{ selection.length }} selected
      </span>
    </div>
    <div class="flex items-center gap-2">
      <template v-if="selection.length">
        <Button label="Assign" icon-left="lucide-user-plus" />
        <Button label="Close tickets" icon-left="lucide-check" />
      </template>
      <template v-else>
        <TabButtons
          v-if="isMainList"
          v-model="filterTab"
          :options="filterOptions"
        />
        <Button label="Filter" icon-left="lucide-list-filter" />
        <Button variant="solid" label="New ticket" icon-left="lucide-plus" />
      </template>
    </div>
  </PageHeader>

  <div class="px-3 pt-3 pb-10 sm:px-5">
    <List
      v-if="sortedTickets.length"
      class="w-full list-row-px-3"
      :columns="['minmax(0,1fr)', '11rem', '6.5rem', '6rem', '9rem', '5rem']"
      :row-height="60"
      selectable
      v-model:selection="selection"
    >
      <ListHeader>
        <ListHeaderCell>Subject</ListHeaderCell>
        <ListHeaderCell>Response / Resolution</ListHeaderCell>
        <ListHeaderCell>Status</ListHeaderCell>
        <ListHeaderCellSort
          :direction="directionFor('priority')"
          @click="toggleSort('priority')"
        >
          Priority
        </ListHeaderCellSort>
        <ListHeaderCell>Assigned to</ListHeaderCell>
        <ListHeaderCellSort
          :direction="directionFor('modified')"
          align="end"
          @click="toggleSort('modified')"
        >
          Modified
        </ListHeaderCellSort>
      </ListHeader>
      <ListRows :items="sortedTickets" v-slot="{ item: ticket, value }">
        <ListRow :value="value" @click="() => {}">
          <ListCell>
            <div class="min-w-0">
              <div class="truncate text-base text-ink-gray-8">
                {{ ticket.subject }}
              </div>
              <div class="mt-1.5 truncate text-sm text-ink-gray-5">
                #{{ ticket.id }} · {{ ticket.customer }}
              </div>
            </div>
          </ListCell>
          <ListCell>
            <div class="min-w-0 leading-tight">
              <div class="flex items-center gap-1.5" title="First response">
                <span
                  class="lucide-reply size-3.5 shrink-0 text-ink-gray-4"
                  aria-hidden="true"
                />
                <span
                  class="truncate text-sm"
                  :class="slaTextClass[ticket.firstResponse.state]"
                >
                  {{ ticket.firstResponse.label }}
                </span>
              </div>
              <div class="mt-1.5 flex items-center gap-1.5" title="Resolution">
                <span
                  class="lucide-circle-check size-3.5 shrink-0 text-ink-gray-4"
                  aria-hidden="true"
                />
                <span
                  class="truncate text-sm"
                  :class="slaTextClass[ticket.resolution.state]"
                >
                  {{ ticket.resolution.label }}
                </span>
              </div>
            </div>
          </ListCell>
          <ListCell>
            <Badge
              :theme="statusTheme[ticket.status]"
              :label="ticket.status"
            />
          </ListCell>
          <ListCell>
            <span
              class="size-2 shrink-0 rounded-full"
              :class="priorityDot[ticket.priority]"
              aria-hidden="true"
            />
            <span class="ml-2 whitespace-nowrap text-base text-ink-gray-7">
              {{ ticket.priority }}
            </span>
          </ListCell>
          <ListCell>
            <Avatar
              :label="ticket.agent"
              :image="ticket.agentImage"
              size="sm"
            />
            <span class="ml-2 truncate text-base text-ink-gray-7">
              {{ ticket.agent }}
            </span>
          </ListCell>
          <ListCell class="justify-end">
            <span class="text-sm text-ink-gray-5">
              {{ ticket.modifiedLabel }}
            </span>
          </ListCell>
        </ListRow>
      </ListRows>
    </List>

    <EmptyState
      v-else
      icon="lucide-ticket"
      title="No tickets in this view"
      description="Nothing matches this filter right now."
      action="New ticket"
    />
  </div>
</template>
