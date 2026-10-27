<script setup lang="ts">
/**
 * The version history of one Prototype, newest first.
 *
 * The agent records a version at the end of each user request. The prompt is
 * what the person recognises, so it leads the row, and the meta line under it
 * holds the only other facts: when, and how many files changed. A row has no
 * version number, no badge and no button. Everything that acts on a row lives
 * in its ... menu, which shows on hover so the list reads as plain text.
 *
 * The newest row is Current. Every other row that kept a snapshot offers
 * "Restore this version", which opens the confirm step
 * (`PrototypeRestoreDialog`). A restore is recorded as a new version on top,
 * so it is never a loss: while that restore is Current, its menu offers "Undo
 * restore", which restores the version just below it.
 *
 * Undo lives in the row menu and not in a toast. A modal reka dialog sets
 * `pointer-events: none` on the body and its overlay catches every click, so a
 * toast action under an open dialog cannot be clicked: the click closes the
 * dialog instead.
 *
 * Rows group under a sticky day header. A click on a row opens it (full prompt
 * and file list), or on a restore row jumps to the version it restored. The
 * rows are a roving-tabindex list: arrows move between them, Tab goes on to the
 * active row's menu. From ten versions up a search box filters by prompt.
 *
 * The list sits in a fixed-height scroll box, so the loading, empty, error and
 * loaded states all have the same size and the dialog never jumps.
 */
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { Button, Dialog, Dropdown, ErrorMessage, LoadingText, TextInput, toast, useCall } from 'frappe-ui'
import PrototypeChangeList from './PrototypeChangeList.vue'
import PrototypeDeleteVersionsDialog from './PrototypeDeleteVersionsDialog.vue'
import PrototypeRestoreDialog from './PrototypeRestoreDialog.vue'
import { method } from '../store'
import type { HistoryUsage, Prototype, PrototypeVersion, PruneResult, RestoreResult } from '../types'

/** A prompt past this many lines or characters is clamped to two lines. */
const CLAMP_LINES = 2
const CLAMP_CHARS = 140
/** The search box shows from this many versions up. */
const SEARCH_MIN_VERSIONS = 10
/** How long a jumped-to row stays lit (scroll time), then how long it fades. */
const FLASH_HOLD_MS = 600
const FLASH_FADE_MS = 1200

interface DaySection {
  key: string
  label: string
  versions: PrototypeVersion[]
}

const props = defineProps<{ prototype: Prototype }>()
const open = defineModel<boolean>('open', { required: true })
// The card reloads the gallery on this, so the thumbnail and "Updated" move.
const emit = defineEmits<{ restored: [] }>()

const history = useCall<PrototypeVersion[], { slug: string }>({
  url: method('list_versions'),
  params: () => ({ slug: props.prototype.slug }),
  immediate: false,
  initialData: [],
})

const usage = useCall<HistoryUsage, { slug: string }>({
  url: method('history_usage'),
  params: () => ({ slug: props.prototype.slug }),
  immediate: false,
})

// Same method as the confirm step, with the dry run off. Undo needs no preview:
// it puts back the tree the person was just looking at, as a new version.
const undoRestore = useCall<RestoreResult, { slug: string; sequence: number; dry_run: 0 }>({
  url: method('restore_version'),
  method: 'POST',
  immediate: false,
})

/** The version the confirm step is about. Kept after close, for the fade. */
const restoring = ref<PrototypeVersion | null>(null)
const confirmOpen = ref(false)
/** The version the delete step is about. Kept after close, for the fade. */
const pruning = ref<PrototypeVersion | null>(null)
const pruneOpen = ref(false)

/** Versions that are open (full prompt and file list), by version name. */
const openRows = ref<Set<string>>(new Set())

const query = ref('')
const searchRef = ref<{ inputElement: HTMLInputElement | null } | null>(null)

/** The row that holds the tab stop. Falls back to the first visible row. */
const activeName = ref<string | null>(null)
const rowEls = new Map<string, HTMLElement>()
/** The jumped-to row: lit (`flashName`), then fading out (`fadeName`). */
const flashName = ref<string | null>(null)
const fadeName = ref<string | null>(null)
let flashTimers: number[] = []

