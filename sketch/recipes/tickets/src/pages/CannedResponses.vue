<script setup lang="ts">
import { Button, PageHeader, PageHeaderTitle } from 'frappe-ui'
import EmptyState from '../components/EmptyState.vue'

// The upstream recipe ships no fixture for this screen. The route is real and
// the page shows its empty state.
</script>

<template>
  <PageHeader>
    <PageHeaderTitle title="Canned responses" />
    <Button variant="solid" label="New response" icon-left="lucide-plus" />
  </PageHeader>

  <div class="px-3 pt-3 pb-10 sm:px-5">
    <EmptyState
      icon="lucide-message-square-text"
      title="No canned responses yet"
      description="Save a reply you send often and reuse it."
      action="New response"
    />
  </div>
</template>
