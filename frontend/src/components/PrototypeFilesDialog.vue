<script setup lang="ts">
/**
 * The source of one Prototype, read only.
 *
 * Sketch has no editor: the agent writes the files and the Viewer renders
 * them. Between those two there was nothing that showed what the agent
 * actually wrote, so a user who wanted the source had to ask the agent to
 * print it back. This dialog is that surface, and it never writes.
 *
 * Two panes at a fixed height, so the loading, empty, error and loaded states
 * are all the same size and the dialog never jumps. The tree on the left, one
 * file on the right.
 *
 * The list is one stat walk (`sketch.api.list_prototype_files`); source
 * arrives one file at a time (`sketch.api.read_prototype_file`) and is kept
 * for as long as the dialog is open, so going back to a file costs nothing.
 */
import { computed, ref, watch } from 'vue'
import { Dialog, ErrorMessage, LoadingText, useCall } from 'frappe-ui'
import { method } from '../store'
import type { Prototype, PrototypeFile, PrototypeFileSource } from '../types'

const props = defineProps<{ prototype: Prototype }>()
const open = defineModel<boolean>('open', { required: true })

const files = useCall<PrototypeFile[], { slug: string }>({
  url: method('list_prototype_files'),
  params: () => ({ slug: props.prototype.slug }),
  immediate: false,
  initialData: [],
})

const source = useCall<PrototypeFileSource, { slug: string; path: string }>({
  url: method('read_prototype_file'),
  immediate: false,
})

/** The path on screen. Empty until the first file lands. */
const selected = ref('')
/** Source by path. One read per file per open. */
const sources = ref<Record<string, PrototypeFileSource>>({})
/** Why a read failed, by path. A failed file is not read again on a re-click. */
const failures = ref<Record<string, string>>({})

// The card holds one dialog per Prototype, so nothing is read until the user
// opens this. The same rule as PrototypeHistoryDialog.vue.
watch(open, async (value) => {
  if (!value) return
  selected.value = ''
  sources.value = {}
  failures.value = {}
  const rows = await files.reload()
  // The first path in the tree, not a favourite one. `list_files` sorts by
  // path, so a Vue app opens on src/App.vue without this code knowing that.
  if (rows?.length) select(rows[0].path)
})

/**
 * Show one file, and read it if this is the first time.
 *
 * The answer is filed under the path the server names, never under the path
 * asked for. A read replaces the one before it (`useFetch.execute` aborts the
 * request in flight), so the reply that arrives is not always the reply this
 * call asked for, and the server's own path is the only honest key.
 */
async function select(path: string): Promise<void> {
  selected.value = path
  if (sources.value[path] || failures.value[path]) return

  const answer = await source.submit({ slug: props.prototype.slug, path })
  if (answer?.path) {
    sources.value[answer.path] = answer
    return
  }

  // A newer click aborted this read. The file it selected reports its own
  // result, and this one stays unread until the user asks for it again.
  if (selected.value !== path) return
  failures.value[path] = source.error?.message ?? 'Could not read this file.'
}

/** The tree, one group per directory, root first. */
const groups = computed(() => {
  const byDirectory = new Map<string, PrototypeFile[]>()
  for (const file of files.data ?? []) {
    const cut = file.path.lastIndexOf('/')
    const directory = cut < 0 ? '' : file.path.slice(0, cut)
    const group = byDirectory.get(directory)
    if (group) group.push(file)
    else byDirectory.set(directory, [file])
  }

  return [...byDirectory.entries()]
    .sort((one, two) => one[0].localeCompare(two[0]))
    .map(([directory, entries]) => ({
      directory,
      label: directory ? `${directory}/` : '/',
      files: entries,
    }))
})

const current = computed<PrototypeFileSource | undefined>(() => sources.value[selected.value])
const failure = computed<string | undefined>(() => failures.value[selected.value])

/** The size line for the pane header. */
const meta = computed(() => {
  if (!current.value) return ''
  const size = formatSize(current.value.size)
  return current.value.truncated ? `${size} · showing the start only` : size
})

