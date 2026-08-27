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

function fileLabel(count: number): string {
  return `${count} ${count === 1 ? 'file' : 'files'}`
}
</script>

<template>
  <Dialog v-model:open="open" size="xl" :title="`${prototype.title} history`">
    <template #default>
      <div class="h-96 overflow-y-auto">
        <LoadingText v-if="history.loading && !history.data?.length" :lines="4" />

        <ErrorMessage v-else-if="history.error" :message="history.error.message" />

        <div
          v-else-if="!history.data?.length"
          class="flex h-full flex-col items-center justify-center px-6 text-center"
        >
          <span
            class="grid size-10 place-items-center rounded-full bg-surface-gray-2 text-ink-gray-5"
          >
            <span class="lucide-history size-5" aria-hidden="true" />
          </span>
          <p class="mt-3 text-base font-medium text-ink-gray-8">No version yet</p>
          <p class="mt-1 text-p-sm text-ink-gray-5">
            The agent records a version each time it changes this prototype.
          </p>
        </div>

        <ul v-else class="-mx-2">
          <li
            v-for="version in history.data"
            :key="version.name"
            class="rounded-4 border-b border-outline-gray-1 px-2 py-3 transition-colors last:border-b-0 hover:bg-surface-gray-1"
          >
            <div class="flex items-start gap-3">
              <p
                class="min-w-0 flex-1 whitespace-pre-line text-p-base text-ink-gray-8"
                :class="openPrompts.has(version.name) ? '' : 'line-clamp-3'"
              >
                {{ version.prompt }}
              </p>
              <span class="shrink-0 text-xs text-ink-gray-5" :title="version.creation">
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

              <Button
                v-if="version.changes.length"
                :icon-left="
                  openFiles.has(version.name) ? 'lucide-chevron-down' : 'lucide-chevron-right'
                "
                :label="fileLabel(version.changes.length)"
                size="sm"
                variant="ghost"
                @click="openFiles = toggle(openFiles, version.name)"
              />

              <Button
                v-if="isLong(version.prompt)"
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
    </template>
  </Dialog>
</template>
