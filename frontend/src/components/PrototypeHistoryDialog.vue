<script setup lang="ts">
/**
 * The version history of one Prototype, newest first.
 *
 * The agent records a version at the end of each user request. The prompt is
 * what the person recognises, so it leads the row. Everything else is meta.
 *
 * The list sits in a fixed-height scroll box, so the loading, empty, error and
 * loaded states all have the same size and the dialog never jumps.
 */
import { ref, watch } from 'vue'
import { Badge, Button, Dialog, ErrorMessage, LoadingText, useCall } from 'frappe-ui'
import { method } from '../store'
import type { Prototype, PrototypeVersion } from '../types'

/**
 * Tailwind builds a `lucide-*` class only when it reads the literal string in
 * this project's source, so the names live here and not in the API response.
 */
const ACTION_ICONS: Record<string, string> = {
  added: 'lucide-file-plus',
  modified: 'lucide-file-pen-line',
  deleted: 'lucide-file-minus',
}

const ACTION_COLORS: Record<string, string> = {
  added: 'text-ink-green-7',
  modified: 'text-ink-blue-7',
  deleted: 'text-ink-red-7',
}

const props = defineProps<{ prototype: Prototype }>()
const open = defineModel<boolean>('open', { required: true })

const history = useCall<PrototypeVersion[], { slug: string }>({
  url: method('list_versions'),
  params: () => ({ slug: props.prototype.slug }),
  immediate: false,
  initialData: [],
})

/** Versions whose full prompt is shown, by version name. */
const openPrompts = ref<Set<string>>(new Set())
/** Versions whose file list is shown, by version name. */
const openFiles = ref<Set<string>>(new Set())

// The card holds one dialog per Prototype, so the fetch waits for the open.
// Nothing loads while the gallery only renders the cards.
watch(open, (value) => {
  if (!value) return
  openPrompts.value = new Set()
  openFiles.value = new Set()
  history.reload()
})

function toggle(set: Set<string>, name: string): Set<string> {
  const next = new Set(set)
  if (next.has(name)) next.delete(name)
  else next.add(name)
  return next
}

/** A prompt long enough to clamp. Three lines is the clamp. */
function isLong(prompt: string): boolean {
  return prompt.split('\n').length > 3 || prompt.length > 180
}

function actionIcon(action: string): string {
  return ACTION_ICONS[action] ?? 'lucide-file'
}

function actionColor(action: string): string {
  return ACTION_COLORS[action] ?? 'text-ink-gray-6'
}

/**
 * The disclosure glyph, shared by both toggles in a row.
 *
 * Tailwind only builds a `lucide-*` class it reads as a literal in this
 * project's source, so both names stay written out here.
 */
function chevronFor(isOpen: boolean): string {
  return isOpen ? 'lucide-chevron-down' : 'lucide-chevron-right'
}

function fileLabel(count: number): string {
  return `${count} ${count === 1 ? 'file' : 'files'}`
}
</script>

