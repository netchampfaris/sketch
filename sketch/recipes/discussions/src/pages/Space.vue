<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Button, Dropdown, PageHeader, PageHeaderTitle } from 'frappe-ui'
import DiscussionList from '../components/DiscussionList.vue'
import { discussionsInSpace, spaceActions } from '../data'

// Every space has its own path. The name rides on the route meta, so no route
// takes a parameter.
const route = useRoute()
const spaceName = computed(() => String(route.meta.space ?? ''))
const items = computed(() => discussionsInSpace(spaceName.value))
</script>

<template>
  <PageHeader>
    <div class="flex items-center gap-1">
      <PageHeaderTitle>{{ spaceName }}</PageHeaderTitle>
      <Dropdown :options="spaceActions">
        <Button variant="ghost" icon="lucide-ellipsis" label="Space actions" />
      </Dropdown>
    </div>
    <Button label="Add new" icon-left="lucide-plus" />
  </PageHeader>

  <div class="mx-auto mt-5 w-full max-w-[940px] px-3 pb-10 sm:px-5">
    <DiscussionList :items="items" />
  </div>
</template>
