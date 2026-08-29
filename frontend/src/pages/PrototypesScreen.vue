<script setup lang="ts">
/**
 * Your prototypes: the Prototype gallery (spec 11).
 *
 * The header holds the count and the one primary action. The body is a
 * responsive grid of cards, each with a live preview of the Prototype.
 *
 * The screen also polls, because this is the screen a new user watches while
 * the agent writes its first Prototype. See the polling block below.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { Button, PageHeader, Skeleton, useCall } from 'frappe-ui'
import NewPrototypeDialog from '../components/NewPrototypeDialog.vue'
import PrototypeCard from '../components/PrototypeCard.vue'
import { usePoll } from '../poll'
import { method, prototypes, session } from '../store'
import type { Prototype } from '../types'

const showPicker = ref(false)

const items = computed(() => prototypes.data ?? [])
const count = computed(() => items.value.length)

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
const firstLoad = computed(() => !settled.value)

/**
 * True once an agent has called /mcp with a good token (plan v2, step 1.5).
 *
 * Read from `session`, never from `get_agent_token`: that call mints a token
 * as a side effect, and rendering a screen must never mint one. `has_token`
 * is the wrong signal for the same reason.
 */
const connected = computed(() => Boolean(session.data?.last_used))

/**
 * The empty state says the one thing a new user must do next, and only that.
 *
 * Sketch has no editor, so an empty gallery is normal, not an error. Which
 * sentence shows depends on whether an agent has ever reached /mcp: before
 * that, creating a Prototype gives the user an empty page and nothing to do
 * with it.
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
// One request a tick, plus one more only when the list actually moved. The
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
 * The poll's own reader. It hits the same endpoint as `prototypes` and writes
 * a separate copy of the answer, which the poll then compares.
 *
 * It cannot be `prototypes.reload()`: that commits the answer before anyone
 * can look at it, and `reload()` is `useFetch.execute`, so every poll would
 * also flip `isFetching` and `isFinished` under the whole screen.
 *
 * It cannot be `call()` either. `call` is POST-only and unwraps
 * `response.message`, while `/api/v2/method/...` answers `{"data": ...}`
 * (frappe-ui utils/frappeRequest.ts, `transformResponse`), so it would read
 * `undefined` on every poll.
 */
const probe = useCall<Prototype[]>({
  url: method('list_prototypes'),
  immediate: false,
})

/**
 * The list the store currently holds, serialised. The poll compares against
 * this and writes nothing when it matches.
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
 */
let signature = ''

watch(
  () => prototypes.data,
  (rows) => {
    signature = JSON.stringify(rows ?? [])
  },
  { immediate: true },
)

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
    // `reload()` resolves rather than rejects on a failed request
    // (@vueuse/core `useFetch.execute`, called with `throwOnFailed` unset), so
    // the error ref is the only signal that the answer is not real. Returning
    // false is silent, like the Viewer's poller: a failed poll leaves the
    // gallery as it is, because the rows on screen are the last good answer.
    const rows = await probe.reload()
    // The screen may have gone while the request was out. Commit nothing to a
    // store the next screen also reads.
    if (!alive()) return
    if (probe.error || !rows) return false
    // The second request costs one extra list only when something actually
    // moved, and it keeps the store the single writer of `prototypes.data`.
    if (JSON.stringify(rows) !== signature) await prototypes.reload()
    return true
  },
  { interval: POLL_MS },
)

onMounted(() => {
  if (!prototypes.isFinished) prototypes.reload()
})
</script>

