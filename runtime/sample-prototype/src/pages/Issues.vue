<script setup lang="ts">
import { ref } from 'vue'
import { Button, PageHeader } from 'frappe-ui'
import { List, ListHeader, ListHeaderCell, ListRow, ListRows, ListCell } from 'frappe-ui/list'
import { issues } from '../data'
import StatusBadge from '../components/StatusBadge.vue'
import NewIssueDialog from '../components/NewIssueDialog.vue'

const showNew = ref(false)
const columns = ['6rem', 'minmax(0,1fr)', '8rem', '7rem']
</script>

<template>
  <PageHeader>
    <div class="flex w-full items-center justify-between">
      <h1 class="text-lg font-semibold text-ink-gray-9">Issues</h1>
      <Button variant="solid" theme="gray" @click="showNew = true">
        <template #prefix><span class="lucide-plus size-4" aria-hidden="true" /></template>
        New issue
      </Button>
    </div>
  </PageHeader>

  <div class="p-5">
    <List :columns="columns" class="list-gap-4">
      <ListHeader>
        <ListHeaderCell>ID</ListHeaderCell>
        <ListHeaderCell>Title</ListHeaderCell>
        <ListHeaderCell>Status</ListHeaderCell>
        <ListHeaderCell>Assignee</ListHeaderCell>
      </ListHeader>
      <ListRows :items="issues" v-slot="{ item, value }">
        <ListRow :value="value">
          <ListCell class="text-sm text-ink-gray-5">{{ item.name }}</ListCell>
          <ListCell class="truncate text-sm text-ink-gray-8">{{ item.title }}</ListCell>
          <ListCell><StatusBadge :status="item.status" /></ListCell>
          <ListCell class="text-sm text-ink-gray-6">{{ item.owner }}</ListCell>
        </ListRow>
      </ListRows>
    </List>

    <p v-if="!issues.length" class="py-10 text-center text-sm text-ink-gray-5">
      No issues yet.
    </p>
  </div>

  <NewIssueDialog v-model:open="showNew" />
</template>
