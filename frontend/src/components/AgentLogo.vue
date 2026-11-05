<script setup lang="ts">
/**
 * One agent app's mark, sized by the caller and coloured by `currentColor`.
 *
 * `v-html` is safe here: `svg` is one of the bundled files in
 * `assets/agents/`, never user input.
 */
defineProps<{ svg: string }>()
</script>

<template>
  <span aria-hidden="true" class="inline-flex shrink-0 [&>svg]:size-full" v-html="svg" />
</template>
