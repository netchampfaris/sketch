<script setup lang="ts">
import { ref } from 'vue'
import { Breadcrumbs, Button, PageHeader, PageHeaderBase } from 'frappe-ui'
import {
  AlignCenter,
  AlignLeft,
  AlignRight,
  Blockquote,
  Bold,
  BulletList,
  Editor,
  EditorContent,
  EditorFixedMenu,
  FontColor,
  H2,
  H3,
  H4,
  HorizontalRule,
  InlineCode,
  InsertImage,
  InsertLink,
  InsertTable,
  InsertVideo,
  Italic,
  OrderedList,
  Paragraph,
  Redo,
  RichTextKit,
  Separator,
  Strike,
  Undo,
} from 'frappe-ui/editor'
import ComposeTitle from '../components/ComposeTitle.vue'
import { initialContent, initialTitle, people } from '../data'

const extensions = [RichTextKit.configure({ mention: { items: people } })]

// The rich-text compose toolbar, item for item.
const toolbar = [
  Paragraph,
  H2,
  H3,
  H4,
  Separator,
  Bold,
  Italic,
  Strike,
  Separator,
  BulletList,
  OrderedList,
  Separator,
  AlignLeft,
  AlignCenter,
  AlignRight,
  FontColor,
  Separator,
  InsertImage,
  InsertVideo,
  InsertLink,
  Blockquote,
  InlineCode,
  HorizontalRule,
  Separator,
  InsertTable,
  Separator,
  Undo,
  Redo,
]

const title = ref(initialTitle)
const content = ref(initialContent)

// Demo only: turns dropped or pasted files into local object URLs. A real app
// returns a stored URL from its upload endpoint.
const uploadFunction = async (file: File) => ({
  file_url: URL.createObjectURL(file),
  file_name: file.name,
})
</script>

<template>
  <Editor
    v-model="content"
    :extensions="extensions"
    :upload-function="uploadFunction"
    placeholder="Type '/' for commands or select text to format"
  >
    <template #default="{ editor }">
      <PageHeader>
        <Breadcrumbs :items="[{ label: 'Drafts' }, { label: 'New discussion' }]" />
        <div class="flex shrink-0 items-center space-x-2">
          <Button variant="ghost" icon="lucide-trash-2" label="Delete draft" />
          <Button variant="solid">Publish</Button>
        </div>
      </PageHeader>

      <PageHeaderBase
        class="flex h-10 items-center border-b bg-surface-base px-3 sm:px-5"
      >
        <div class="w-full overflow-x-auto">
          <EditorFixedMenu :editor="editor" :items="toolbar" />
        </div>
      </PageHeaderBase>

      <!-- Prose container: 720px of prose plus padding. -->
      <div class="mx-auto w-full max-w-[770px] px-3 pt-4 sm:px-5">
        <ComposeTitle v-model="title" @next="editor.commands.focus()" />
        <EditorContent
          :editor="editor"
          class="prose-v3 -mx-2 min-h-[calc(100vh-200px)] max-w-[unset] overflow-auto px-2 pb-40"
        />
      </div>
    </template>
  </Editor>
</template>
