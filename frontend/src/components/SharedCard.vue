<script setup lang="ts">
/**
 * One card under "Shared with me": a prototype somebody invited this user to.
 *
 * The same two rows as the gallery card, because it draws the same picture and
 * the same facts. Row two leads with the owner, an Avatar and a name, because
 * the card is theirs and the address is theirs. The menu holds reads only:
 * the invited person adds variants through their own agent, and the owner
 * decides everything else. An editor's menu also has "Copy prompt", the words
 * to hand their agent. The same card draws "Conversations", prototypes the
 * user only talked on: they are not editors, so it has no prompt.
 *
 * Both rows are `h-7`, the height of a `sm` Button, so the card never moves.
 */
import { computed, ref } from 'vue'
import { Avatar, Button, Dropdown, Tooltip, toast } from 'frappe-ui'
import { avatarTheme } from '../../../runtime/shared/avatarTheme'
import NewLine from './NewLine.vue'
import PrototypeFilesDialog from './PrototypeFilesDialog.vue'
import PrototypePreview from './PrototypePreview.vue'
import { copyText, downloadPrototypeZip, session } from '../store'
import type { SharedPrototype } from '../types'

const props = defineProps<{ prototype: SharedPrototype; conversation?: boolean }>()

const filesOpen = ref(false)
const exporting = ref(false)

/** A prototype always opens in a new tab, and `noopener` keeps the Viewer away from this window. */
function openViewer(): void {
  window.open(props.prototype.viewer_path, '_blank', 'noopener')
}

async function copyLink(): Promise<void> {
  try {
    await copyText(props.prototype.public_url)
  } catch {
    return
  }
  toast.success('Link copied')
}

/** What an editor hands their agent: where to work, and the one folder it may write in. */
function promptFor(): string {
  const { owner, slug } = props.prototype
  const address = `${owner.username}/${slug}`
  return [
    `In Sketch, add a variant to ${address}.`,
    '',
    `- Use the prototype "${address}". I'm an invited editor there, not the owner.`,
    `- Write only in src/variants/@${session.data?.username ?? 'your-username'}/. Sketch refuses any other path, and the owner's files stay as they are.`,
    '- Start the file with a <variant set="…" name="…" /> tag. Call get_skill first for the format.',
    "- Read the owner's file for that part first, and match its look.",
    '- Commit when you are done.',
    '',
    'What to add: ',
  ].join('\n')
}

async function copyPrompt(): Promise<void> {
  try {
    await copyText(promptFor())
  } catch {
    return
  }
  toast.success('Prompt copied')
}

async function exportZip(): Promise<void> {
  exporting.value = true
  try {
    await downloadPrototypeZip(props.prototype.slug, props.prototype.owner.username)
  } finally {
    exporting.value = false
  }
}

const menuOptions = computed(() => [
  ...(props.conversation
    ? []
    : [{ label: 'Copy prompt', icon: 'lucide-message-square-text', onClick: copyPrompt }]),
  { label: 'Files', icon: 'lucide-file-code', onClick: () => (filesOpen.value = true) },
  {
    label: 'Export as zip',
    icon: 'lucide-file-archive',
    disabled: exporting.value || !props.prototype.file_count,
    onClick: exportZip,
  },
  { label: 'Copy link', icon: 'lucide-link', onClick: copyLink },
])
</script>

<template>
  <article class="flex min-w-0 flex-col">
    <PrototypePreview :href="prototype.viewer_path" :thumbnail="prototype.thumbnail" />

    <div class="mt-3 flex h-7 items-center gap-2">
      <h2 class="min-w-0 flex-1 truncate text-base-medium text-ink-gray-8">
        <a
          class="hover:underline"
          :href="prototype.viewer_path"
          rel="noopener"
          target="_blank"
          :title="prototype.title"
          >{{ prototype.title }}</a
        >
      </h2>
      <Tooltip text="Open prototype">
        <Button
          aria-label="Open prototype"
          icon="lucide-external-link"
          variant="ghost"
          @click="openViewer"
        />
      </Tooltip>
      <Dropdown align="end" :options="menuOptions">
        <Button aria-label="Prototype actions" icon="lucide-more-horizontal" variant="ghost" />
      </Dropdown>
    </div>

    <NewLine :news="prototype.new" :href="prototype.viewer_path" />

    <div class="mt-auto flex h-7 items-center gap-2">
      <Avatar
        :image="prototype.owner.user_image"
        :label="prototype.owner.full_name"
        :theme="avatarTheme(prototype.owner.username)"
        size="xs"
      />
      <span class="min-w-0 truncate text-xs text-ink-gray-5">
        <span :title="prototype.owner.full_name">{{ prototype.owner.username }}</span>
        &middot; {{ prototype.description }} &middot; Updated {{ prototype.updated }}
      </span>
    </div>

    <PrototypeFilesDialog
      v-model:open="filesOpen"
      :slug="prototype.slug"
      :title="prototype.title"
      :username="prototype.owner.username"
    />
  </article>
</template>