function fileName(path: string): string {
  return path.slice(path.lastIndexOf('/') + 1)
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`

  const kb = bytes / 1024
  if (kb < 1024) return `${kb < 10 ? kb.toFixed(1) : Math.round(kb)} KB`

  return `${(kb / 1024).toFixed(1)} MB`
}
</script>

<template>
  <Dialog v-model:open="open" size="5xl" :title="`${prototype.title} files`">
    <template #default>
      <!--
        One fixed height for every state, the same rule the history dialog
        follows. The two panes scroll inside it, so the dialog itself never
        grows with a long file.
      -->
      <div class="h-96">
        <LoadingText v-if="files.loading && !files.data?.length" />

        <ErrorMessage v-else-if="files.error" :message="files.error.message" />

        <!--
          The app's one empty-state recipe: 48px circle, 24px glyph, `gap-3`.
          `py-16` becomes `h-full`, because the box above already fixes the
          height.
        -->
        <div
          v-else-if="!files.data?.length"
          class="flex h-full flex-col items-center justify-center gap-3 text-center"
        >
          <span
            class="grid size-12 place-items-center rounded-full bg-surface-gray-2 text-ink-gray-5"
          >
            <span class="lucide-file-code size-6" aria-hidden="true" />
          </span>
          <p class="text-base-medium text-ink-gray-8">No files yet</p>
          <p class="max-w-sm text-p-sm text-ink-gray-5">
            The files appear here as soon as the agent writes them.
          </p>
        </div>

        <div v-else class="flex h-full gap-4">
          <!--
            The tree. A border, not a fill: this is a navigation column beside
            the source, and a second surface would read as a second card.
          -->
          <nav
            aria-label="Files"
            class="w-56 shrink-0 overflow-y-auto border-r border-outline-gray-1 pr-2"
          >
            <div v-for="group in groups" :key="group.directory" class="pb-2">
              <p
                class="flex h-7 items-center gap-1.5 truncate px-2 text-xs text-ink-gray-5"
                :title="group.label"
              >
                <span class="lucide-folder size-3.5 shrink-0" aria-hidden="true" />
                <span class="truncate">{{ group.label }}</span>
              </p>
              <button
                v-for="file in group.files"
                :key="file.path"
                class="flex h-7 w-full items-center gap-2 rounded-4 px-2 text-left text-sm hover:bg-surface-gray-2"
                :class="
                  selected === file.path
                    ? 'bg-surface-gray-3 text-ink-gray-8'
                    : 'text-ink-gray-7'
                "
                type="button"
                :title="file.path"
                @click="select(file.path)"
              >
                <span class="min-w-0 flex-1 truncate">{{ fileName(file.path) }}</span>
                <!--
                  The repeating trailing value, in its own fixed column, so
                  every name ends on the same x (DESIGN.md principle 5).
                -->
                <span class="w-12 shrink-0 text-right text-xs text-ink-gray-5">
                  {{ formatSize(file.size) }}
                </span>
              </button>
            </div>
          </nav>

          <!-- The source. `min-w-0` is what lets a long line scroll instead
               of widening the dialog. -->
          <div class="flex min-w-0 flex-1 flex-col">
            <!--
              `h-7` matches the rows in the tree beside it, so the two columns
              start on the same line and the header cannot move when the size
              text changes.
            -->
            <div class="flex h-7 shrink-0 items-center gap-3">
              <p class="min-w-0 flex-1 truncate text-sm text-ink-gray-7" :title="selected">
                {{ selected }}
              </p>
              <span class="shrink-0 whitespace-nowrap text-xs text-ink-gray-5">{{ meta }}</span>
            </div>

            <div
              class="mt-2 min-h-0 flex-1 overflow-auto rounded-4 bg-surface-gray-1 p-3"
            >
              <ErrorMessage v-if="failure" :message="failure" />
              <LoadingText v-else-if="!current" />
              <!--
                `whitespace-pre` and no wrapping: a wrapped line of source
                hides where the real line ends. Long lines scroll sideways in
                the box above instead.
              -->
              <pre
                v-else
                class="whitespace-pre font-mono text-xs leading-5 text-ink-gray-8"
              ><code>{{ current.content }}</code></pre>
            </div>
          </div>
        </div>
      </div>
    </template>
  </Dialog>
</template>
