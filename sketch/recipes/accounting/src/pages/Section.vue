<script setup lang="ts">
import { computed } from 'vue'
import { PageHeader, PageHeaderTitle } from 'frappe-ui'
import EmptySection from '../components/EmptySection.vue'
import { metaFor } from '../data'

// One stub page serves every shell-only nav item. The route passes the key as
// a static prop, so the path stays parameterless.
const props = defineProps<{ itemKey: string }>()
const meta = computed(() => metaFor(props.itemKey))
</script>

<template>
  <PageHeader>
    <PageHeaderTitle>{{ meta.label }}</PageHeaderTitle>
  </PageHeader>

  <EmptySection :label="meta.label" :icon="meta.icon" />
</template>
