<script setup lang="ts">
/**
 * Prototypes: the Prototype gallery (spec 11, decisions 69 to 72).
 *
 * No visible title (decision 79): one toolbar row, then one grid of cards,
 * newest update first: the user's own and the ones shared with them.
 * Shared is what somebody invited them to, plus what they only commented on.
 * Tabs "All · Mine · Shared" show only while there is something shared, and a
 * search sits beside them once the tab holds more than ten.
 *
 * With nothing in it at all, the gallery is the setup (decision 87): a new
 * user connects their agent here, and once it connects, the same space offers
 * starter requests and watches for the first card.
 *
 * The screen also polls, because this is the screen a new user watches while
 * the agent writes its first Prototype. See the polling block below.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Button, Skeleton, TabButtons, TextInput, Tooltip, useCall } from 'frappe-ui'
import AgentConnect from '../components/AgentConnect.vue'
import AgentStatus from '../components/AgentStatus.vue'
import NewPrototypeDialog from '../components/NewPrototypeDialog.vue'
import PrototypeCard from '../components/PrototypeCard.vue'
import SharedCard from '../components/SharedCard.vue'
import StarterRequests from '../components/StarterRequests.vue'
import { connected } from '../agents'
import { usePoll } from '../poll'
import { conversationPrototypes, method, prototypes, sharedPrototypes } from '../store'
import type { Prototype, SharedPrototype } from '../types'

const showPicker = ref(false)

const items = computed(() => prototypes.data ?? [])

/**
 * Prototypes somebody invited this user to, then the ones this user commented on or was mentioned in and neither
 * owns nor edits. A prototype in both reads once, as the invitation.
 */
const shared = computed(() => {
  const invited = sharedPrototypes.data ?? []
  const named = new Set(invited.map((row) => row.name))
  const talked = (conversationPrototypes.data ?? []).filter((row) => !named.has(row.name))
  return [
    ...invited.map((row) => ({ row, conversation: false })),
    ...talked.map((row) => ({ row, conversation: true })),
  ]
})

type Tab = 'all' | 'mine' | 'shared'

const route = useRoute()
const router = useRouter()

/** The tab is in the address (`?tab=mine`, `?tab=shared`; All is no parameter), so a reload and a link keep it. */
const requested = computed<Tab>(() => {
  const tab = route.query.tab
  return tab === 'mine' || tab === 'shared' ? tab : 'all'
})

/** There is no Shared tab to land on while nothing is shared, so a stale `?tab=shared` reads as All. */
const tab = computed<Tab>(() => (requested.value === 'shared' && !shared.value.length ? 'all' : requested.value))

const tabModel = computed<Tab>({
  get: () => tab.value,
  set: (value) => {
    const { tab: _drop, ...rest } = route.query
    router.replace({ query: value === 'all' ? rest : { ...rest, tab: value } })
  },
})

const showTabs = computed(() => shared.value.length > 0)

const counts = computed<Record<Tab, number>>(() => ({
  all: items.value.length + shared.value.length,
  mine: items.value.length,
  shared: shared.value.length,
}))

const tabs: { value: Tab; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'mine', label: 'Mine' },
  { value: 'shared', label: 'Shared' },
]

/** The cards of the tab, newest update first across both kinds. `modified` is the tree's own stamp. */
const tabItems = computed(() => {
  const mine = items.value.map((row) => ({ row, shared: false, conversation: false }))
  const others = shared.value.map((one) => ({ row: one.row, shared: true, conversation: one.conversation }))
  const rows = tab.value === 'mine' ? mine : tab.value === 'shared' ? others : [...mine, ...others]
  return rows.sort((a, b) => (b.row.modified ?? '').localeCompare(a.row.modified ?? ''))
})

/** The search appears once the tab holds more than ten, and filters by title. */
const SEARCH_ABOVE = 10
const query = ref('')
const showSearch = computed(() => tabItems.value.length > SEARCH_ABOVE)
const needle = computed(() => (showSearch.value ? query.value.trim() : ''))
const visible = computed(() =>
  needle.value
    ? tabItems.value.filter((one) => one.row.title.toLowerCase().includes(needle.value.toLowerCase()))
    : tabItems.value,
)

/**
 * The empty state's title. A user with prototypes shared to them but none of their own sees it on Mine only, so the
 * sentence is about them and not about the product.
 */