// The card holds one dialog per Prototype, so the fetch waits for the open.
// Nothing loads while the gallery only renders the cards.
watch(open, (value) => {
  if (!value) return
  openRows.value = new Set()
  query.value = ''
  activeName.value = null
  history.reload()
  usage.reload()
})

onBeforeUnmount(clearFlash)

/**
 * Escape clears a non-empty search first. The Dialog closes on a document-level
 * capture listener, so the input cannot stop it; the close is refused here.
 */
const dialogOpen = computed({
  get: () => open.value,
  set: (value: boolean) => {
    const input = searchRef.value?.inputElement
    if (!value && query.value && input && document.activeElement === input) {
      query.value = ''
      return
    }
    open.value = value
  },
})

/** True when some row has no snapshot, so the footer can say why. */
const hasLegacy = computed(() => history.data?.some((version) => !version.restorable))

const total = computed(() => history.data?.length ?? 0)
const showSearch = computed(() => total.value >= SEARCH_MIN_VERSIONS)
const needle = computed(() => query.value.trim().toLowerCase())

function matches(version: PrototypeVersion): boolean {
  if (version.prompt.toLowerCase().includes(needle.value)) return true
  return `version ${version.sequence}`.includes(needle.value) || `v${version.sequence}` === needle.value
}

const visible = computed(() => {
  const rows = history.data ?? []
  return needle.value ? rows.filter(matches) : rows
})

const sections = computed<DaySection[]>(() => {
  const result: DaySection[] = []
  for (const version of visible.value) {
    const date = versionDate(version)
    const key = dayKey(date)
    const last = result[result.length - 1]
    if (last?.key === key) last.versions.push(version)
    else result.push({ key, label: dayLabel(date), versions: [version] })
  }
  return result
})

const tabStop = computed(() => {
  const rows = visible.value
  return rows.some((row) => row.name === activeName.value) ? activeName.value : rows[0]?.name
})

/** Share of the cap the history uses, where the footer and the delete item start. */
const NEARLY_FULL = 0.8

const nearlyFull = computed(() => {
  const data = usage.data
  return !!data && data.used_bytes >= data.cap_bytes * NEARLY_FULL
})
const isFull = computed(() => !!usage.data && usage.data.used_bytes >= usage.data.cap_bytes)

const usageText = computed(() => {
  const data = usage.data
  if (!data) return ''
  if (isFull.value) return 'History is full. Delete older versions to keep saving.'
  const megabytes = 1024 * 1024
  return `History uses ${Math.round(data.used_bytes / megabytes)} of ${Math.round(data.cap_bytes / megabytes)} MB`
})

/** The newest version, whatever the search hides. */
const currentName = computed(() => history.data?.[0]?.name)

function askRestore(version: PrototypeVersion): void {
  restoring.value = version
  confirmOpen.value = true
}

function askPrune(version: PrototypeVersion): void {
  pruning.value = version
  pruneOpen.value = true
}

async function onPruned(result: PruneResult): Promise<void> {
  await Promise.all([history.reload(), usage.reload()])
  toast.success(`Deleted ${versionLabel(result.deleted)}`)
}

/**
 * The version Undo puts back: the row under a Current restore, which is the
 * tree as it stood right before that restore (a pending change was committed
 * as its own version first). None when row 0 is not a restore, or when the
 * row under it is a legacy row with no snapshot.
 */
const undoTarget = computed(() => {
  const [current, before] = history.data ?? []
  if (current?.kind !== 'restore' || !before?.restorable) return null
  return before
})

/** Show the new version and tell the card. The new row carries the Undo. */
async function onRestored(): Promise<void> {
  await history.reload()
  emit('restored')
  toast.success('Version restored')
}

async function undo(): Promise<void> {
  const target = undoTarget.value
  if (!target) return
  try {
    await undoRestore.submit({
      slug: props.prototype.slug,
      sequence: target.sequence,
      dry_run: 0,
    })
  } catch (error) {
    toast.error((error as Error).message)
    return
  }
  await history.reload()
  emit('restored')
  toast.success('Undid the restore')
}

/**
 * A prompt long enough to clamp. Only a request row can be long: a restore or
 * created row is one short line the server wrote.
 */
function isLong(version: PrototypeVersion): boolean {
  if (version.kind !== 'request') return false
  return version.prompt.split('\n').length > CLAMP_LINES || version.prompt.length > CLAMP_CHARS
}

