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
 *
 * Public/Private is one boolean, so it is drawn twice and no more: the switch
 * sets it, the footer row shows what it gives you, a link or nobody. The
 * "Public" Badge beside the title was a third drawing of the same fact.
 */
import { computed, ref } from 'vue'
import { Button, Dropdown, Switch, Tooltip, dialog, toast, useCall } from 'frappe-ui'
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

/**
 * The line under the name. `description` is derived on the server and its
 * wording is the server's to change (`sketch/api.py` `_row`), so the card
 * never parses it. The count is the fallback for a reply that carries no
 * description at all, which keeps the row filled and its height honest.
 */
const subtitle = computed(() => {
  if (props.prototype.description) return props.prototype.description
  const count = props.prototype.file_count
  return `${count} ${count === 1 ? 'file' : 'files'}`
})

function openViewer(): void {
  window.location.href = props.prototype.viewer_path
}

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
  // `theme: 'red'` colours the whole row, not the icon alone: frappe-ui
  // `Menu/utils.ts:164` returns `text-ink-red-7` for the label too, so this
  // row needs no class override (review 5.9).
  { label: 'Delete', icon: 'lucide-trash-2', theme: 'red' as const, onClick: askDelete },
])
</script>

<template>
  <article class="group min-w-0">
    <div class="relative">
      <PrototypePreview :src="prototype.viewer_path" :title="prototype.title" />
      <!--
        A mouse gets the named action on hover. It is never the only door:
        the preview and the title are both links to the same page, so a touch
        device, which never fires `group-hover`, still opens the prototype.
        `pointer-events-none` at rest keeps the invisible button from eating
        taps meant for the preview link under it. `shadow-lg` is the token for
        something floating over content; `shadow-md` belongs to slider thumbs
        (TOKENS > Shadow).

        It is centred at its own label width, not stretched. `inset-x-4` made
        it 406px wide on a two-column card, which reads as a bar across the
        preview and not as a button (review 5.11). `left-1/2 -translate-x-1/2`
        centres it without a wrapper element; only `opacity` transitions, so
        the offset never animates.
      -->
      <Button
        class="pointer-events-none absolute bottom-4 left-1/2 -translate-x-1/2 opacity-0 shadow-lg transition-opacity focus-visible:pointer-events-auto focus-visible:opacity-100 group-hover:pointer-events-auto group-hover:opacity-100"
        icon-left="lucide-external-link"
        label="Open prototype"
        theme="gray"
        variant="subtle"
        @click="openViewer"
      />
    </div>

    <div class="mt-3 flex h-10 items-start gap-2">
      <div class="min-w-0 flex-1">
        <!--
          A real `<a>`, not a click handler: it is the one door into the
          prototype that a touch user, a middle click and "open in new tab"
          all find. The Viewer is rendered by Python at /u/<user>/<slug> and
          is deliberately outside the SPA router (`router.ts:11`), so this is
          an href and not a RouterLink.
        -->
        <h2 class="truncate text-base-medium text-ink-gray-8">
          <a class="hover:underline" :href="prototype.viewer_path">{{ prototype.title }}</a>
        </h2>
        <p class="mt-1 truncate text-sm text-ink-gray-5">{{ subtitle }}</p>
      </div>
      <Dropdown align="end" :options="menuOptions">
        <Button aria-label="Prototype actions" icon="lucide-more-horizontal" variant="ghost" />
      </Dropdown>
    </div>

    <div
      class="mt-2 flex h-9 items-center justify-between border-t border-outline-gray-1 pt-2"
    >
      <span class="truncate text-xs text-ink-gray-5">Updated {{ prototype.updated }}</span>
      <!--
        The label goes through the slot only to drop it to 12px, so both ends
        of this row sit on one type step. `InputLabel.vue:39` hard-codes
        `text-base` on the label element and takes no size prop, and the span
        inside it wins on the cascade. The row height does not move: the
        switch group is the 16px control plus `py-1.5` (`Switch.vue:192`),
        which is the 28px this `h-9 pt-2` row already reserves.
      -->
      <Switch
        :disabled="busy"
        :model-value="prototype.is_public"
        @update:model-value="
          (value) => setPublic.submit({ slug: prototype.slug, is_public: value })
        "
      >
        <template #label>
          <span class="text-xs">{{ prototype.is_public ? 'Public' : 'Private' }}</span>
        </template>
      </Switch>
    </div>

    <!--
      Reserved in both states, so the switch never changes the card height.
      Both states start their text on the card's own left edge, with no button
      padding in front of it, so flipping the switch does not shift the line.
      The path is meta, not a title: 12px mono ink-gray-5 keeps the name above
      it the loudest thing on the card.
    -->
    <div class="flex h-7 items-center justify-between gap-2">
      <template v-if="prototype.is_public">
        <span class="min-w-0 truncate font-mono text-xs text-ink-gray-5">
          {{ prototype.viewer_path }}
        </span>
        <!--
          Icon-only because copy is universal and the path beside it already
          names what is copied. The `sm` icon button is 28px square
          (`Button.vue:209`), which is this row's full height, so its right
          edge lands on the same rail as the menu button and the switch.
        -->
        <Tooltip text="Copy public link">
          <Button
            aria-label="Copy public link"
            icon="lucide-copy"
            size="sm"
            variant="ghost"
            @click="copyPublicUrl"
          />
        </Tooltip>
      </template>
      <span v-else class="truncate text-xs text-ink-gray-5">Private. Only you can open it.</span>
    </div>

    <PrototypeHistoryDialog v-model:open="historyOpen" :prototype="prototype" />
  </article>
</template>
