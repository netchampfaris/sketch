<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Avatar, Button, ScrollArea } from 'frappe-ui'
import ReplyComposer from './ReplyComposer.vue'
import type { MailThread } from '../data'

// The reading pane. It shows one conversation, or an empty state when the
// mailbox holds nothing.
const props = defineProps<{ thread: MailThread | null }>()

const replying = ref(false)

// A new thread closes the composer, so a draft never follows the reader.
watch(
  () => props.thread,
  () => (replying.value = false),
)

const replyTo = computed(() => {
  const messages = props.thread?.messages ?? []
  return messages[messages.length - 1]?.author.name ?? 'the sender'
})
</script>

<template>
  <section class="flex h-full min-h-0 min-w-0 flex-1 flex-col">
    <ScrollArea v-if="thread" class="min-h-0 flex-1">
      <div class="space-y-6 px-6 py-5">
        <article
          v-for="(message, i) in thread.messages"
          :key="i"
          class="border-t border-outline-gray-1 pt-6 first:border-0 first:pt-0"
        >
          <div class="flex items-start justify-between gap-4">
            <div class="flex items-center gap-3">
              <Avatar
                size="xl"
                :label="message.author.name"
                :image="message.author.image"
              />
              <div class="min-w-0">
                <div class="text-base font-semibold text-ink-gray-9">
                  {{ message.author.name }}
                </div>
                <div class="mt-0.5 truncate text-sm text-ink-gray-5">
                  From {{ message.author.email }}
                </div>
              </div>
            </div>
            <span class="shrink-0 text-sm text-ink-gray-5">
              {{ message.date }}
            </span>
          </div>

          <div class="mt-4 space-y-4">
            <p
              v-for="(paragraph, p) in message.body"
              :key="p"
              class="whitespace-pre-line text-p-base text-ink-gray-8"
            >
              {{ paragraph }}
            </p>
          </div>
        </article>
      </div>
    </ScrollArea>

    <div
      v-else
      class="flex min-h-0 flex-1 flex-col items-center justify-center gap-3 px-6 text-center"
    >
      <div class="rounded-full bg-surface-gray-2 p-3 text-ink-gray-5">
        <span class="lucide-mail-open size-6" aria-hidden="true" />
      </div>
      <p class="text-base text-ink-gray-7">No conversation open</p>
      <p class="text-p-sm text-ink-gray-5">
        Pick a message on the left to read it.
      </p>
    </div>

    <!-- The reply bar, pinned below the scroll region. It becomes the composer
         once a reply starts. -->
    <ReplyComposer
      v-if="thread && replying"
      :to="replyTo"
      @close="replying = false"
    />
    <footer
      v-else-if="thread"
      class="flex shrink-0 items-center gap-2 border-t border-outline-gray-1 px-5 py-3"
    >
      <Button
        variant="solid"
        theme="gray"
        label="Reply"
        icon-left="lucide-reply"
        @click="replying = true"
      />
      <Button
        variant="ghost"
        label="Reply all"
        icon-left="lucide-reply-all"
        @click="replying = true"
      />
      <Button variant="ghost" label="Forward" icon-left="lucide-forward" />
    </footer>
  </section>
</template>