const emptyTitle = computed(() =>
  tab.value === 'mine' && shared.value.length ? 'No prototypes of your own yet' : 'No prototypes yet',
)

/**
 * True until the first list lands. It latches, and it is not a computed over
 * `prototypes.loading`.
 *
 * `reload()` is `useFetch.execute`, which sets `isFetching` back to true and
 * `isFinished` back to false on every call (frappe-ui
 * data-fetching/useCall/useCall.ts, `reload: execute`). A computed over those
 * flags would swap the loaded grid for skeleton cards on every poll and on
 * every card action.
 */
const settled = ref(false)
const firstLoad = computed(() => !settled.value || !sharedSettled.value)

/**
 * The first answer of all three lists, not only the owned one: the tabs and the grid's first row both depend on what
 * is shared, so waiting for it keeps the page from growing a tab row under the pointer.
 */
const sharedSettled = ref(false)
watch(
  () => [sharedPrototypes.isFinished, conversationPrototypes.isFinished],
  ([invited, talked]) => {
    if (invited && talked) sharedSettled.value = true
  },
  { immediate: true },
)

/**
 * Nothing owned and nothing shared: the gallery turns into the setup.
 *
 * `connected` reads the boot session until the setup block has read the
 * token, then the token's own replies (`agents.ts`). The session read never
 * mints a token; only the setup block, drawn here, does.
 */
const setup = computed(() => !items.value.length && !shared.value.length)

/** True once the setup gave way to a first card, so that grid fades in. */
const arrived = ref(false)
watch(setup, (now, before) => {
  arrived.value = before && !now && !firstLoad.value
})

/**
 * The empty Mine tab of a user who only has shared prototypes. Sketch has no
 * editor, so an empty gallery is normal, not an error.
 */
const emptyBody = computed(() =>
  connected.value
    ? 'Sketch has no editor. Your own agent writes the prototypes over MCP.'
    : 'Sketch has no editor. Connect an agent first, then ask it to build something.',
)

// ------------------------------------------------------------------ polling
// A Prototype the agent has just written must appear here without a reload
// (finding 2.1). This is the moment the user is watching to learn whether the
// connection worked, and a screen that says nothing happened reads as a
// failure.
//
// Four seconds, not the Viewer's two (`runtime/viewer/boot.js`, POLL_MS): the
// Viewer's poller answers from a stat walk over one tree, while
// `list_prototypes` loads every Prototype the user owns and counts the files
// in each (`sketch/api.py`, `_row`).
//
// One request per list each tick, plus one more only when that list moved. The
// loop used to reload `session` on every tick too, so an unconnected user, who
// is exactly the user that leaves this screen open, paid two requests every
// four seconds. `connected` is read once at boot instead (`App.vue`,
// `session.reload()`). It only picks the empty state's sentence, and the
// arrival the user is waiting for replaces that whole empty state with the
// grid.
//
// The backoff and the visibility rule live in `poll.ts`.
const POLL_MS = 4000

/**
 * A list's poll: its own reader, and the list it last committed.
 *
 * The reader hits the same endpoint as the store's list and writes a separate
 * copy of the answer, which the poll then compares. It cannot be the store's
 * `reload()`: that commits the answer before anyone can look at it, and
 * `reload()` is `useFetch.execute`, so every poll would also flip `isFetching`
 * and `isFinished` under the whole screen.
 *
 * It cannot be `call()` either. `call` is POST-only and unwraps
 * `response.message`, while `/api/v2/method/...` answers `{"data": ...}`
 * (frappe-ui utils/frappeRequest.ts, `transformResponse`), so it would read
 * `undefined` on every poll.
 *
 * `signature` is the list the store currently holds, serialised. The poll
 * compares against it and writes nothing when it matches.
 *
 * The Viewer compares one revision string (`sketch.api.prototype_revision`).
 * There is no list-wide equivalent, so the payload is the revision: it
 * carries `modified`, `is_public` and the file count for every row, which is
 * everything a card draws.
 *
 * The comparison is what keeps the grid still. `prototypes.data` is a
 * computed over the fetch response, so committing an identical payload still
 * hands every PrototypeCard a fresh prop object, which recomputes its menu
 * options and rebuilds an open Dropdown under the pointer.
 *
 * Only the store's own data writes it, so the baseline is always something
 * the user has seen. Seeding it from the first poll instead would swallow any
 * write made between mount and that poll: the new row would arrive, become
 * the baseline, and never be committed.
 *
 * The check answers `false` when the read failed and `null` when the screen
 * went while it was out. `reload()` resolves rather than rejects on a failed
 * request (@vueuse/core `useFetch.execute`, called with `throwOnFailed`
 * unset), so the error ref is the only signal that the answer is not real.
 */
