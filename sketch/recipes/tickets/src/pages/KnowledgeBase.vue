<script setup lang="ts">
import { Button, PageHeader, PageHeaderTitle } from 'frappe-ui'
import EmptyState from '../components/EmptyState.vue'

// The upstream recipe ships no fixture for this screen. The route is real and
// the page shows its empty state.
</script>

<template>
  <PageHeader>
    <PageHeaderTitle title="Knowledge base" />
    <Button variant="solid" label="New article" icon-left="lucide-plus" />
  </PageHeader>

  <div class="px-3 pt-3 pb-10 sm:px-5">
    <EmptyState
      icon="lucide-book-open"
      title="No articles yet"
      description="Write an article once, then link it from a reply."
      action="New article"
    />
  </div>
</template>