/** Every version by sequence, for the jump from a restore row. */
const bySequence = computed(() => new Map((history.data ?? []).map((row) => [row.sequence, row])))

/** The row a restore row jumps to: the one whose sequence it restored. */
function jumpTarget(version: PrototypeVersion): PrototypeVersion | null {
  if (version.kind !== 'restore' || version.restored_from == null) return null
  return bySequence.value.get(version.restored_from) ?? null
}

/** A row opens when it has a file list or a clamped prompt to show. */
function isOpenable(version: PrototypeVersion): boolean {
  return version.kind !== 'restore' && (version.changes.length > 0 || isLong(version))
}

function isClickable(version: PrototypeVersion): boolean {
  return isOpenable(version) || jumpTarget(version) !== null
}

/** The items of a row's ... menu. Empty means the row gets no menu at all. */
function menuOptions(version: PrototypeVersion) {
  const isCurrent = version.name === currentName.value
  if (isCurrent) {
    return undoTarget.value ? [{ label: 'Undo restore', icon: 'lucide-undo-2', onClick: undo }] : []
  }
  const restore = version.restorable
    ? [{ label: 'Restore this version', icon: 'lucide-rotate-ccw', onClick: () => askRestore(version) }]
    : []
  // Only offered once the history is close to the cap: deleting is the way out.
  const remove = nearlyFull.value
    ? [
        {
          label: 'Delete this and older versions',
          icon: 'lucide-trash-2',
          onClick: () => askPrune(version),
        },
      ]
    : []
  if (!restore.length || !remove.length) return [...restore, ...remove]
  // Two groups give a separator. The group label is hidden.
  return [
    { key: 'restore', group: ' ', hideLabel: true, options: restore },
    { key: 'delete', group: ' ', hideLabel: true, options: remove },
  ]
}

// ------------------------------------------------------------------- dates

/** The server sends `YYYY-MM-DD HH:mm:ss[.ffffff]`, read as local time. */
function versionDate(version: PrototypeVersion): Date {
  return new Date(version.creation.replace(' ', 'T'))
}

function dayKey(date: Date): string {
  return `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`
}

function dayLabel(date: Date): string {
  const now = new Date()
  if (dayKey(date) === dayKey(now)) return 'Today'
  const yesterday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1)
  if (dayKey(date) === dayKey(yesterday)) return 'Yesterday'
  return date.toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    year: date.getFullYear() === now.getFullYear() ? undefined : 'numeric',
  })
}

function timeLabel(version: PrototypeVersion): string {
  return versionDate(version).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
}

