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
 *
 * Two cards open this one dialog. The gallery card names a slug and means its
 * own Prototype; the feed card names a `username` too and means somebody
 * else's public one. The server reads the same pair and `is_public` is the
 * check there (`sketch.prototype.resolve_readable`), so this component takes
 * the address and asserts nothing about who owns it.
 *
 * The highlighter is a lazy chunk. It is fetched when the dialog opens and
 * never with the gallery, so a user who only looks at pictures pays nothing
 * for it, and the source reads in plain ink until it lands.
 */
import { computed, ref, shallowRef, watch } from 'vue'
import { Dialog, ErrorMessage, LoadingText, useCall } from 'frappe-ui'
import { method } from '../store'
import type { PrototypeFile, PrototypeFileSource } from '../types'

/**
 * The language each file extension is highlighted as.
 *
 * A `.vue` file is `xml`: highlight.js reads the `<script>` and `<style>`
 * blocks inside it as JavaScript and CSS on its own. An extension that is not
 * here is drawn as plain source, which is the honest answer for a file this
 * app cannot name.
 */
const LANGUAGES: Record<string, string> = {
  vue: 'xml',
  html: 'xml',
  svg: 'xml',
  xml: 'xml',
  ts: 'typescript',
  tsx: 'typescript',
  mts: 'typescript',
  js: 'javascript',
  jsx: 'javascript',
  mjs: 'javascript',
  cjs: 'javascript',
  json: 'json',
  css: 'css',
  md: 'markdown',
}

const props = defineProps<{
  /** The dialog title. The Prototype's display name. */
  title: string
  slug: string
  /**
   * The owner's handle, on a Prototype the reader does not own. Empty means
   * "mine", which is what the gallery card passes.
   */
  username?: string
}>()
const open = defineModel<boolean>('open', { required: true })

/** The address every read here carries. See the `username` prop. */
const address = computed(() => ({ slug: props.slug, username: props.username ?? '' }))

const files = useCall<PrototypeFile[], { slug: string; username: string }>({
  url: method('list_prototype_files'),
  params: () => address.value,
  immediate: false,
  initialData: [],
})

const source = useCall<
  PrototypeFileSource,
  { slug: string; path: string; username: string }
>({
  url: method('read_prototype_file'),
  immediate: false,
})

/** The path on screen. Empty until the first file lands. */
const selected = ref('')
/** Source by path. One read per file per open. */
const sources = ref<Record<string, PrototypeFileSource>>({})
/** Why a read failed, by path. A failed file is not read again on a re-click. */
const failures = ref<Record<string, string>>({})

/**
 * The highlighter, once its chunk has landed. Null until then.
 *
 * `shallowRef`, because this is a library object with a large internal graph
 * and nothing in it is reactive state.
 */
const highlighter = shallowRef<Awaited<
  typeof import('highlight.js/lib/core')
>['default'] | null>(null)

/** The in-flight load. It is the lock: one fetch per page, not per open. */
let pending: Promise<void> | null = null

/**
 * Fetch the highlighter and the languages this app can meet.
 *
 * `highlight.js/lib/core` carries no language of its own, so each one is a
 * separate import and the whole set lands as one chunk beside the gallery
 * bundle. The caller does not await it: the pane draws plain source first and
 * colours it when this resolves.
 *
 * A failed chunk is not an error the user has to read. The source is on
 * screen either way, so the lock is released and the next open tries again.
 */
function loadHighlighter(): void {
  if (highlighter.value || pending) return

  pending = (async () => {
    const [core, xml, javascript, typescript, json, css, markdown] = await Promise.all([
      import('highlight.js/lib/core'),
      import('highlight.js/lib/languages/xml'),
      import('highlight.js/lib/languages/javascript'),
      import('highlight.js/lib/languages/typescript'),
      import('highlight.js/lib/languages/json'),
      import('highlight.js/lib/languages/css'),
      import('highlight.js/lib/languages/markdown'),
    ])

    const engine = core.default
    engine.registerLanguage('xml', xml.default)
    engine.registerLanguage('javascript', javascript.default)
    engine.registerLanguage('typescript', typescript.default)
    engine.registerLanguage('json', json.default)
    engine.registerLanguage('css', css.default)
    engine.registerLanguage('markdown', markdown.default)
    highlighter.value = engine
  })().catch(() => {
    pending = null
  })
}

