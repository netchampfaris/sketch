<script setup lang="ts">
import { Button, PageHeader, PageHeaderTitle } from 'frappe-ui'
import {
  List,
  ListCell,
  ListHeader,
  ListHeaderCell,
  ListRow,
  ListRows,
} from 'frappe-ui/list'
import { currency, expenses } from '../data'
</script>

<template>
  <PageHeader>
    <PageHeaderTitle>Expenses</PageHeaderTitle>
    <div class="flex items-center gap-2">
      <Button variant="solid" label="Add transaction" icon-left="lucide-plus" />
    </div>
  </PageHeader>

  <div class="p-4">
    <List
      class="w-full list-row-px-3"
      :columns="['10rem', 'minmax(0,1fr)', '9rem']"
      :row-height="40"
    >
      <ListHeader>
        <ListHeaderCell>Date</ListHeaderCell>
        <ListHeaderCell>Description</ListHeaderCell>
        <ListHeaderCell class="justify-end">Amount</ListHeaderCell>
      </ListHeader>
      <ListRows :items="expenses" v-slot="{ item }">
        <ListRow @click="() => {}">
          <ListCell>
            <span class="text-base text-ink-gray-7">{{ item.date }}</span>
          </ListCell>
          <ListCell>
            <span class="truncate text-base text-ink-gray-8">
              {{ item.description }}
            </span>
          </ListCell>
          <ListCell class="justify-end">
            <span class="text-base text-ink-gray-8">
              {{ currency(item.amount) }}
            </span>
          </ListCell>
        </ListRow>
      </ListRows>
    </List>
  </div>
</template>
