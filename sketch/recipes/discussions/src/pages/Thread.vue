<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import {
  Avatar,
  Badge,
  Breadcrumbs,
  Button,
  Dropdown,
  PageHeader,
  Textarea,
  toast,
} from 'frappe-ui'
import ThreadPost from '../components/ThreadPost.vue'
import {
  findDiscussion,
  fullName,
  spaceActions,
  threadBody,
  threadReplies,
  userImage,
} from '../data'
import type { Reply } from '../data'

// The reader takes no route parameter. The query picks the row, and the first
// discussion is the default.
const route = useRoute()
const discussion = computed(() => findDiscussion(Number(route.query.d ?? 0)))

const replies = ref<Reply[]>([...threadReplies])
const draft = ref('')

function postReply() {
  if (!draft.value.trim()) return
  replies.value.push({
    author: fullName.value,
    image: userImage,
    time: 'now',
    text: draft.value.trim(),
  })
  draft.value = ''
  toast.success('Reply posted')
}
</script>

<template>
  <PageHeader>
    <Breadcrumbs
      :items="[
        { label: discussion.space, route: { path: '/' } },
        { label: discussion.title },
      ]"
    />
    <div class="flex shrink-0 items-center gap-2">
      <Button variant="ghost" icon="lucide-bell" label="Follow" />
      <Dropdown :options="spaceActions">
        <Button variant="ghost" icon="lucide-ellipsis" label="Thread actions" />
      </Dropdown>
    </div>
  </PageHeader>

  <div class="mx-auto mt-5 w-full max-w-[770px] px-3 pb-10 sm:px-5">
    <h1 class="text-3xl text-ink-gray-9">{{ discussion.title }}</h1>
    <div class="mt-2 flex items-center gap-2">
      <Badge variant="subtle" theme="gray">{{ discussion.space }}</Badge>
      <span class="text-sm text-ink-gray-5">
        {{ replies.length }} replies · last activity {{ discussion.lastActivity }}
      </span>
    </div>

    <div class="mt-6">
      <ThreadPost
        lead
        :author="discussion.author"
        :image="discussion.image"
        :time="discussion.lastActivity"
      >
        <p class="text-p-base text-ink-gray-7">{{ discussion.excerpt }}</p>
        <p v-for="p in threadBody" :key="p" class="text-p-base text-ink-gray-7">
          {{ p }}
        </p>
      </ThreadPost>
    </div>

    <div class="mt-8 space-y-6 border-t border-outline-gray-1 pt-6">
      <ThreadPost
        v-for="(reply, i) in replies"
        :key="i"
        :author="reply.author"
        :image="reply.image"
        :time="reply.time"
      >
        <p class="text-p-base text-ink-gray-7">{{ reply.text }}</p>
      </ThreadPost>
    </div>

    <div class="mt-8 flex gap-3 border-t border-outline-gray-1 pt-6">
      <Avatar :image="userImage" :label="fullName" size="xl" />
      <div class="min-w-0 flex-1">
        <Textarea
          v-model="draft"
          class="w-full"
          :rows="3"
          placeholder="Write a reply"
        />
        <div class="mt-2 flex justify-end">
          <Button
            variant="solid"
            theme="gray"
            label="Reply"
            :disabled="!draft.trim()"
            @click="postReply"
          />
        </div>
      </div>
    </div>
  </div>
</template>
