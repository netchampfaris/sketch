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
import { currentAgent, tickets } from '../data'

// The agent list is a roll-up of the same ticket fixture. No new content.
const rows = computed(() => {
  const byName = new Map<string, any>()
  for (const ticket of tickets) {
    let row = byName.get(ticket.agent)
    if (!row) {
      row = {
        name: ticket.agent,
        image: ticket.agentImage,
        total: 0,
        open: 0,
        breached: 0,
      }
      byName.set(ticket.agent, row)
    }
    row.total += 1
    if (['Open', 'Replied'].includes(ticket.status)) row.open += 1
    if (
      ticket.firstResponse.state === 'breached' ||
      ticket.resolution.state === 'breached'
    ) {
      row.breached += 1
    }
  }
  return [...byName.values()].sort((a, b) => b.open - a.open)
})
</script>

<template>
  <PageHeader>
    <PageHeaderTitle title="Agents" />
    <div class="flex items-center gap-2">
      <Button label="Filter" icon-left="lucide-list-filter" />
      <Button variant="solid" label="Invite agent" icon-left="lucide-plus" />
    </div>
  </PageHeader>

  <div class="px-3 pt-3 pb-10 sm:px-5">
    <List
      v-if="rows.length"
      class="w-full list-row-px-3"
      :columns="['minmax(0,1fr)', '8rem', '8rem', '9rem']"
      :row-height="48"
    >
      <ListHeader>
        <ListHeaderCell>Agent</ListHeaderCell>
        <ListHeaderCell>Open</ListHeaderCell>
        <ListHeaderCell>Assigned</ListHeaderCell>
        <ListHeaderCell class="justify-end">SLA breached</ListHeaderCell>
      </ListHeader>
      <ListRows :items="rows" v-slot="{ item: row, value }">
        <ListRow :value="value" @click="() => {}">
          <ListCell>
            <Avatar :label="row.name" :image="row.image" size="sm" />
            <span class="ml-2 truncate text-base text-ink-gray-8">
              {{ row.name }}
            </span>
            <Badge
              v-if="row.name === currentAgent"
              variant="subtle"
              label="You"
              class="ml-2"
            />
          </ListCell>
          <ListCell>
            <span class="text-base text-ink-gray-7">{{ row.open }}</span>
          </ListCell>
          <ListCell>
            <span class="text-base text-ink-gray-7">{{ row.total }}</span>
          </ListCell>
          <ListCell class="justify-end">
            <span
              class="text-sm"
              :class="row.breached ? 'text-ink-red-5' : 'text-ink-gray-5'"
            >
              {{ row.breached }}
            </span>
          </ListCell>
        </ListRow>
      </ListRows>
    </List>

    <EmptyState
      v-else
      icon="lucide-headset"
      title="No agents yet"
      description="Invite a teammate to take tickets."
    />
  </div>
</template>
