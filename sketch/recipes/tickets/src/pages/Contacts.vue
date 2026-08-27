<script setup lang="ts">
import { Button, PageHeader, PageHeaderTitle } from 'frappe-ui'
import EmptyState from '../components/EmptyState.vue'

// The upstream recipe ships no fixture for this screen. The route is real and
// the page shows its empty state.
</script>

<template>
  <PageHeader>
    <PageHeaderTitle title="Contacts" />
    <Button variant="solid" label="New contact" icon-left="lucide-plus" />
  </PageHeader>

  <div class="px-3 pt-3 pb-10 sm:px-5">
    <EmptyState
      icon="lucide-contact"
      title="No contacts yet"
      description="Add the people you talk to at each customer."
      action="New contact"
    />
  </div>
</template>
