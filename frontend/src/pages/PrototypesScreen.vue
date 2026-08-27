<script setup lang="ts">
/**
 * Your studio: the Prototype gallery (spec 11).
 *
 * The header holds the count and the one solid action. The body is a
 * responsive grid of cards, each with a live preview of the Prototype.
 */
import { computed, onMounted, ref } from 'vue'
import { Button, LoadingText, PageHeader } from 'frappe-ui'
import NewPrototypeDialog from '../components/NewPrototypeDialog.vue'
import PrototypeCard from '../components/PrototypeCard.vue'
import { prototypes } from '../store'

const showPicker = ref(false)

const items = computed(() => prototypes.data ?? [])
const count = computed(() => items.value.length)
const firstLoad = computed(() => prototypes.loading && !prototypes.isFinished)

onMounted(() => {
  if (!prototypes.isFinished) prototypes.reload()
})
</script>

<template>
  <PageHeader>
    <div class="min-w-0">
      <h1 class="truncate text-lg font-semibold text-ink-gray-8">Your studio</h1>
      <p class="text-xs text-ink-gray-5">
        {{ count }} {{ count === 1 ? 'prototype' : 'prototypes' }}
      </p>
    </div>
    <Button
      icon-left="lucide-plus"
      label="New prototype"
      theme="gray"
      variant="solid"
      @click="showPicker = true"
    />
  </PageHeader>

  <div class="px-3 pb-10 pt-6 sm:px-5">
    <div v-if="firstLoad" class="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
      <div v-for="n in 3" :key="n">
        <div class="aspect-[16/10] w-full rounded-6 bg-surface-gray-2" />
        <div class="mt-3 h-10"><LoadingText :lines="2" /></div>
      </div>
    </div>

    <div
      v-else-if="!count"
      class="flex flex-col items-center justify-center gap-3 py-16 text-center"
    >
      <div class="rounded-full bg-surface-gray-2 p-3 text-ink-gray-5">
        <span class="lucide-panels-top-left size-6" aria-hidden="true" />
      </div>
      <p class="text-base text-ink-gray-7">No prototypes yet</p>
      <p class="text-sm text-ink-gray-5">Pick a recipe and your agent takes it from there.</p>
      <Button
        class="mt-2"
        icon-left="lucide-plus"
        label="New prototype"
        theme="gray"
        variant="solid"
        @click="showPicker = true"
      />
    </div>

    <div v-else class="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
      <PrototypeCard
        v-for="item in items"
        :key="item.name"
        :prototype="item"
        @changed="prototypes.reload()"
        @removed="prototypes.reload()"
      />
    </div>
  </div>

  <NewPrototypeDialog v-model:open="showPicker" @created="prototypes.reload()" />
</template>
