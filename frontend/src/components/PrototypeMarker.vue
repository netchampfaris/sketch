<script setup lang="ts">
/**
 * What is new on a prototype since this person last looked: a small blue pill on the corner of its preview
 * (decision 70). An icon and a count, or "New" for an invitation they have not opened. Nothing new, no pill.
 *
 * The icon is the most personal news: @ when someone mentioned them, a speech bubble for new comments, layers for new
 * variants. The count is new comments plus new variants, "99+" past 99. The tooltip spells it out, "Arohi mentioned
 * you · 2 new variants · 3 new comments · 2 hours ago". An invited editor's line leads with "Sadiq made your Compact the
 * default", or "Sadiq invited you" until they open it: one lead, a mention first, then the default, then the invitation.
 * A mention opens the prototype on that thread. Opening the prototype does not clear it: what has been looked at does,
 * on the server (`sketch/badges.py`).
 *
 * It sits over the preview's own link, so it is a link too: the same prototype, a new tab.
 */
import { computed } from 'vue'
import { Tooltip } from 'frappe-ui'
import type { NewPerson, PrototypeNew } from '../types'

const props = defineProps<{ news?: PrototypeNew | null; href: string }>()

const MAX = 99
const capped = (n: number) => (n > MAX ? `${MAX}+` : String(n))
const count = (n: number, word: string) => `${capped(n)} new ${word}${n === 1 ? '' : 's'}`
const first = (p: NewPerson) => p.name.split(/\s+/)[0] || p.username

const total = computed(() => (props.news?.comments ?? 0) + (props.news?.variants ?? 0))

/** Mention, then comments, then variants. Null leaves the pill as the word "New". */
const icon = computed(() => {
  const n = props.news
  if (!n) return null
  if (n.mention) return 'lucide-at-sign'
  if (n.comments) return 'lucide-message-circle'
  if (n.variants) return 'lucide-layers'
  return null
})

const lead = computed(() => {
  const n = props.news
  if (!n) return ''
  if (n.mention) return `${first(n.mention.by)} mentioned you`
  if (n.adopted) return `${first(n.adopted.by)} made your ${n.adopted.label} the default`
  if (n.invited) return `${first(n.invited.by)} invited you`
  return ''
})

const text = computed(() => {
  const n = props.news
  if (!n) return ''
  const counts = [n.variants && count(n.variants, 'variant'), n.comments && count(n.comments, 'comment')]
  return [lead.value, ...counts, n.ago].filter(Boolean).join(' · ')
})

const link = computed(() =>
  props.news?.mention ? `${props.href}?comment=${encodeURIComponent(props.news.mention.thread)}` : props.href,
)
</script>

<template>
  <div v-if="news && text" class="absolute right-2 top-2 z-10">
    <Tooltip :text="text">
      <a
        :href="link"
        target="_blank"
        rel="noopener"
        :aria-label="text"
        class="flex h-5 items-center gap-1 rounded-full bg-surface-blue-6 px-1.5 text-xs-medium tabular-nums text-ink-white"
      >
        <template v-if="icon && total">
          <span :class="icon" class="size-3" aria-hidden="true" />
          {{ capped(total) }}
        </template>
        <template v-else>New</template>
      </a>
    </Tooltip>
  </div>
</template>