function useChangeProbe<T>(list: { data: T[] | undefined | null; reload: () => Promise<unknown> }, name: string) {
  const probe = useCall<T[]>({ url: method(name), immediate: false })
  let signature = ''
  watch(
    () => list.data,
    (rows) => {
      signature = JSON.stringify(rows ?? [])
    },
    { immediate: true },
  )
  return async (alive: () => boolean): Promise<boolean | null> => {
    const rows = await probe.reload()
    // The screen may have gone while the request was out. Commit nothing to a
    // store the next screen also reads.
    if (!alive()) return null
    if (probe.error || !rows) return false
    // The second request costs one extra list only when something actually
    // moved, and it keeps the store the single writer of the list.
    if (JSON.stringify(rows) !== signature) await list.reload()
    return true
  }
}

// Owned prototypes; an invitation arrives the same way, and so does a reply or a mention.
const checks = [
  useChangeProbe<Prototype>(prototypes, 'list_prototypes'),
  useChangeProbe<SharedPrototype>(sharedPrototypes, 'shared_prototypes'),
  useChangeProbe<SharedPrototype>(conversationPrototypes, 'conversations'),
]

watch(
  () => prototypes.isFinished,
  (done) => {
    if (done) settled.value = true
  },
  { immediate: true },
)

// The gallery never retires its poll: a Prototype can arrive at any moment,
// including long after the first one. `poll.ts` owns the timer, the backoff
// and the visibility rule.
usePoll(
  async (alive) => {
    // Every list is read on every tick. A failed read leaves that list as it
    // is, because the rows on screen are the last good answer, and reports
    // false (silent, like the Viewer's poller) so the poll backs off.
    let ok = true
    for (const check of checks) {
      const read = await check(alive)
      if (read === null) return
      ok &&= read
    }
    return ok
  },
  { interval: POLL_MS },
)

onMounted(() => {
  if (!prototypes.isFinished) prototypes.reload()
  sharedPrototypes.reload()
  conversationPrototypes.reload()
})
</script>