<template>
  <!--
    No rule under the title. The top bar already draws one, and a second line
    12px below it read as a double border rather than as a section edge.

    `border-b-0` beats `PageHeader.vue`'s own `border-b` on source order, not
    on specificity: Tailwind emits `.border-b-0` after `.border-b`. The
    component hard-codes the border and exposes no prop, and its class lands
    on the same element as ours through `PageHeaderBase`'s `$attrs`.

    `pt-6` matches the body's own top padding below, so the title sits on the
    same rhythm as the grid. The component is `min-h-12 justify-center`, so
    padding moves the content down and the header grows with it.
  -->
  <PageHeader class="border-b-0 pt-6">
    <div class="min-w-0">
      <h1 class="truncate text-2xl-semibold text-ink-gray-8">Your prototypes</h1>
    </div>
    <!--
      One action per screen (DESIGN.md principle 3), and it lives here in
      every state. Finding 4.5 asked for one "New prototype" button, not for
      the capability to disappear: hiding this one while the list was empty
      left a user with no agent and no prototypes with no way to make one.
      The empty state below therefore never repeats this label.

      It waits for the first list only so the header does not offer an action
      over skeleton cards. The button is 28px and the `h1` line box is 28px,
      so the row height is the same whether or not the button is there.
    -->
    <Button
      v-if="!firstLoad"
      icon-left="lucide-plus"
      label="New prototype"
      theme="gray"
      variant="subtle"
      @click="showPicker = true"
    />
  </PageHeader>

  <div class="px-3 pb-10 pt-6 sm:px-5">
    <!--
      Two columns, never three. The shell centres the page in a 940px column,
      so a third column only makes each card narrower: 284px against 438px.
      The card scales a 1280px iframe to its own width, so a narrow card makes
      the preview unreadable. A wider screen changes nothing, because the
      column does not grow.
    -->
    <!--
      Every placeholder repeats the loaded card's own height and margin
      classes and replaces only the text, so the grid does not resize when the
      rows arrive. The four blocks match PrototypeCard.vue one for one:
      preview, the `h-10` title block, the `h-9` state row, the `h-7` link
      row.
    -->
    <div v-if="firstLoad" class="grid gap-6 md:grid-cols-2">
      <div v-for="n in 3" :key="n">
        <Skeleton class="aspect-[16/10] w-full rounded-6" />
        <div class="mt-3 flex h-10 flex-col gap-2">
          <Skeleton class="h-4 w-40" />
          <Skeleton class="h-3.5 w-56" />
        </div>
        <div class="mt-2 flex h-9 items-center pt-2"><Skeleton class="h-4 w-32" /></div>
        <div class="flex h-7 items-center"><Skeleton class="h-3.5 w-48" /></div>
      </div>
    </div>

    <div
      v-else-if="!count"
      class="flex flex-col items-center justify-center gap-3 py-16 text-center"
    >
      <span
        class="grid size-12 place-items-center rounded-full bg-surface-gray-2 text-ink-gray-5"
      >
        <span class="lucide-panels-top-left size-6" aria-hidden="true" />
      </span>
      <p class="text-base-medium text-ink-gray-8">No prototypes yet</p>
      <p class="max-w-sm text-p-sm text-ink-gray-5">{{ emptyBody }}</p>
      <!--
        Never "New prototype": the header already carries that, and one screen
        prints one create action (finding 4.5). This slot holds the other step
        instead, and only while it is still open. An unconnected user who
        creates a Prototype gets a page nothing can write to, so the empty
        state points at the token.

        `connected` is read once at boot and the poll no longer refreshes it,
        so this button cannot vanish under the pointer while the user reads
        the sentence above it. No button is solid: subtle is the heaviest
        weight this app uses (commit 54f7fdc).
      -->
      <Button
        v-if="!connected"
        class="mt-2"
        icon-left="lucide-plug-zap"
        label="Connect your agent"
        route="/settings"
        theme="gray"
        variant="subtle"
      />
    </div>

    <div v-else class="grid gap-6 md:grid-cols-2">
      <PrototypeCard
        v-for="item in items"
        :key="item.name"
        :prototype="item"
        @changed="prototypes.reload()"
        @removed="prototypes.reload()"
      />
    </div>
  </div>

  <NewPrototypeDialog v-model:open="showPicker" @created="prototypes.reload()" />
</template>