function fullDate(version: PrototypeVersion): string {
  return versionDate(version).toLocaleString([], {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}

// ----------------------------------------------------------- row behaviour

function setRowEl(name: string, el: unknown): void {
  if (el instanceof HTMLElement) rowEls.set(name, el)
  else rowEls.delete(name)
}

function clearFlash(): void {
  flashTimers.forEach((timer) => window.clearTimeout(timer))
  flashTimers = []
  flashName.value = null
  fadeName.value = null
}

/** Light the row, hold it while the scroll lands, then fade it out. */
function flash(name: string): void {
  clearFlash()
  flashName.value = name
  flashTimers.push(
    window.setTimeout(() => {
      flashName.value = null
      fadeName.value = name
    }, FLASH_HOLD_MS),
    window.setTimeout(() => {
      fadeName.value = null
    }, FLASH_HOLD_MS + FLASH_FADE_MS),
  )
}

async function jumpTo(target: PrototypeVersion): Promise<void> {
  if (!visible.value.includes(target)) {
    query.value = ''
    await nextTick()
  }
  const el = rowEls.get(target.name)
  if (!el) return
  activeName.value = target.name
  el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  el.focus({ preventScroll: true })
  flash(target.name)
}

function activate(version: PrototypeVersion): void {
  activeName.value = version.name
  const target = jumpTarget(version)
  if (target) {
    jumpTo(target)
    return
  }
  if (!isOpenable(version)) return
  const next = new Set(openRows.value)
  if (!next.delete(version.name)) next.add(version.name)
  openRows.value = next
}

function focusRow(name: string | undefined): void {
  if (!name) return
  activeName.value = name
  rowEls.get(name)?.focus()
}

function onRowKeydown(event: KeyboardEvent, version: PrototypeVersion): void {
  // Keys on the row's own menu button belong to the button.
  if (event.target !== event.currentTarget) return
  const rows = visible.value
  const index = rows.findIndex((row) => row.name === version.name)
  const moves: Record<string, () => void> = {
    ArrowDown: () => focusRow(rows[Math.min(index + 1, rows.length - 1)]?.name),
    ArrowUp: () => focusRow(rows[Math.max(index - 1, 0)]?.name),
    Home: () => focusRow(rows[0]?.name),
    End: () => focusRow(rows[rows.length - 1]?.name),
    Enter: () => activate(version),
    ' ': () => activate(version),
  }
  const move = moves[event.key]
  if (!move) return
  event.preventDefault()
  move()
}

function versionLabel(count: number): string {
  return `${count} ${count === 1 ? 'version' : 'versions'}`
}

function fileLabel(count: number): string {
  return `${count} ${count === 1 ? 'file' : 'files'}`
}
</script>

<template>
  <Dialog v-model:open="dialogOpen" size="xl">
    <!-- Same classes as the Dialog's own title, with the count beside it. -->
    <template #title>
      <h3 class="text-2xl-semibold leading-6 text-ink-gray-8">
        History
        <span v-if="total" class="text-base text-ink-gray-5">
          {{ needle ? `${visible.length} of ${total}` : versionLabel(total) }}
        </span>
      </h3>
    </template>

    <template #default>
      <TextInput
        v-if="showSearch"
        ref="searchRef"
        v-model="query"
        class="mb-3"
        type="text"
        size="sm"
        placeholder="Search prompts"
        aria-label="Search prompts"
        @keydown.down.prevent="focusRow(visible[0]?.name)"
      >
        <template #prefix>
          <span class="lucide-search size-4 text-ink-gray-5" aria-hidden="true" />
        </template>
      </TextInput>

      <!--
        `-mx-3 px-3` gives the rows' hover surface room to bleed past the text.
        The scroll box clips on x, so without it the surface would end flush
        with the text.
      -->
      <div class="-mx-3 h-96 overflow-y-auto px-3" :class="{ '!h-80': showSearch }">
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

        <p
          v-else-if="!visible.length"
          class="flex h-full items-center justify-center px-6 text-center text-p-sm text-ink-gray-5"
        >
          No versions match &ldquo;{{ query.trim() }}&rdquo;
        </p>

        <!--
          One section per day. The header sticks to the top of the scroll box on
          the dialog's own background, so the day stays in view. Each section has
          its own list, so the `first:` and `+li` divider rules work per day.

          The divider is a `before:` hairline, not `border-t`: a top border on
          a rounded row bends up into the corners. Inset by the row padding so
          it spans the text, and hidden above and below a hovered or focused row
          so the rounded surface never meets a line.
        -->
        <template v-else>
        <section v-for="(section, sectionIndex) in sections" :key="section.key" class="-mx-3">
          <h4
            class="sticky top-0 z-10 bg-surface-elevation-1 px-3 pb-1 text-sm text-ink-gray-5"
            :class="sectionIndex === 0 ? 'pt-0' : 'pt-3'"
          >
            {{ section.label }}
          </h4>
          <ul>
            <li
              v-for="version in section.versions"
              :key="version.name"
              :ref="(el) => setRowEl(version.name, el)"
              :tabindex="version.name === tabStop ? 0 : -1"
              :aria-expanded="isOpenable(version) ? openRows.has(version.name) : undefined"
              class="group relative scroll-mt-8 rounded-6 px-3 py-2.5 before:absolute before:inset-x-3 before:top-0 before:border-t before:border-outline-gray-1 first:before:hidden hover:bg-surface-gray-2 hover:before:hidden focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-outline-gray-3 focus-visible:before:hidden [&:focus-visible+li]:before:hidden [&:hover+li]:before:hidden"
              :class="[
                isClickable(version) && 'cursor-pointer',
                flashName === version.name && '!bg-surface-gray-3',
                fadeName === version.name && 'transition-colors duration-[1200ms]',
              ]"
              @click="activate(version)"
              @focus="activeName = version.name"
              @keydown="onRowKeydown($event, version)"
            >
              <!--
                Hidden until the row is hovered or focused, and held visible
                while its menu is open (reka stamps `data-state="open"` on the
                trigger). Line 1 reserves `pr-8` so the prompt never runs under
                it. Only the active row's button is a tab stop.
              -->
              <div
                v-if="menuOptions(version).length"
                class="absolute right-2 top-2 opacity-0 group-focus-visible:opacity-100 has-[:focus-visible]:opacity-100 group-hover:opacity-100 has-[[data-state=open]]:opacity-100"
                @click.stop
              >
                <Dropdown align="end" :options="menuOptions(version)">
                  <Button
                    aria-label="Version actions"
                    icon="lucide-ellipsis"
                    size="sm"
                    variant="ghost"
                    :tabindex="version.name === tabStop ? 0 : -1"
                  />
                </Dropdown>
              </div>

              <div class="pr-8">
                <!-- A restore row names the version it went back to. Clicking it jumps there. -->
                <p
                  v-if="version.kind === 'restore'"
                  class="flex items-center gap-2 text-p-base text-ink-gray-8"
                >
                  <span class="lucide-undo-2 size-4 shrink-0 text-ink-gray-5" aria-hidden="true" />
                  <span class="min-w-0 truncate">Restored v{{ version.restored_from }}</span>
                </p>

                <p
                  v-else-if="version.kind === 'created'"
                  class="flex items-start gap-2 text-p-base text-ink-gray-7"
                >
                  <span
                    class="lucide-sparkles mt-0.5 size-4 shrink-0 text-ink-gray-5"
                    aria-hidden="true"
                  />
                  <span class="min-w-0">{{ version.prompt }}</span>
                </p>

                <p
                  v-else
                  class="whitespace-pre-line text-p-base text-ink-gray-8"
                  :class="{ 'line-clamp-2': isLong(version) && !openRows.has(version.name) }"
                >
                  {{ version.prompt }}
                </p>
              </div>

              <p class="mt-0.5 flex flex-wrap items-center gap-x-1.5 text-sm text-ink-gray-5">
                <span>v{{ version.sequence }}</span>
                <span aria-hidden="true">&middot;</span>
                <template v-if="version.name === currentName">
                  <span class="font-medium text-ink-gray-7">Current</span>
                  <span aria-hidden="true">&middot;</span>
                </template>
                <span :title="fullDate(version)">{{ timeLabel(version) }}</span>
                <template v-if="version.kind === 'request' && version.source === 'App'">
                  <span aria-hidden="true">&middot;</span>
                  <span>from the app</span>
                </template>
                <template v-if="version.kind === 'restore' && version.source === 'Agent'">
                  <span aria-hidden="true">&middot;</span>
                  <span>by agent</span>
                </template>
                <template v-if="version.changes.length">
                  <span aria-hidden="true">&middot;</span>
                  <span class="inline-flex items-center gap-0.5">
                    {{ fileLabel(version.changes.length) }}
                    <span
                      v-if="version.kind !== 'restore'"
                      class="lucide-chevron-right size-3 transition-transform"
                      :class="{ 'rotate-90': openRows.has(version.name) }"
                      aria-hidden="true"
                    />
                  </span>
                </template>
              </p>

              <PrototypeChangeList
                v-if="version.kind !== 'restore' && openRows.has(version.name)"
                class="mt-2"
                :changes="version.changes"
              />
            </li>
          </ul>
        </section>
        </template>
      </div>

      <p v-if="nearlyFull" class="mt-3 text-sm" :class="isFull ? 'text-ink-red-4' : 'text-ink-gray-5'">
        {{ usageText }}
      </p>

      <!-- Only when a row lacks a snapshot, so most dialogs never show it. -->
      <p v-if="hasLegacy" class="mt-3 text-xs text-ink-gray-5">
        Versions recorded before restore existed can't be restored.
      </p>

      <PrototypeDeleteVersionsDialog
        v-model:open="pruneOpen"
        :slug="prototype.slug"
        :version="pruning"
        @deleted="onPruned"
      />

      <!--
        Nested over this dialog. Both are reka dialogs, which stack: the later
        portal sits on top, Escape closes only the top one, and focus returns
        here when it closes.
      -->
      <PrototypeRestoreDialog
        v-model:open="confirmOpen"
        :slug="prototype.slug"
        :version="restoring"
        @restored="onRestored"
      />
    </template>
  </Dialog>
</template>
