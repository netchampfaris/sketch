<script setup lang="ts">
import { computed, ref } from 'vue'
import { Avatar, Badge, TabButtons, Tooltip } from 'frappe-ui'
import { List, ListCell, ListRow } from 'frappe-ui/list'
import type { Discussion } from '../data'

const props = defineProps<{ items: Discussion[] }>()

const feedTab = ref('All')
const visibleDiscussions = computed(() =>
  feedTab.value === 'Unread' ? props.items.filter((d) => d.unread) : props.items,
)
</script>

<template>
  <div class="mb-4 flex items-center justify-between">
    <TabButtons
      v-model="feedTab"
      :options="[{ label: 'Unread' }, { label: 'All' }]"
    />
    <span class="text-sm text-ink-gray-5">
      {{ visibleDiscussions.length }} discussions
    </span>
  </div>

  <!-- -mx-3 lets the row hover surface bleed past the text edge, so the content
       stays aligned with the container. -->
  <List v-if="visibleDiscussions.length" class="-mx-3 sm:list-gap-4">
    <ListRow
      v-for="discussion in visibleDiscussions"
      :key="discussion.id"
      class="h-15"
      :to="`/thread?d=${discussion.id}`"
    >
      <ListCell>
        <Avatar :image="discussion.image" :label="discussion.author" size="2xl" />
      </ListCell>
      <ListCell>
        <div class="min-w-0 flex-1">
          <!-- The sized text lives in an inner span so it keeps its own line
               height. `leading-none` on the same element as `truncate`
               (overflow-hidden) would shear off the tail of a "g". -->
          <div class="truncate leading-none text-ink-gray-8">
            <span :class="discussion.unread ? 'text-base-semibold' : 'text-base'">
              {{ discussion.title }}
            </span>
          </div>
          <div class="mt-1.5 flex min-w-0 items-center text-base text-ink-gray-5">
            <span class="lucide-reply mr-1 size-4 shrink-0" aria-hidden="true" />
            <span class="shrink-0">{{ discussion.author }}:&nbsp;</span>
            <span class="truncate">{{ discussion.excerpt }}</span>
          </div>
        </div>
      </ListCell>
      <ListCell class="justify-end">
        <div>
          <div class="whitespace-nowrap text-right text-sm text-ink-gray-5">
            {{ discussion.lastActivity }}
          </div>
          <div class="mt-1.5 flex items-center justify-end">
            <Tooltip
              v-if="discussion.unread"
              :text="`${discussion.unread} unread`"
            >
              <Badge theme="amber" variant="solid" size="sm">
                {{ discussion.unread }}
              </Badge>
            </Tooltip>
            <Badge v-else>{{ discussion.comments + 1 }}</Badge>
          </div>
        </div>
      </ListCell>
    </ListRow>
  </List>

  <div v-else class="flex flex-col items-center justify-center gap-3 py-16 text-center">
    <div class="rounded-full bg-surface-gray-2 p-3 text-ink-gray-5">
      <span class="lucide-inbox size-6" aria-hidden="true" />
    </div>
    <p class="text-base text-ink-gray-7">Nothing unread</p>
    <p class="text-sm text-ink-gray-5">You have read every discussion here.</p>
  </div>
</template>
