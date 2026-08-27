<script setup lang="ts">
import { Button, PageHeader } from 'frappe-ui'
</script>

<template>
  <PageHeader>
    <h1 class="text-2xl text-ink-gray-9">Untitled</h1>
  </PageHeader>

  <div class="px-3 pt-5 pb-10 sm:px-5">
    <div class="flex flex-col items-center justify-center gap-3 py-16 text-center">
      <div class="rounded-full bg-surface-gray-2 p-3 text-ink-gray-5">
        <span class="lucide-pencil-ruler size-6" aria-hidden="true" />
      </div>
      <p class="text-base text-ink-gray-7">An empty prototype</p>
      <p class="text-sm text-ink-gray-5">
        Edit <code class="text-ink-gray-7">src/pages/Home.vue</code> to start.
      </p>
      <Button
        variant="solid"
        theme="gray"
        icon-left="lucide-plus"
        label="Add a page"
        class="mt-2"
      />
    </div>
  </div>
</template>