<template>
  <Dialog v-model:open="open" size="xl" :title="`${prototype.title} history`">
    <template #default>
      <div class="h-96 overflow-y-auto">
        <LoadingText v-if="history.loading && !history.data?.length" />

        <ErrorMessage v-else-if="history.error" :message="history.error.message" />

        <!--
          The one empty-state recipe the app uses: 48px circle, 24px glyph,
          `gap-3`. It matches the gallery's empty state on the Prototypes
          screen. `py-16` becomes `h-full` because the scroll box above
          already fixes the height.
        -->
        <div
          v-else-if="!history.data?.length"
          class="flex h-full flex-col items-center justify-center gap-3 text-center"
        >
          <span
            class="grid size-12 place-items-center rounded-full bg-surface-gray-2 text-ink-gray-5"
          >
            <span class="lucide-history size-6" aria-hidden="true" />
          </span>
          <p class="text-base-medium text-ink-gray-8">No version yet</p>
          <p class="max-w-sm text-p-sm text-ink-gray-5">
            The agent records a version each time it changes this prototype.
          </p>
        </div>

        <!--
          A read-only list: the row itself is not a target, so it carries no
          hover surface and no gutter bleed. The separator is `divide-y` on the
          list, not `border-b` on a rounded row, which used to draw a straight
          rule across a rounded corner.
        -->
        <ul v-else class="divide-y divide-outline-gray-1">
          <li v-for="version in history.data" :key="version.name" class="py-3 first:pt-0">
            <div class="flex items-start gap-3">
              <p
                class="min-w-0 flex-1 whitespace-pre-line text-p-base text-ink-gray-8"
                :class="openPrompts.has(version.name) ? '' : 'line-clamp-3'"
              >
                {{ version.prompt }}
              </p>
              <!--
                A fixed trailing column, per DESIGN.md principle 5. `created`
                is `pretty_date` in long form (`sketch/api.py:241`), so the
                text runs from "just now" to "22 minutes ago"; `w-24` holds the
                longest of those on one line and every prompt then ends on the
                same x.
              -->
              <span
                class="w-24 shrink-0 whitespace-nowrap text-right text-xs text-ink-gray-5"
                :title="version.creation"
              >
                {{ version.created }}
              </span>
            </div>

            <p v-if="version.summary" class="mt-1 text-p-sm text-ink-gray-6">
              {{ version.summary }}
            </p>

            <div class="mt-2 flex flex-wrap items-center gap-2">
              <Badge
                v-if="version.files_added"
                :label="`${version.files_added} added`"
                size="sm"
                theme="green"
              />
              <Badge
                v-if="version.files_modified"
                :label="`${version.files_modified} changed`"
                size="sm"
                theme="blue"
              />
              <Badge
                v-if="version.files_deleted"
                :label="`${version.files_deleted} deleted`"
                size="sm"
                theme="red"
              />

              <!--
                Both toggles are disclosures, so both carry the same chevron:
                right when closed, down when open. `chevronFor` keeps the two
                literal class names in one place for Tailwind's scanner.
              -->
              <Button
                v-if="version.changes.length"
                :icon-left="chevronFor(openFiles.has(version.name))"
                :label="fileLabel(version.changes.length)"
                size="sm"
                variant="ghost"
                @click="openFiles = toggle(openFiles, version.name)"
              />

              <Button
                v-if="isLong(version.prompt)"
                :icon-left="chevronFor(openPrompts.has(version.name))"
                :label="openPrompts.has(version.name) ? 'Show less' : 'Show full prompt'"
                size="sm"
                variant="ghost"
                @click="openPrompts = toggle(openPrompts, version.name)"
              />
            </div>

            <ul
              v-if="openFiles.has(version.name)"
              class="mt-2 space-y-1 rounded-4 bg-surface-gray-2 px-3 py-2"
            >
              <li
                v-for="change in version.changes"
                :key="change.path"
                class="flex items-center gap-2 text-xs text-ink-gray-7"
              >
                <span
                  :class="[actionIcon(change.action), actionColor(change.action), 'size-3.5 shrink-0']"
                  aria-hidden="true"
                />
                <span class="truncate">{{ change.path }}</span>
                <span class="ml-auto shrink-0 text-ink-gray-5">{{ change.action }}</span>
              </li>
            </ul>
          </li>
        </ul>
      </div>

      <!--
        The Runtime pin, at meta size. It used to lead the card subtitle, which
        made the library version the loudest fact about a Prototype and told a
        new user nothing they could act on (review 5.8); `sketch/api.py:250`
        still returns it, and this is where it lands. It is one build detail
        for the whole Prototype, not a per-version fact, so it sits under the
        list and never becomes a heading. The value is constant while the
        dialog is open, so this row cannot move the panel.
      -->
      <p class="mt-3 truncate border-t border-outline-gray-1 pt-3 text-xs text-ink-gray-5">
        Pinned to frappe-ui {{ prototype.pin }}
      </p>
    </template>
  </Dialog>
</template>
