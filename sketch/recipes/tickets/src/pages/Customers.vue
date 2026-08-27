<script setup lang="ts">
import { computed } from 'vue'
import { Avatar, Badge, Button, PageHeader, PageHeaderTitle } from 'frappe-ui'
import {
  List,
  ListCell,
  ListHeader,
  ListHeaderCell,
  ListRow,
  ListRows,
} from 'frappe-ui/list'
import EmptyState from '../components/EmptyState.vue'
import { tickets } from '../data'

// The customer list is a roll-up of the same ticket fixture. No new content.
const rows = computed(() => {
  const byName = new Map<string, any>()
  for (const ticket of tickets) {
    let row = byName.get(ticket.customer)
    if (!row) {
      row = {
        name: ticket.customer,
        total: 0,
        open: 0,
        urgent: 0,
        lastModified: ticket.modified,
        lastLabel: ticket.modifiedLabel,
      }
      byName.set(ticket.customer, row)
    }
    row.total += 1
    if (['Open', 'Replied'].includes(ticket.status)) row.open += 1
    if (ticket.priority === 'Urgent') row.urgent += 1
    if (ticket.modified < row.lastModified) {
      row.lastModified = ticket.modified
      row.lastLabel = ticket.modifiedLabel
    }
  }
  return [...byName.values()].sort((a, b) => b.open - a.open || b.total - a.total)
})
</script>

<template>
  <PageHeader>
    <PageHeaderTitle title="Customers" />
    <div class="flex items-center gap-2">
      <Button label="Filter" icon-left="lucide-list-filter" />
      <Button variant="solid" label="New customer" icon-left="lucide-plus" />
    </div>
  </PageHeader>

  <div class="px-3 pt-3 pb-10 sm:px-5">
    <List
      v-if="rows.length"
      class="w-full list-row-px-3"
      :columns="['minmax(0,1fr)', '8rem', '8rem', '8rem']"
      :row-height="48"
    >
      <ListHeader>
        <ListHeaderCell>Customer</ListHeaderCell>
        <ListHeaderCell>Open</ListHeaderCell>
        <ListHeaderCell>Urgent</ListHeaderCell>
        <ListHeaderCell class="justify-end">Last activity</ListHeaderCell>
      </ListHeader>
      <ListRows :items="rows" v-slot="{ item: row, value }">
        <ListRow :value="value" @click="() => {}">
          <ListCell>
            <Avatar :label="row.name" size="sm" shape="square" />
            <span class="ml-2 truncate text-base text-ink-gray-8">
              {{ row.name }}
            </span>
          </ListCell>
          <ListCell>
            <span class="text-base text-ink-gray-7">
              {{ row.open }} of {{ row.total }}
            </span>
          </ListCell>
          <ListCell>
            <Badge
              v-if="row.urgent"
              theme="red"
              variant="subtle"
              :label="String(row.urgent)"
            />
            <span v-else class="text-base text-ink-gray-4">0</span>
          </ListCell>
          <ListCell class="justify-end">
            <span class="text-sm text-ink-gray-5">{{ row.lastLabel }}</span>
          </ListCell>
        </ListRow>
      </ListRows>
    </List>

    <EmptyState
      v-else
      icon="lucide-building-2"
      title="No customers yet"
      description="A customer appears here after the first ticket."
    />
  </div>
</template>
