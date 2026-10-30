<script setup lang="ts">
/**
 * One card under "Shared with me": a prototype somebody invited this user to.
 *
 * The same card as the gallery's own (`PrototypeCard.vue`), because it draws
 * the same picture and the same facts, minus the editors' stack: who it is
 * shared with is the owner's to know. The menu holds reads only: the invited
 * person adds variants through their own agent, and the owner decides
 * everything else. An editor's menu also has "Copy prompt", the words to hand
 * their agent. A prototype the user only talked on (`conversation`) is not
 * theirs to edit, so it has no prompt.
 *
 * Row one is the name, a gray "Private" Badge when it is private, and ⋯; the
 * preview and the name are the links in. Row two is "Updated 2 hours ago", and
 * what is new is a pill on the preview (`PrototypeMarker.vue`). Row one is
 * `h-7`, the height of a `sm` Button, row two `h-5`, so the card never moves.
 */
import { computed, ref } from 'vue'
import { Badge, Button, Dropdown, toast } from 'frappe-ui'
import PrototypeFilesDialog from './PrototypeFilesDialog.vue'
import PrototypeMarker from './PrototypeMarker.vue'
import PrototypePreview from './PrototypePreview.vue'
import { copyText, downloadPrototypeZip, session } from '../store'
import type { SharedPrototype } from '../types'

const props = defineProps<{ prototype: SharedPrototype; conversation?: boolean }>()

const filesOpen = ref(false)
const exporting = ref(false)

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
    <div class="relative">
      <PrototypePreview :href="prototype.viewer_path" :thumbnail="prototype.thumbnail" />
      <PrototypeMarker :news="prototype.new" :href="prototype.viewer_path" />
    </div>

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
      <Badge v-if="!prototype.is_public" label="Private" size="sm" theme="gray">
        <template #prefix><span class="lucide-lock size-3" aria-hidden="true" /></template>
      </Badge>
      <Dropdown align="end" :options="menuOptions">
        <Button aria-label="Prototype actions" icon="lucide-more-horizontal" variant="ghost" />
      </Dropdown>
    </div>

    <div class="flex h-5 items-center text-xs text-ink-gray-5">
      <span class="min-w-0 truncate">Updated {{ prototype.updated }}</span>
    </div>

    <PrototypeFilesDialog
      v-model:open="filesOpen"
      :slug="prototype.slug"
      :title="prototype.title"
      :username="prototype.owner.username"
    />
  </article>
</template>
