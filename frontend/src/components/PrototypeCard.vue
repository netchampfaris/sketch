<script setup lang="ts">
/**
 * One gallery item: preview, then two rows, two controls (decisions 60, 70).
 *
 * Row one is the name, a gray "Private" Badge only when it is private (public
 * is the default, so it goes unsaid), the editors' stack, then the overflow
 * menu. Row two is "Updated 2 hours ago" and nothing else. What is new is a
 * pill on the preview's corner (`PrototypeMarker.vue`). The preview and the
 * name are the ways in, both real links, so there is no Open button.
 *
 * Public/Private is set in the Share dialog, never on the card. Share has one
 * home, "Share…" in the menu, and "Copy link" sits right after it while there
 * is a public link to copy. The editors' stack says who it is shared with, and
 * opens the same dialog. No editors, no stack.
 *
 * Rename, Files, Export as zip, History and Delete sit in the same menu,
 * because they are UI-only actions. Files reads the source the agent wrote,
 * Export takes it away, History reads when it was written. Delete uses the
 * destructive confirm preset.
 *
 * Row one is `h-7`, the height of a `sm` Button; row two is `h-5`, one line of
 * text, so it sits close under the title. No state change moves the card.
 */
import { computed, ref } from 'vue'
import { Avatar, Badge, Button, Dropdown, Tooltip, dialog, toast, useCall } from 'frappe-ui'
import { avatarTheme } from '../../../runtime/shared/avatarTheme'
import PrototypeFilesDialog from './PrototypeFilesDialog.vue'
import PrototypeHistoryDialog from './PrototypeHistoryDialog.vue'
import PrototypeMarker from './PrototypeMarker.vue'
import PrototypePreview from './PrototypePreview.vue'
import ShareDialog from './ShareDialog.vue'
import { copyText, downloadPrototypeZip, method, errorText } from '../store'
import type { Prototype } from '../types'

const props = defineProps<{ prototype: Prototype }>()
const emit = defineEmits<{ changed: []; removed: [] }>()

const rename = useCall<Prototype, { slug: string; title: string }>({
  url: method('rename_prototype'),
  method: 'POST',
  immediate: false,
  onSuccess: () => {
    toast.success('Renamed')
    emit('changed')
  },
  onError: (error) => toast.error(errorText(error)),
})

/**
 * Re-take the card picture on demand.
 *
 * It runs a real browser on the server, so it is slower than the other rows
 * in this menu, about two seconds. `busy` disables the whole menu while it is
 * in flight, which is the only progress this card shows: a spinner inside a
 * closed dropdown would be invisible, and the toast says when it is done.
 */
const refresh = useCall<Prototype, { slug: string }>({
  url: method('refresh_preview'),
  method: 'POST',
  immediate: false,
  onSuccess: () => {
    toast.success('Preview updated')
    emit('changed')
  },
  onError: (error) => toast.error(errorText(error)),
})

const remove = useCall<{ name: string }, { slug: string }>({
  url: method('delete_prototype'),
  method: 'POST',
  immediate: false,
  onSuccess: () => {
    toast.success('Deleted')
    emit('removed')
  },
  onError: (error) => toast.error(errorText(error)),
})

// Both dialogs fetch on open, so the gallery never loads history or source
// per card.
const historyOpen = ref(false)
const filesOpen = ref(false)
const shareOpen = ref(false)

/** The editors as the stack and its tooltip tell it: the first three faces, the rest as +n. */
const SHOWN = 3
const NAMED = 6
const sharedWith = computed(() => {
  const people = props.prototype.editors ?? []
  const names = people.map((p) => p.full_name.split(/\s+/)[0] || p.username)
  const listed = names.slice(0, NAMED).join(', ')
  const rest = names.length - NAMED
  return {
    length: people.length,
    shown: people.slice(0, SHOWN),
    more: Math.max(people.length - SHOWN, 0),
    text: `Shared with ${listed}${rest > 0 ? ` and ${rest} more` : ''}`,
  }
})

/** True while the zip is on the wire. It disables the menu, like a write. */
const exporting = ref(false)

const busy = computed(
  () =>
    rename.loading ||
    remove.loading ||
    refresh.loading ||
    exporting.value,
)

async function copyPublicUrl(): Promise<void> {
  try {
    await copyText(props.prototype.public_url)
  } catch {
    // `copyText` rejects only after it has shown the text to copy by hand, so
    // there is nothing left to say. The catch is here to keep the rejection
    // from surfacing as an unhandled promise in the console, and to keep the
    // green toast below from firing next to the red one.
    return
  }
  toast.success('Link copied')
}

/**
 * Take the whole tree away as one zip.
 *
 * `downloadPrototypeZip` owns the request and both toasts, because the feed
 * card runs the same action against somebody else's public Prototype. This
 * only holds the flag that disables the menu while it is on the wire.
 */
