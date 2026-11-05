<script setup lang="ts">
/**
 * One agent app's mark, sized by the caller and coloured by `currentColor`.
 *
 * `v-html` is safe here: `svg` is one of the bundled files in
 * `assets/agents/`, never user input. A lucide class stands in for the rows
 * that have no single brand (Other, claude.ai).
 */
defineProps<{ svg?: string; icon?: string }>()
</script>

<template>
  <span v-if="svg" aria-hidden="true" class="inline-flex shrink-0 [&>svg]:size-full" v-html="svg" />
  <span v-else aria-hidden="true" class="shrink-0" :class="icon" />
</template>
