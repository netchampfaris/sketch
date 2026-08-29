<script setup lang="ts">
/**
 * The one page a Blank Prototype starts with.
 *
 * `__SKETCH_TITLE__` in the heading is replaced with the name the user typed,
 * by `create_prototype` in sketch/api.py. The heading used to be the literal
 * "Untitled", so a Prototype named "First look" opened on somebody else's word
 * (review 6.2). The token is left readable, because
 * sketch/tests/test_recipes_boot.py boots this tree unsubstituted.
 *
 * There is no action button here. Sketch has no editor, so a button on this
 * page has nothing to do, and the "Add a page" one that used to sit here had
 * no handler at all (review 6.1). The agent is the only thing that can fill
 * the page, so the copy points at the agent.
 */
import { PageHeader } from 'frappe-ui'
</script>

<template>
  <PageHeader>
    <h1 class="text-2xl-semibold text-ink-gray-8">__SKETCH_TITLE__</h1>
  </PageHeader>

  <div class="px-3 pt-5 pb-10 sm:px-5">
    <div class="flex flex-col items-center justify-center gap-3 py-16 text-center">
      <span class="grid size-12 place-items-center rounded-full bg-surface-gray-2 text-ink-gray-5">
        <span class="lucide-pencil-ruler size-6" aria-hidden="true" />
      </span>
      <p class="text-base-medium text-ink-gray-8">This page is empty</p>
      <p class="max-w-sm text-p-sm text-ink-gray-5">
        Sketch has no editor. Tell your agent what this page should hold, and it
        writes the files for you.
      </p>
    </div>
  </div>
</template>