<template>
  <!-- No visible title: the top bar's "My prototypes" already names the page. Screen readers still get one. -->
  <h1 class="sr-only">Prototypes</h1>

  <div class="px-3 pb-10 pt-6 sm:px-5">
    <!--
      One toolbar: the tabs on the left; the search (once the tab holds more than ten) and "New prototype" on the right
      edge. All 28px, so the row is one height whatever is in it. With nothing shared there are no tabs and the right
      group keeps the right edge.

      "New prototype" is the one action on this screen (DESIGN.md principle 3) and it is here in every state, the empty
      one too: hiding it while the list was empty left a user with no way to make one (finding 4.5), so the empty state
      below never repeats it. It waits for the first list only so the row does not offer an action over skeleton cards.

      Inert until an agent connects: a Prototype made before that is a page nothing can write to. `aria-disabled`, not
      `disabled`, so the button keeps its tab stop and its touch target, and the tooltip saying why still opens.
    -->
    <div v-if="!firstLoad" class="mb-4 flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
      <TabButtons v-if="showTabs" v-model="tabModel" :options="tabs" size="sm">
        <template #suffix="{ button }">
          <span class="ml-1 tabular-nums text-ink-gray-5">{{ counts[button.value as Tab] }}</span>
        </template>
      </TabButtons>
      <div class="ml-auto flex min-w-0 items-center gap-2">
        <TextInput
          v-if="showSearch"
          v-model="query"
          class="w-40 sm:w-64"
          aria-label="Search prototypes"
          placeholder="Search prototypes"
        >
          <template #prefix><span class="lucide-search size-4 text-ink-gray-5" aria-hidden="true" /></template>
        </TextInput>
        <Tooltip :disabled="connected" text="Connect your agent first">
          <Button
            :aria-disabled="!connected || undefined"
            :class="{ 'cursor-default !bg-surface-gray-2 !text-ink-gray-4 hover:!bg-surface-gray-2 active:!bg-surface-gray-2': !connected }"
            icon-left="lucide-plus"
            label="New prototype"
            theme="gray"
            variant="subtle"
            @click="showPicker = connected"
          />
        </Tooltip>
      </div>
    </div>

    <!--
      Every placeholder repeats the loaded card's own height and margin classes
      and replaces only the text, so the grid does not resize when the rows
      arrive (finding 4.2). The blocks match PrototypeCard.vue one for one:
      the picture, then the `h-7` and `h-5` rows.

      Those heights are load-bearing, not decoration. The card was four rows
      once, and this block kept its four after the card became two, so the
      placeholder measured 124px below the picture against the card's 68px and
      the whole grid rose 56px a row when the list landed. Change a row here
      only with the matching rows in `PrototypeCard.vue` and `SharedCard.vue`.
    -->
    <!--
      The first card fades in over the setup it replaces. Only that arrival:
      `arrived` is false on every other change, so loading, tabs and search
      swap their content at once, as before.
    -->
    <Transition
      enter-active-class="transition-opacity duration-200 ease-out"
      enter-from-class="opacity-0"
      :css="arrived"
      @after-enter="arrived = false"
    >
      <div v-if="firstLoad" class="grid gap-6 md:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
        <div v-for="n in 3" :key="n">
          <Skeleton class="aspect-[16/10] w-full rounded-6" />
          <div class="mt-3 flex h-7 items-center"><Skeleton class="h-4 w-40" /></div>
          <div class="flex h-5 items-center"><Skeleton class="h-3.5 w-28" /></div>
        </div>
      </div>

      <!-- First use: nothing exists and no agent has connected. The setup is the page. -->
      <div v-else-if="setup && !connected" class="mx-auto max-w-[620px] py-6 sm:py-12">
        <h2 class="text-xl-semibold text-ink-gray-8">Connect your agent</h2>
        <p class="mt-2 text-p-base text-ink-gray-6">
          Sketch has no editor. Your AI agent builds the prototypes, and they show up here.
        </p>
        <AgentConnect class="mt-6" />
      </div>

      <!--
        Connected, nothing built yet: what to ask for, and the gallery watching
        for the answer. The same frame as first use, with the status as the
        heading's line, so the page changes its words, not its shape.
      -->
      <div v-else-if="setup" class="mx-auto max-w-[620px] py-6 sm:py-12">
        <h2 class="text-xl-semibold text-ink-gray-8">Ask for your first prototype</h2>
        <AgentStatus class="mt-1" />
        <StarterRequests class="mt-6" />
      </div>

      <div
        v-else-if="!tabItems.length"
        class="flex flex-col items-center justify-center gap-3 py-16 text-center"
      >
        <span
          class="grid size-12 place-items-center rounded-full bg-surface-gray-2 text-ink-gray-5"
        >
          <span class="lucide-panels-top-left size-6" aria-hidden="true" />
        </span>
        <p class="text-base-medium text-ink-gray-8">{{ emptyTitle }}</p>
        <p class="max-w-sm text-p-sm text-ink-gray-5">{{ emptyBody }}</p>
      </div>

      <div
        v-else-if="!visible.length"
        class="flex flex-col items-center justify-center gap-3 py-16 text-center"
      >
        <p class="text-base-medium text-ink-gray-8">No prototypes match "{{ needle }}"</p>
        <Button label="Clear search" variant="ghost" @click="query = ''" />
      </div>

      <!--
        One column on a phone, two from md, three from lg, four from 2xl. The
        shell's column is 1240px (App.vue), and the top bar is as wide, so the
        mark and the title stay on one line. A card scales a 1280px iframe's
        picture to its own width, and three across at 1240px is still 390px, the
        smallest the picture stays readable at.
      -->
      <div v-else class="grid gap-6 md:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
        <template v-for="one in visible" :key="one.row.name">
          <SharedCard v-if="one.shared" :prototype="one.row" :conversation="one.conversation" />
          <PrototypeCard
            v-else
            :prototype="one.row"
            @changed="prototypes.reload()"
            @removed="prototypes.reload()"
          />
        </template>
      </div>
    </Transition>
  </div>

  <NewPrototypeDialog v-model:open="showPicker" @created="prototypes.reload()" />
</template>
