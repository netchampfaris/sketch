<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Button, PageHeader, PageHeaderTitle, TabButtons } from 'frappe-ui'

// The upstream `view` ref becomes the route. Each tab is a RouterLink, and the
// current path selects it. frappe-ui 1.0.0-beta.55 needs an explicit `value`
// on every option, so the value is the path itself.
const route = useRoute()
const view = computed(() => (route.path === '/list' ? '/list' : '/'))

const options = [
  { label: 'Board', value: '/', route: { path: '/' } },
  { label: 'List', value: '/list', route: { path: '/list' } },
]
</script>

<template>
  <PageHeader>
    <PageHeaderTitle title="Deals" />
    <div class="flex items-center gap-2">
      <TabButtons :model-value="view" :options="options" />
      <Button label="Filter" icon-left="lucide-list-filter" />
      <Button label="Sort" icon-left="lucide-arrow-down-up" />
      <Button variant="solid" label="New deal" icon-left="lucide-plus" />
    </div>
  </PageHeader>
</template>
