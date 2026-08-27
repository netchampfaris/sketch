<script setup lang="ts">
import { computed, ref } from 'vue'
import { Avatar, Badge, PageHeader, PageHeaderTitle, TextInput } from 'frappe-ui'
import { List, ListCell, ListRow } from 'frappe-ui/list'
import { discussions } from '../data'

const query = ref('onboarding')

const results = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return []
  return discussions.filter(
    (d) =>
      d.title.toLowerCase().includes(q) ||
      d.author.toLowerCase().includes(q) ||
      d.excerpt.toLowerCase().includes(q),
  )
})
</script>

<template>
  <PageHeader>
    <PageHeaderTitle>Search</PageHeaderTitle>
  </PageHeader>

  <div class="mx-auto mt-5 w-full max-w-[940px] px-3 pb-10 sm:px-5">
    <TextInput
      v-model="query"
      class="w-full"
      size="lg"
      label="Search discussions"
      placeholder="Title, author, or text"
    >
      <template #prefix>
        <span class="lucide-search size-4 text-ink-gray-5" aria-hidden="true" />
      </template>
    </TextInput>

    <p class="mt-4 text-sm text-ink-gray-5">
      {{ results.length }} results
    </p>

    <List v-if="results.length" class="-mx-3 mt-2 sm:list-gap-4">
      <ListRow
        v-for="d in results"
        :key="d.id"
        class="h-15"
        :to="`/thread?d=${d.id}`"
      >
        <ListCell>
          <Avatar :image="d.image" :label="d.author" size="2xl" />
        </ListCell>
        <ListCell>
          <div class="min-w-0 flex-1">
            <div class="truncate leading-none text-ink-gray-8">
              <span class="text-base">{{ d.title }}</span>
            </div>
            <div class="mt-1.5 truncate text-base text-ink-gray-5">
              {{ d.space }} · {{ d.excerpt }}
            </div>
          </div>
        </ListCell>
        <ListCell class="justify-end">
          <Badge>{{ d.comments + 1 }}</Badge>
        </ListCell>
      </ListRow>
    </List>

    <div v-else class="flex flex-col items-center justify-center gap-3 py-16 text-center">
      <div class="rounded-full bg-surface-gray-2 p-3 text-ink-gray-5">
        <span class="lucide-search size-6" aria-hidden="true" />
      </div>
      <p class="text-base text-ink-gray-7">No matches</p>
      <p class="text-sm text-ink-gray-5">Try another word.</p>
    </div>
  </div>
</template>
