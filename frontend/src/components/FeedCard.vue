<script setup lang="ts">
/**
 * One card on /feed: somebody else's public Prototype.
 *
 * The same two rows as the gallery card (`PrototypeCard.vue`), because both
 * draw the same picture and the same facts. What differs is who owns the
 * thing under it, so row two leads with the author, an Avatar and a handle,
 * and the menu holds no write that touches the Prototype itself.
 *
 * The actions are Fork, Files, Export as zip and Copy link. Fork is the only
 * one that needs a session: it writes a new Prototype into the reader's own
 * gallery. The other three read what the Viewer already renders, so a Guest
 * gets them too (`sketch.prototype.resolve_readable`).
 *
 * Row one is `h-7`, the height of a `sm` Button; row two is `h-5`, one line of
 * text, so it sits close under the title. No state change moves the card.
 */
import { computed, ref } from 'vue'
import { Avatar, Button, Dropdown, toast, useCall } from 'frappe-ui'
import PrototypeFilesDialog from './PrototypeFilesDialog.vue'
import PrototypePreview from './PrototypePreview.vue'
import { copyText, downloadPrototypeZip, method, prototypes, signedIn, errorText } from '../store'
import type { Prototype, PublicPrototype } from '../types'

const props = defineProps<{ prototype: PublicPrototype }>()

const filesOpen = ref(false)

/** True while the zip is on the wire. It disables the menu, like a write. */
const exporting = ref(false)

/**
 * Copy this Prototype into the reader's own gallery.
 *
 * The gallery is reloaded on success, so the copy is already there when the
 * user follows the toast to it. The toast is the only report: the feed does
 * not move, because the fork is private and belongs on the other screen.
 */
const fork = useCall<Prototype, { username: string; slug: string }>({
  url: method('fork_prototype'),
  method: 'POST',
  immediate: false,
  onSuccess: (row) => {
    prototypes.reload()
    toast.success(`Forked ${row.title}. It is private, in your prototypes.`)
  },
  onError: (error) => toast.error(errorText(error)),
})

const busy = computed(() => fork.loading || exporting.value)


async function copyLink(): Promise<void> {
  try {
    await copyText(props.prototype.public_url)
  } catch {
    // `copyText` rejects only after it has shown the text to copy by hand, so
    // there is nothing left to say, and the green toast below must not fire
    // next to the red one.
    return
  }
  toast.success('Link copied')
}

async function exportZip(): Promise<void> {
  exporting.value = true
  try {
    await downloadPrototypeZip(props.prototype.slug, props.prototype.username)
  } finally {
    exporting.value = false
  }
}

/**
 * Fork leads, and it is absent for a Guest rather than disabled.
 *
 * A disabled row makes the reader click to learn why. The top bar carries the
 * one sign-in action on this page, so a signed-out reader is asked once, in
 * one place.
 */
// A write's `submit` rejects on failure. Its `onError` already shows a toast,
// so each menu row drops the rejection with `.catch(() => {})`.
const menuOptions = computed(() => [
  ...(signedIn.value
    ? [
        {
          label: 'Fork this prototype',
          icon: 'lucide-git-fork',
          disabled: busy.value,
          onClick: () =>
            fork
              .submit({
                username: props.prototype.username,
                slug: props.prototype.slug,
              })
              .catch(() => {}),
        },
      ]
    : []),
  { label: 'Files', icon: 'lucide-file-code', onClick: () => (filesOpen.value = true) },
  // Disabled on an empty tree, the same rule the gallery menu carries. A zip
  // of nothing is a file the user has to open to learn it holds nothing.
  {
    label: 'Export as zip',
    icon: 'lucide-file-archive',
    disabled: busy.value || !props.prototype.file_count,
    onClick: exportZip,
  },
  { label: 'Copy link', icon: 'lucide-link', onClick: copyLink },
])
</script>

<template>
  <article class="min-w-0">
    <PrototypePreview :href="prototype.viewer_path" :thumbnail="prototype.thumbnail" />

    <div class="mt-3 flex h-7 items-center gap-2">
      <!--
        A real `<a>`, not a click handler: it is the one door a touch user, a
        middle click and "open in new tab" all find. The Viewer is rendered by
        Python at /u/<user>/<slug> and is outside the SPA router
        (`router.ts`), so this is an href and not a RouterLink.
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
      <!--
        No Badge: every card on this page is public. No Open button: the
        preview and the name are the links in.
      -->
      <Dropdown align="end" :options="menuOptions">
        <Button aria-label="Prototype actions" icon="lucide-more-horizontal" variant="ghost" />
      </Dropdown>
    </div>

    <!--
      The author leads this row, because the feed crosses users and the handle
      is also the first half of the address. The Avatar is `xs`, 16px, so the
      row keeps the `h-5` under the title and the face sits inside the
      cap height of the text beside it.
    -->
    <div class="flex h-5 items-center gap-2">
      <Avatar
        :image="prototype.user_image"
        :label="prototype.full_name"
        size="xs"
      />
      <span class="min-w-0 truncate text-xs text-ink-gray-5">
        {{ prototype.username }} &middot; {{ prototype.description }} &middot; Updated
        {{ prototype.updated }}
      </span>
    </div>

    <PrototypeFilesDialog
      v-model:open="filesOpen"
      :slug="prototype.slug"
      :title="prototype.title"
      :username="prototype.username"
    />
  </article>
</template>
