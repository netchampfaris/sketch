<script setup lang="ts">
import { computed } from 'vue'
import { Badge } from 'frappe-ui'
import type { Status } from '../data'

const props = defineProps<{ status: Status }>()

const theme = computed(() =>
  ({ open: 'orange', 'in-progress': 'blue', done: 'green' })[props.status],
)
const label = computed(() =>
  ({ open: 'Open', 'in-progress': 'In progress', done: 'Done' })[props.status],
)
</script>

<template>
  <Badge :theme="theme" variant="subtle">{{ label }}</Badge>
</template>
