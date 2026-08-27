<script setup lang="ts">
import { ref } from 'vue'
import { Button, toast } from 'frappe-ui'
import {
  CommentKit,
  Editor,
  EditorContent,
  EditorFixedMenu,
  commentToolbar,
} from 'frappe-ui/editor'

// The reply box. `Editor` is renderless, so this file owns the chrome:
// EditorFixedMenu on top, EditorContent below, actions in the footer.
const props = defineProps<{ to: string }>()
const emit = defineEmits<{ (event: 'close'): void }>()

const body = ref('')

function send() {
  body.value = ''
  toast.success(`Reply sent to ${props.to}`)
  emit('close')
}
</script>

<template>
  <div
    class="shrink-0 border-t border-outline-gray-1 bg-surface-base px-5 py-4"
  >
    <div class="mb-2 flex items-center gap-2">
      <span class="lucide-reply size-4 text-ink-gray-5" aria-hidden="true" />
      <span class="text-sm text-ink-gray-6">To {{ to }}</span>
      <Button
        variant="ghost"
        icon="lucide-x"
        label="Discard reply"
        class="ml-auto"
        @click="$emit('close')"
      />
    </div>

    <div class="rounded-5 border border-outline-gray-2 bg-surface-base">
      <Editor
        v-model="body"
        :extensions="[CommentKit]"
        placeholder="Write your reply…"
      >
        <div class="border-b border-outline-gray-1 px-2 py-1.5">
          <EditorFixedMenu :items="commentToolbar" button-size="sm" />
        </div>
        <EditorContent class="max-h-56 overflow-y-auto px-3 py-2" />
      </Editor>
    </div>

    <div class="mt-3 flex items-center gap-2">
      <Button
        variant="solid"
        theme="gray"
        label="Send"
        icon-left="lucide-send"
        @click="send"
      />
      <Button variant="ghost" icon="lucide-paperclip" label="Attach a file" />
      <Button variant="ghost" icon="lucide-smile" label="Add an emoji" />
    </div>
  </div>
</template>
