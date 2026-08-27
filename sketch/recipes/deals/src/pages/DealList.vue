<script setup lang="ts">
import { computed, ref } from 'vue'
import { Avatar, Badge, ScrollArea } from 'frappe-ui'
import {
  List,
  ListCell,
  ListHeader,
  ListHeaderCell,
  ListHeaderCellSort,
  ListRow,
  ListRows,
} from 'frappe-ui/list'
import DealsHeader from '../components/DealsHeader.vue'
import { columns, logo, owners, statusBadgeTheme } from '../data'

// The list shows the same deals as the board, flattened. The board writes the
// order into the shared `columns` ref, so a drag shows up here too.
const rows = computed(() =>
  columns.value.flatMap((column) =>
    column.deals.map((deal) => ({
      ...deal,
      status: column.status,
      theme: column.theme,
    })),
  ),
)

// Sort state is app code. The header cell only draws the direction it is given.
const sortField = ref('value')
const sortDirection = ref<'asc' | 'desc'>('desc')

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

// "$ 1,10,000" is a display string. Strip everything but the digits to sort.
const amount = (value: string) => Number(value.replace(/[^0-9]/g, ''))

const sortedRows = computed(() => {
  const factor = sortDirection.value === 'desc' ? -1 : 1
  return [...rows.value].sort((a, b) => {
    if (sortField.value === 'org') return factor * a.org.localeCompare(b.org)
    return factor * (amount(a.value) - amount(b.value))
  })
})

// No `selectable` on the List: in frappe-ui 1.0.0-beta.55 a selectable row
// swallows its own click to toggle the checkbox, so the row could not open the
// deal. The row is a link to the detail route instead.
</script>

<template>
  <DealsHeader />

  <ScrollArea class="min-h-0 flex-1" viewport-class="px-3 pt-3 pb-10 sm:px-5">
    <List
      class="w-full list-row-px-3"
      :columns="['minmax(0,1fr)', '9rem', '8rem', '11rem', '7rem', '7rem']"
      :row-height="52"
    >
      <ListHeader>
        <ListHeaderCellSort
          :direction="directionFor('org')"
          @click="toggleSort('org')"
        >
          Organization
        </ListHeaderCellSort>
        <ListHeaderCell>Stage</ListHeaderCell>
        <ListHeaderCellSort
          :direction="directionFor('value')"
          @click="toggleSort('value')"
        >
          Value
        </ListHeaderCellSort>
        <ListHeaderCell>Owner</ListHeaderCell>
        <ListHeaderCell>Tag</ListHeaderCell>
        <ListHeaderCell class="justify-end">Close date</ListHeaderCell>
      </ListHeader>
      <ListRows :items="sortedRows" v-slot="{ item: deal, value }">
        <ListRow :value="value" :to="`/deals/${encodeURIComponent(deal.org)}`">
          <ListCell>
            <Avatar
              :label="deal.org"
              :image="logo(deal.org)"
              size="sm"
              shape="square"
            />
            <span class="ml-2 truncate text-base text-ink-gray-8">
              {{ deal.org }}
            </span>
          </ListCell>
          <ListCell>
            <Badge
              variant="subtle"
              :theme="statusBadgeTheme[deal.theme]"
              :label="deal.status"
            />
          </ListCell>
          <ListCell>
            <span class="text-base font-medium text-ink-gray-8">
              {{ deal.value }}
            </span>
          </ListCell>
          <ListCell>
            <Avatar
              :label="owners[deal.owner].name"
              :image="owners[deal.owner].image"
              size="sm"
            />
            <span class="ml-2 truncate text-base text-ink-gray-7">
              {{ owners[deal.owner].name }}
            </span>
          </ListCell>
          <ListCell>
            <Badge variant="outline" :label="deal.tag" />
          </ListCell>
          <ListCell class="justify-end">
            <span class="whitespace-nowrap text-sm text-ink-gray-5">
              {{ deal.due }}
            </span>
          </ListCell>
        </ListRow>
      </ListRows>
    </List>

    <div
      v-if="!sortedRows.length"
      class="flex flex-col items-center justify-center gap-3 py-16 text-center"
    >
      <div class="rounded-full bg-surface-gray-2 p-3 text-ink-gray-5">
        <span class="lucide-handshake size-6" aria-hidden="true" />
      </div>
      <p class="text-base text-ink-gray-7">No deals yet</p>
      <p class="text-sm text-ink-gray-5">Add one to start the pipeline.</p>
    </div>
  </ScrollArea>
</template>
