<script setup lang="ts">
/**
 * One gallery item: preview, then two rows (spec 11).
 *
 * Row one is the name, a Badge for the Public/Private state, and the action
 * rail: Open, then the overflow menu. Row two is every meta fact on one line,
 * with the copy-link button when there is a link.
 *
 * Public/Private is one boolean and it is drawn once, by the Badge. The menu
 * sets it: Share makes it public, Make private takes it back. It was a Switch
 * on the card, which put a control that publishes to the internet one stray
 * click away from the artwork, and cost a row to say what the Badge says.
 *
 * Rename, History and Delete sit in the same menu, because they are UI-only
 * actions. Delete uses the destructive confirm preset.
 *
 * Both rows are `h-7`, the height of a `sm` Button, so no state change moves
 * the card.
 */
import { computed, ref } from 'vue'
import { Badge, Button, Dropdown, Tooltip, dialog, toast, useCall } from 'frappe-ui'
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

/**
 * A Prototype always opens in a new tab, so the gallery stays where it was.
 *
 * `noopener` is not optional here. The Viewer runs prototype code that the
 * user's own agent wrote, and without it that page holds a live
 * `window.opener` handle to Sketch. It also implies `noreferrer` in every
 * current browser, which is why only the one token is passed.
 */
function openViewer(): void {
  window.open(props.prototype.viewer_path, '_blank', 'noopener')
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
  // No Open row: the action has its own button beside this menu.
  //
  // One row, two labels. It names what the click does next, not the state the
  // card is already in: the Badge beside the title carries the state. It is
  // disabled while a write is in flight, which is the job the switch's own
  // `:disabled` used to do.
  props.prototype.is_public
    ? {
        label: 'Make private',
        icon: 'lucide-lock',
        disabled: busy.value,
        onClick: () => setPublic.submit({ slug: props.prototype.slug, is_public: false }),
      }
    : {
        label: 'Share',
        icon: 'lucide-globe',
        disabled: busy.value,
        onClick: () => setPublic.submit({ slug: props.prototype.slug, is_public: true }),
      },
  {
    label: 'Copy public link',
    icon: 'lucide-link',
    disabled: !props.prototype.is_public,
    onClick: copyPublicUrl,
  },
  { label: 'Rename', icon: 'lucide-pencil', onClick: askRename },
  { label: 'History', icon: 'lucide-history', onClick: () => (historyOpen.value = true) },
  // `theme: 'red'` colours the whole row, not the icon alone: frappe-ui
  // `Menu/utils.ts:164` returns `text-ink-red-7` for the label too, so this
  // row needs no class override (review 5.9).
  { label: 'Delete', icon: 'lucide-trash-2', theme: 'red' as const, onClick: askDelete },
])
</script>

<template>
  <article class="min-w-0">
    <PrototypePreview :href="prototype.viewer_path" :thumbnail="prototype.thumbnail" />

    <!--
      Two rows under the preview, not four. Name and state on the first, every
      meta fact on the second. `h-7` on both is the height of a `sm` Button
      (`Button.vue:209`), so the action rail sets the rhythm and neither row
      changes height when its contents change.
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
      <!--
        The Badge reports the state. It does not set it: Share and Make
        private are in the menu, so nothing on the card can be toggled by a
        stray click on the artwork. `sm` keeps it quieter than the name beside
        it, and green reads as "anyone can reach this", which is the fact that
        matters here.
      -->
      <Badge
        :label="prototype.is_public ? 'Public' : 'Private'"
        size="sm"
        :theme="prototype.is_public ? 'green' : 'gray'"
      />
      <!--
        Open sits on the action rail beside the menu, not over the preview. A
        button floating on the artwork needed a shadow to stay legible, and it
        appeared on hover only, so it was invisible until the pointer arrived
        and absent on touch. Here it is always on screen and always in the
        same place.

        Icon-only with a Tooltip, the same treatment as "Copy public link"
        below. DESIGN principle 6 reserves that for universal actions, and the
        card names the target three times over: the title, the preview and the
        path. The menu drops its own Open row, which this replaces.
      -->
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

    <!--
      Every meta fact on one line, in the order a user asks for them: how big
      is it, when did the agent last touch it. One separator, one type step,
      one ink step, so the line reads as a single caption and not as a list.

      The copy button only exists while there is a link to copy. The row keeps
      its height either way, because `h-7` is the button's own height.
    -->
    <div class="flex h-7 items-center justify-between gap-2">
      <span class="min-w-0 truncate text-xs text-ink-gray-5">
        {{ subtitle }} &middot; Updated {{ prototype.updated }}
      </span>
      <!--
        Icon-only because copy is universal, and the Badge above already says
        the link exists. Its right edge lands on the same rail as the menu
        button on the row above (`Button.vue:209`, `sm` is 28px square).
      -->
      <Tooltip v-if="prototype.is_public" text="Copy public link">
        <Button
          aria-label="Copy public link"
          icon="lucide-copy"
          size="sm"
          variant="ghost"
          @click="copyPublicUrl"
        />
      </Tooltip>
    </div>

    <PrototypeHistoryDialog v-model:open="historyOpen" :prototype="prototype" />
  </article>
</template>
