<script setup lang="ts">
/**
 * A gallery card's second row: what is new on the prototype since this person last looked, or, when nothing is, the
 * meta in the `#default` slot ("16 files · Updated 1 day ago"). One `h-7` line either way, so the card never changes
 * height and cards in a grid row line up.
 *
 * News reads "• 1 new comment · 2 hours ago": the unread dot, the news in normal ink, then when the newest of it
 * happened in gray. "2 new variants · 3 new comments" leaves out any part that is 0. When someone mentioned this person
 * the line leads with "Arohi mentioned you", and opens the prototype on that thread. An invited editor's line leads
 * with "Sadiq made your Compact the default", or "Sadiq invited you" until they open it. One lead, the newest and most
 * personal first: a mention, then the default, then the invitation. Counts over 99 read "99+". No faces: the line is
 * what happened, and the card's avatar stack already says who it is shared with. Opening the prototype does not clear
 * it: what has been looked at does, on the server (`sketch/badges.py`).
 */
import { computed } from 'vue'
import type { NewPerson, PrototypeNew } from '../types'
const props = defineProps<{ news?: PrototypeNew | null; href: string }>()

const MAX = 99
const count = (n: number, word: string) => `${n > MAX ? `${MAX}+` : n} new ${word}${n === 1 ? '' : 's'}`

const counts = computed(() => {
  const n = props.news
  if (!n) return ''
  return [n.variants && count(n.variants, 'variant'), n.comments && count(n.comments, 'comment')].filter(Boolean).join(' · ')
})
const first = (p: NewPerson) => p.name.split(/\s+/)[0] || p.username
/** The line's lead: the most personal news, in normal ink. */
const mention = computed(() => {
  const n = props.news
  if (!n) return ''
  if (n.mention) return `${first(n.mention.by)} mentioned you`
  if (n.adopted) return `${first(n.adopted.by)} made your ${n.adopted.label} the default`
  if (n.invited) return `${first(n.invited.by)} invited you`
  return ''
})
const label = computed(() => [mention.value, counts.value].filter(Boolean).join(' · '))
const title = computed(() => [label.value, props.news?.ago].filter(Boolean).join(' · '))
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
    class="group flex h-7 min-w-0 items-center gap-1.5 text-xs text-ink-gray-5"
    :title="title"
  >
    <span class="size-1.5 shrink-0 rounded-full bg-surface-blue-6" aria-hidden="true" />
    <span class="min-w-0 truncate">
      <span class="text-ink-gray-8 group-hover:underline">{{ label }}</span>
      <template v-if="news.ago"> &middot; {{ news.ago }}</template>
    </span>
  </a>
  <div v-else class="flex h-7 min-w-0 items-center gap-2 text-xs text-ink-gray-5">
    <slot />
  </div>
</template>