async function exportZip(): Promise<void> {
  exporting.value = true
  try {
    await downloadPrototypeZip(props.prototype.slug)
  } finally {
    exporting.value = false
  }
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

// A write's `submit` rejects on failure. Its `onError` already shows a toast,
// so each menu row drops the rejection with `.catch(() => {})`.
const menuOptions = computed(() => [
  // No Open row: the preview and the name are links.
  //
  // Share opens the dialog that holds who is invited and whether the link is
  // public. Copy link follows it while there is a public link to copy.
  { label: 'Share…', icon: 'lucide-users', onClick: () => (shareOpen.value = true) },
  ...(props.prototype.is_public ? [{ label: 'Copy link', icon: 'lucide-link', onClick: copyPublicUrl }] : []),
  // Above Rename, because it is about the picture the row sits under, and the
  // rows below it are about the Prototype's name and history. It is one row
  // whatever the card is showing: "there is no picture yet" and "the picture
  // is of an older tree" are the same ask from the user, and a label that
  // changed with the state would make the user read it before every click.
  {
    label: 'Refresh preview',
    icon: 'lucide-refresh-cw',
    disabled: busy.value,
    onClick: () => refresh.submit({ slug: props.prototype.slug }).catch(() => {}),
  },
  { label: 'Rename', icon: 'lucide-pencil', onClick: askRename },
  { label: 'Files', icon: 'lucide-file-code', onClick: () => (filesOpen.value = true) },
  // Disabled on an empty tree. A zip of nothing is a file the user has to open to
  // learn it holds nothing.
  {
    label: 'Export as zip',
    icon: 'lucide-file-archive',
    disabled: busy.value || !props.prototype.file_count,
    onClick: exportZip,
  },
  { label: 'History', icon: 'lucide-history', onClick: () => (historyOpen.value = true) },
  // `theme: 'red'` colours the whole row, not the icon alone: frappe-ui
  // `Menu/utils.ts:164` returns `text-ink-red-7` for the label too, so this
  // row needs no class override (review 5.9).
  { label: 'Delete', icon: 'lucide-trash-2', theme: 'red' as const, onClick: askDelete },
])
</script>

<template>
  <article class="flex min-w-0 flex-col">
    <div class="relative">
      <PrototypePreview :href="prototype.viewer_path" :thumbnail="prototype.thumbnail" />
      <PrototypeMarker :news="prototype.new" :href="prototype.viewer_path" />
    </div>

    <!--
      Two rows under the preview: `h-7`, the height of a `sm` Button (`Button.vue:209`),
      then `h-5` for the line of text. Neither changes height when its contents change.
    -->
    <div class="mt-3 flex h-7 items-center gap-2">
      <!--
        A real `<a>`, not a click handler: it is the one door into the
        prototype that a touch user, a middle click and "open in new tab"
        all find. The Viewer is rendered by Python at /u/<user>/<slug> and
        is deliberately outside the SPA router (`router.ts:11`), so this is
        an href and not a RouterLink.
      -->
      <h2 class="min-w-0 flex-1 truncate text-base-medium text-ink-gray-8">
        <a
          class="hover:underline"
          :href="prototype.viewer_path"
          rel="noopener"
          target="_blank"
          >{{ prototype.title }}</a
        >
      </h2>
      <!-- Only the exception is drawn: public is the default. The Share dialog sets it, never the card. -->
      <Badge v-if="!prototype.is_public" label="Private" size="sm" theme="gray">
        <template #prefix><span class="lucide-lock size-3" aria-hidden="true" /></template>
      </Badge>
      <!--
        Status: who it is shared with, up to three faces and then +n. A click opens the share dialog the menu opens,
        but it draws as faces, not as a Button: no box, no hover fill. The ring is the page's own surface colour
        (`--surface-base`; Tailwind has no `ring-surface-*`), so it cuts each face from the next.
      -->
      <Tooltip v-if="sharedWith.length" :text="sharedWith.text">
        <button
          type="button"
          class="flex items-center rounded-full focus-visible:ring-0 focus-visible:focus-ring"
          :aria-label="sharedWith.text"
          @click="shareOpen = true"
        >
            <span class="flex -space-x-1.5">
              <Avatar
                v-for="person in sharedWith.shown"
                :key="person.username"
                class="ring-2 ring-[color:var(--surface-base)]"
                size="sm"
                :theme="avatarTheme(person.username)"
                :image="person.user_image"
                :label="person.full_name"
              />
            </span>
            <span v-if="sharedWith.more" class="ml-1 text-xs tabular-nums text-ink-gray-5">+{{ sharedWith.more }}</span>
        </button>
      </Tooltip>
      <Dropdown align="end" :options="menuOptions">
        <Button aria-label="Prototype actions" icon="lucide-more-horizontal" variant="ghost" />
      </Dropdown>
    </div>

    <div class="flex h-5 items-center text-xs text-ink-gray-5">
      <span class="min-w-0 truncate">Updated {{ prototype.updated }}</span>
    </div>

    <ShareDialog v-model:open="shareOpen" :prototype="prototype" @changed="emit('changed')" />
    <PrototypeFilesDialog
      v-model:open="filesOpen"
      :slug="prototype.slug"
      :title="prototype.title"
    />
    <!-- A restore changes the tree, so the picture and "Updated" are stale. -->
    <PrototypeHistoryDialog
      v-model:open="historyOpen"
      :prototype="prototype"
      @restored="emit('changed')"
    />
  </article>
</template>
