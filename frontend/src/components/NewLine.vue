<script setup lang="ts">
/**
 * What is new on a prototype since this person last looked: one muted line under the title, and who made it.
 *
 * "2 new variants · 3 new comments", leaving out any part that is 0, and no line at all when nothing is new. When
 * someone mentioned this person the line leads with "Arohi mentioned you" in normal ink, and opens the prototype on
 * that thread. Counts over 99 read "99+". Opening the prototype does not clear them: what has been looked at does,
 * on the server (`sketch/badges.py`).
 *
 * `h-6` and no button, so it is the one row on the card that is not a button's height.
 */
import { computed } from 'vue'
import { Avatar } from 'frappe-ui'
import type { PrototypeNew } from '../types'

const props = defineProps<{ news?: PrototypeNew | null; href: string }>()

const MAX = 99
const count = (n: number, word: string) => `${n > MAX ? `${MAX}+` : n} new ${word}${n === 1 ? '' : 's'}`

const counts = computed(() => {
  const n = props.news
  if (!n) return ''
  return [n.variants && count(n.variants, 'variant'), n.comments && count(n.comments, 'comment')].filter(Boolean).join(' · ')
})
const mention = computed(() => {
  const m = props.news?.mention
  return m ? `${m.by.name.split(/\s+/)[0] || m.by.username} mentioned you` : ''
})
const label = computed(() => [mention.value, counts.value].filter(Boolean).join(' · '))
const link = computed(() =>
  props.news?.mention ? `${props.href}?comment=${encodeURIComponent(props.news.mention.thread)}` : props.href,
)
</script>

<template>
  <a
    v-if="news && label"
    :href="link"
    target="_blank"
    rel="noopener"
    class="flex h-6 min-w-0 items-center gap-2 text-xs text-ink-gray-5 hover:text-ink-gray-7"
    :title="label"
  >
    <!-- The mention gives way first when the card is narrow; the counts and the faces after it keep their room. -->
    <span class="flex min-w-0 items-baseline gap-1">
      <span v-if="mention" class="min-w-0 truncate text-ink-gray-8">{{ mention }}</span>
      <span v-if="mention && counts" class="shrink-0" aria-hidden="true">&middot;</span>
      <span v-if="counts" class="whitespace-nowrap" :class="mention ? 'shrink-0' : 'truncate'">{{ counts }}</span>
    </span>
    <span v-if="news.by.length" class="flex shrink-0 items-center" :title="news.by.map((p) => p.name).join(', ')">
      <Avatar
        v-for="(p, i) in news.by"
        :key="p.username"
        :class="i ? '-ml-1' : ''"
        class="ring-2 ring-outline-base"
        size="xs"
        :image="p.image || undefined"
        :label="p.name"
      />
      <span v-if="news.more" class="ml-1.5 tabular-nums">+{{ news.more }}</span>
    </span>
  </a>
</template>
