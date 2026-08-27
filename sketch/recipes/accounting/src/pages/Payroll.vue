<script setup lang="ts">
import { ref } from 'vue'
import { Button, PageHeader, PageHeaderTitle } from 'frappe-ui'
import {
  List,
  ListCell,
  ListHeader,
  ListHeaderCell,
  ListRow,
  ListRows,
} from 'frappe-ui/list'
import { currency, payroll } from '../data'

// The list's own selection model: `selectable` reveals the checkbox column and
// `v-model:selection` holds the chosen row values, which are strings. A header
// button toggles the mode on and off.
const selectMode = ref(true)
const selection = ref(['2'])
function toggleSelectMode() {
  selectMode.value = !selectMode.value
  if (!selectMode.value) selection.value = []
}
</script>

<template>
  <PageHeader>
    <PageHeaderTitle>Payroll</PageHeaderTitle>
    <div class="flex items-center gap-2">
      <span
        v-if="selectMode && selection.length"
        class="text-sm text-ink-gray-6"
      >
        {{ selection.length }} selected
      </span>
      <Button
        :label="selectMode ? 'Done' : 'Select'"
        :icon-left="selectMode ? 'lucide-check' : 'lucide-list-checks'"
        @click="toggleSelectMode"
      />
      <Button variant="solid" label="Add employee" icon-left="lucide-plus" />
    </div>
  </PageHeader>

  <div class="p-4">
    <List
      class="w-full list-row-px-3"
      :columns="['minmax(0,1fr)', '9rem', '7rem', '7rem', '10rem']"
      :row-height="40"
      :selectable="selectMode"
      v-model:selection="selection"
    >
      <ListHeader>
        <ListHeaderCell>Name</ListHeaderCell>
        <ListHeaderCell>
          Total pay <span class="text-ink-gray-5">(per annum)</span>
        </ListHeaderCell>
        <ListHeaderCell>
          Tax <span class="text-ink-gray-5">20%</span>
        </ListHeaderCell>
        <ListHeaderCell>NI</ListHeaderCell>
        <ListHeaderCell>
          Net pay <span class="text-ink-gray-5">(per annum)</span>
        </ListHeaderCell>
      </ListHeader>
      <ListRows :items="payroll" v-slot="{ item, value }">
        <ListRow :value="value" @click="() => {}">
          <ListCell>
            <span class="truncate text-base text-ink-gray-8">
              {{ item.name }}
            </span>
          </ListCell>
          <ListCell>
            <span class="text-base text-ink-gray-7">
              {{ currency(item.total) }}
            </span>
          </ListCell>
          <ListCell>
            <span class="text-base text-ink-gray-7">
              {{ currency(item.tax) }}
            </span>
          </ListCell>
          <ListCell>
            <span class="text-base text-ink-gray-7">
              {{ currency(item.ni) }}
            </span>
          </ListCell>
          <ListCell>
            <span class="text-base text-ink-gray-8">
              {{ currency(item.net) }}
            </span>
          </ListCell>
        </ListRow>
      </ListRows>
    </List>
  </div>
</template>