// The card holds one dialog per Prototype, so nothing is read until the user
// opens this. The same rule as PrototypeHistoryDialog.vue.
watch(open, async (value) => {
  if (!value) return
  // Beside the listing, not before it. The two requests do not wait for each
  // other, and the source draws as soon as the file lands.
  loadHighlighter()
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

  const answer = await source.submit({ ...address.value, path })
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

/**
 * The file on screen, marked up. Empty until the highlighter lands, and for
 * an extension it does not name: the plain branch draws those.
 *
 * `highlight()` escapes the source it returns (highlight.js `escapeHTML`),
 * and that is what makes `v-html` safe here. Nothing else in this dialog may
 * reach the DOM as markup: every file in it was written by an agent.
 */
const highlighted = computed(() => {
  const file = current.value
  const engine = highlighter.value
  if (!file || !engine) return ''

  const language = LANGUAGES[extensionOf(file.path)]
  if (!language) return ''

  try {
    return engine.highlight(file.content, { language, ignoreIllegals: true }).value
  } catch {
    // A grammar that throws is not worth a message. The plain branch draws
    // the same file, in the same box.
    return ''
  }
})

/** The size line for the pane header. */
const meta = computed(() => {
  if (!current.value) return ''
  const size = formatSize(current.value.size)
  return current.value.truncated ? `${size} · showing the start only` : size
})

function fileName(path: string): string {
  return path.slice(path.lastIndexOf('/') + 1)
}

/** The extension, lowercased, without the dot. Empty for a dotfile. */
function extensionOf(path: string): string {
  const name = fileName(path)
  const dot = name.lastIndexOf('.')
  return dot < 1 ? '' : name.slice(dot + 1).toLowerCase()
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`

  const kb = bytes / 1024
  if (kb < 1024) return `${kb < 10 ? kb.toFixed(1) : Math.round(kb)} KB`

  return `${(kb / 1024).toFixed(1)} MB`
}
</script>

<template>
  <Dialog v-model:open="open" size="5xl" :title="`${title} files`">
    <template #default>
      <!--
        One height for every state, so the loading, empty, error and loaded
        states are the same size and the dialog never jumps. The two panes
        scroll inside it, so the dialog never grows with a long file.

        The height follows the screen, because this box holds source and a
        taller box reads more of it. The chrome around it is 192px: the panel
        margin, the padding and the title row. 70vh therefore fits any window
        at least 640px tall, and the shorter one scrolls, which is what the
        dialog's own container already does. `min-h-96` is the floor, and it
        is the height the history dialog beside it uses.
      -->
      <div class="h-[70vh] min-h-96">
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

                Two branches, one box. The colours arrive when the highlighter
                chunk lands, and they change no size, no font and no padding,
                so the swap moves nothing on screen.
              -->
              <pre
                v-else
                class="sketch-code whitespace-pre font-mono text-xs leading-5 text-ink-gray-8"
              ><code v-if="highlighted" v-html="highlighted" /><code v-else>{{ current.content }}</code></pre>
            </div>
          </div>
        </div>
      </div>
    </template>
  </Dialog>
</template>

<!--
  The source theme. Not scoped: `v-html` content carries no scope attribute,
  so a scoped rule would never reach a single token. Every rule is under
  `.sketch-code`, which is the one element that holds highlighted markup.

  Four hues and no more, on the ink scale, so the theme flips with
  `data-theme` and nothing here is a hard-coded colour. Everything the
  grammar does not name stays `ink-gray-8`, the pane's own ink.
-->
<style>
.sketch-code .hljs-comment,
.sketch-code .hljs-quote {
  color: var(--ink-gray-5);
}

.sketch-code .hljs-keyword,
.sketch-code .hljs-name,
.sketch-code .hljs-selector-tag,
.sketch-code .hljs-section,
.sketch-code .hljs-meta {
  color: var(--ink-violet-6);
}

.sketch-code .hljs-string,
.sketch-code .hljs-regexp,
.sketch-code .hljs-symbol,
.sketch-code .hljs-addition {
  color: var(--ink-green-7);
}

.sketch-code .hljs-attr,
.sketch-code .hljs-attribute,
.sketch-code .hljs-property,
.sketch-code .hljs-number,
.sketch-code .hljs-literal,
.sketch-code .hljs-built_in,
.sketch-code .hljs-title,
.sketch-code .hljs-type {
  color: var(--ink-blue-7);
}
</style>
