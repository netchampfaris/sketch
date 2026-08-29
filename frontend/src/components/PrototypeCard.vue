<script setup lang="ts">
/**
 * One gallery item: preview, name, description, updated time, the
 * Public/Private switch and the overflow menu (spec 11).
 *
 * Rename and Delete sit in the overflow menu, because they are UI-only
 * actions. Delete uses the destructive confirm preset.
 *
 * Every row keeps its height in both states. The link row is reserved even
 * while the Prototype is private, so turning the switch never moves the card.
 */
import { computed, ref } from 'vue'
import { Badge, Button, Dropdown, Switch, dialog, toast, useCall } from 'frappe-ui'
import PrototypeHistoryDialog from './PrototypeHistoryDialog.vue'
import PrototypePreview from './PrototypePreview.vue'
import { copyText, method } from '../store'
import type { Prototype } from '../types'

const props = defineProps<{ prototype: Prototype }>()
const emit = defineEmits<{ changed: []; removed: [] }>()

const setPublic = useCall<Prototype, { slug: string; is_public: boolean }>({
  url: method('set_public'),
  method: 'POST',
  immediate: false,
  onSuccess: () => emit('changed'),
  onError: (error) => toast.error(error.message),
})

const rename = useCall<Prototype, { slug: string; title: string }>({
  url: method('rename_prototype'),
  method: 'POST',
  immediate: false,
  onSuccess: () => {
    toast.success('Renamed')
    emit('changed')
  },
  onError: (error) => toast.error(error.message),
})

const remove = useCall<{ name: string }, { slug: string }>({
  url: method('delete_prototype'),
  method: 'POST',
  immediate: false,
  onSuccess: () => {
    toast.success('Deleted')
    emit('removed')
  },
  onError: (error) => toast.error(error.message),
})

// The dialog fetches on open, so the gallery never loads history per card.
const historyOpen = ref(false)

const busy = computed(() => setPublic.loading || rename.loading || remove.loading)

function openViewer(): void {
  window.location.href = props.prototype.viewer_path
}

async function copyPublicUrl(): Promise<void> {
  await copyText(props.prototype.public_url)
  toast.success('Link copied')
}

function askRename(): void {
  dialog.prompt({
    title: 'Rename prototype',
    message: 'The link never moves. Only the display name changes.',
    confirmLabel: 'Rename',
    fields: [
      {
        name: 'title',
        label: 'Name',
        required: true,
        defaultValue: props.prototype.title,
      },
    ],
    onConfirm: async ({ values }) => {
      await rename.submit({ slug: props.prototype.slug, title: values.title })
    },
  })
}

function askDelete(): void {
  dialog.danger({
    title: `Delete ${props.prototype.title}?`,
    message: 'The prototype and every file in it are removed. This cannot be undone.',
    confirmLabel: 'Delete',
    onConfirm: async () => {
      await remove.submit({ slug: props.prototype.slug })
    },
  })
}

const menuOptions = computed(() => [
  { label: 'Open', icon: 'lucide-external-link', onClick: openViewer },
  { label: 'Rename', icon: 'lucide-pencil', onClick: askRename },
  { label: 'History', icon: 'lucide-history', onClick: () => (historyOpen.value = true) },
  {
    label: 'Copy public link',
    icon: 'lucide-link',
    disabled: !props.prototype.is_public,
    onClick: copyPublicUrl,
  },
  { label: 'Delete', icon: 'lucide-trash-2', theme: 'red' as const, onClick: askDelete },
])
</script>

<template>
  <article class="group min-w-0">
    <div class="relative">
      <PrototypePreview :src="prototype.viewer_path" :title="prototype.title" />
      <Button
        class="absolute inset-x-4 bottom-4 opacity-0 shadow-md transition-opacity focus-visible:opacity-100 group-hover:opacity-100"
        icon-left="lucide-external-link"
        label="Open prototype"
        theme="gray"
        variant="subtle"
        @click="openViewer"
      />
    </div>

    <div class="mt-3 flex h-10 items-start gap-2">
      <div class="min-w-0 flex-1">
        <div class="flex items-center gap-2">
          <h2 class="truncate text-base font-medium text-ink-gray-8">
            {{ prototype.title }}
          </h2>
          <Badge v-if="prototype.is_public" label="Public" size="sm" theme="green" />
        </div>
        <p class="mt-1 truncate text-sm text-ink-gray-5">{{ prototype.description }}</p>
      </div>
      <Dropdown align="end" :options="menuOptions">
        <Button aria-label="Prototype actions" icon="lucide-more-horizontal" variant="ghost" />
      </Dropdown>
    </div>

    <div
      class="mt-2 flex h-9 items-center justify-between border-t border-outline-gray-1 pt-2"
    >
      <span class="truncate text-xs text-ink-gray-5">Updated {{ prototype.updated }}</span>
      <Switch
        :disabled="busy"
        :label="prototype.is_public ? 'Public' : 'Private'"
        :model-value="prototype.is_public"
        @update:model-value="
          (value) => setPublic.submit({ slug: prototype.slug, is_public: value })
        "
      />
    </div>

    <!-- Reserved in both states, so the switch never changes the card height. -->
    <div class="flex h-7 items-center">
      <Button
        v-if="prototype.is_public"
        class="max-w-full justify-start"
        icon-left="lucide-copy"
        :label="prototype.viewer_path"
        size="sm"
        variant="ghost"
        @click="copyPublicUrl"
      />
      <span v-else class="px-1 text-xs text-ink-gray-4">Private. Only you can open it.</span>
    </div>

    <PrototypeHistoryDialog v-model:open="historyOpen" :prototype="prototype" />
  </article>
</template>
