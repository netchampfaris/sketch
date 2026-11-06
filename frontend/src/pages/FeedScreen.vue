<script setup lang="ts">
/**
 * /feed: every public Prototype on the site, newest first.
 *
 * It is the front door. `sketch/www/sketch.py` sends a signed-out visitor at
 * `/` here, so a Guest is served the bundle for the public routes and for no
 * other (`router.ts`, `meta.public`).
 *
 * No page title and no count line for a signed-in reader. The grid is the page: a heading that said
 * "Public prototypes" over a wall of public prototypes, and a line under it
 * that counted them, both said what the reader could already see.
 *
 * The one thing a Guest cannot see is what Sketch is, so a small hero stays above
 * the grid, only while there is no session: what it is, the one way in, and
 * what is new. The agent apps that work with Sketch drift around it as logos
 * (decision 86), so "your agent" has faces without a list of names in the copy.
 * Past ten public prototypes a search and an owner picker sit
 * above the grid, and the two filters combine.
 *
 * The cards come from `sketch.api.public_prototypes` and are the whole set:
 * the server sorts on a stat walk over every public tree, so a page size would
 * save nothing and would hide rows the page no longer has a line to admit to.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { Avatar, Button, Combobox, Skeleton, TextInput } from 'frappe-ui'
import AgentLogo from '../components/AgentLogo.vue'
import GithubMark from '../components/GithubMark.vue'
import FeedCard from '../components/FeedCard.vue'
import { heroApps } from '../agents'
import { openWhatsNew } from '../whatsnew'
import { continueWithProvider, publicPrototypes, sessionSettled, signedIn } from '../store'

// Served by Frappe, not bundled: the same path the top bar's mark uses.
const logo = '/assets/sketch/images/sketch-logo.svg'

const items = computed(() => publicPrototypes.data ?? [])

/**
 * Where each hero logo sits: mirrored left and right of the centred text, in
 * three rows that run from the Sketch tile down to the buttons, never over the
 * text. From 768px all five, near the edges, as the side space is about 100px
 * there; the middle row holds Codex on the left. Below 768px there is no side space,
 * so they sit in one still row under the buttons.
 *
 * Solid marks draw at 28px and line marks at 32px, so the two weigh the same.
 * Each drifts on its own period and phase, so they never move in step.
 */
const floating = [
  { place: 'md:grid md:left-[3%] md:top-16 lg:left-[16%]', size: 'size-8', period: '8s', phase: '0s' },
  { place: 'md:grid md:right-[3%] md:top-16 lg:right-[16%]', size: 'size-7', period: '9.5s', phase: '-3s' },
  { place: 'md:grid md:left-[3%] md:top-[132px] lg:left-[6%]', size: 'size-7', period: '7s', phase: '-5s' },
  { place: 'md:grid md:right-[3%] md:top-[200px] lg:right-[13%]', size: 'size-7', period: '6.5s', phase: '-2.5s' },
  { place: 'md:grid md:left-[3%] md:top-[200px] lg:left-[13%]', size: 'size-8', period: '8.5s', phase: '-6s' },
].map((spot, index) => ({ ...spot, app: heroApps[index] }))

/**
 * True until the first listing lands. It latches, and it is not a computed
 * over `publicPrototypes.loading`: `reload()` sets that flag back to true on
 * every call, so a computed would swap the grid for skeletons on a re-read.
 */
const settled = ref(false)
const firstLoad = computed(() => !settled.value)

/**
 * The front-door block, and when it is drawn.
 *
 * Both conditions matter. `sessionSettled` keeps it off the screen until the
 * session read has answered, so a signed-in reader never meets a Sign in
 * button that then disappears under the pointer.
 */
const showIntro = computed(() => sessionSettled.value && !signedIn.value)

/** The toolbar shows to a signed-in reader whenever there is anything public; a signed-out visitor gets the hero and the grid only. */
const query = ref('')
const owner = ref<string | null>(null)
const showFilters = computed(() => signedIn.value && items.value.length > 0)

/** Owners of what is public, most prototypes first, with how many each has. */
const owners = computed(() => {
  const byName = new Map<string, { username: string; full_name: string; user_image: string; count: number }>()
  for (const item of items.value) {
    const known = byName.get(item.username)
    if (known) known.count += 1
    else byName.set(item.username, { ...item, count: 1 })
  }
  return [...byName.values()].sort((a, b) => b.count - a.count || a.full_name.localeCompare(b.full_name))
})

const ownerOptions = computed(() => [
  { type: 'custom' as const, key: 'anyone', label: 'Anyone', onClick: () => (owner.value = null) },
  ...owners.value.map((one) => ({
    label: one.full_name,
    value: one.username,
    username: one.username,
    image: one.user_image,
    count: one.count,
  })),
])

const needle = computed(() => (showFilters.value ? query.value.trim().toLowerCase() : ''))
const who = computed(() => (showFilters.value ? owner.value : null))
const visible = computed(() =>
  items.value.filter(
    (item) =>
      (!who.value || item.username === who.value) && (!needle.value || item.title.toLowerCase().includes(needle.value)),
  ),
)

const nothingMatches = computed(() => {
  const name = owners.value.find((one) => one.username === who.value)?.full_name
  if (needle.value && name) return `No prototypes by ${name} match "${query.value.trim()}"`
  if (needle.value) return `No prototypes match "${query.value.trim()}"`
  return `No prototypes by ${name}`
})

function clearFilters(): void {
  query.value = ''
  owner.value = null
}

watch(
  () => publicPrototypes.isFinished,
  (done) => {
    if (done) settled.value = true
  },
  { immediate: true },
)

onMounted(() => {
  if (!publicPrototypes.isFinished) publicPrototypes.reload()
})
</script>

<template>
  <!--
    No PageHeader. The gallery has one because it carries a title and the New
    prototype action; this page has neither, so for a signed-in reader the grid
    starts at the same `pt-6` the gallery body uses and the top bar's rule is
    the only line above it.

    The Guest hero. Centred, short, and over the grid, so the prototypes stay
    the point of the page: at 1440x900 the first row starts in the top half.

    "Continue with GitHub" is the only way in, so it covers sign-up too and no
    helper line follows it. It goes straight to the provider when the site has
    one (`continueWithProvider`). "See what's new" opens the What's new modal,
    which a Guest may open by hand and never sees on its own. On a phone the two buttons stack, full width, in the same
    order.
  -->
  <main>
    <section v-if="showIntro" class="relative px-3 py-12 text-center sm:px-5 sm:py-16">
      <!--
        The floating logos, from 768px. Absolute, so the text block keeps its
        own centre and height. Each is a named image: it names an app the
        sentence leaves unnamed. The box is 32px for every mark and the mark
        centres in it, so a 28px one stays on its row.
      -->
      <span
        v-for="spot in floating"
        :key="spot.app.name"
        :aria-label="`Works with ${spot.app.name}`"
        class="agent-drift absolute hidden size-8 place-items-center text-ink-gray-3 dark:text-ink-gray-4"
        :class="spot.place"
        role="img"
        :style="{ animationDuration: spot.period, animationDelay: spot.phase }"
        :title="`Works with ${spot.app.name}`"
      >
        <AgentLogo :class="spot.size" :svg="spot.app.logo" />
      </span>

      <img alt="" aria-hidden="true" class="mx-auto mb-4 size-10 dark:invert" :src="logo" />
      <h1 class="text-2xl-semibold text-ink-gray-8">Design with your agent</h1>
      <p class="mx-auto mt-2 max-w-[560px] text-p-base text-ink-gray-6">
        Sketch renders frappe-ui prototypes that your own agent writes over MCP.
      </p>
      <div class="mt-5 flex flex-col justify-center gap-2 sm:flex-row">
        <Button theme="gray" variant="solid" @click="continueWithProvider">
          <template #prefix>
            <GithubMark class="size-4" />
          </template>
          Continue with GitHub
        </Button>
        <Button label="See what's new" theme="gray" variant="outline" @click="openWhatsNew" />
      </div>
      <!-- Below 768px the side space is gone: one still row under the buttons. -->
      <div class="mt-6 flex justify-center gap-4 md:hidden">
        <span
          v-for="app in heroApps"
          :key="app.name"
          :aria-label="`Works with ${app.name}`"
          class="size-5 text-ink-gray-3 dark:text-ink-gray-4"
          role="img"
          :title="`Works with ${app.name}`"
        >
          <AgentLogo class="size-full" :svg="app.logo" />
        </span>
      </div>
    </section>

    <div class="px-3 pb-10 sm:px-5" :class="showIntro ? '' : 'pt-6'">
      <!--
        The toolbar, signed in and whenever anything is public, on the left: a search by title,
        then an owner picker (avatar, name, and how many they have public), both 28px. On a phone each takes its own line.
      -->
      <div v-if="showFilters" class="mb-4 flex flex-col gap-2 sm:flex-row">
        <TextInput v-model="query" class="w-full sm:w-64" aria-label="Search prototypes" placeholder="Search prototypes">
          <template #prefix><span class="lucide-search size-4 text-ink-gray-5" aria-hidden="true" /></template>
        </TextInput>
        <Combobox
          v-model="owner"
          class="w-full sm:w-52"
          :options="ownerOptions"
          placeholder="Anyone"
          trigger="button"
        >
          <template #item-prefix="{ item }">
            <Avatar v-if="item.username" :image="item.image" :label="item.label" size="sm" />
          </template>
          <template #item-suffix="{ item }">
            <span v-if="item.count" class="text-xs tabular-nums text-ink-gray-5">{{ item.count }}</span>
          </template>
        </Combobox>
      </div>

      <!--
        The placeholder repeats the loaded card's own height and margin classes
        and replaces only the text, so the grid does not resize when the rows
        arrive. The blocks match FeedCard.vue one for one: the picture, then the
        `h-7` and `h-5` rows. Change a row here only with the matching row there.
      -->
      <div v-if="firstLoad" class="grid gap-6 md:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
        <div v-for="n in 4" :key="n">
          <Skeleton class="aspect-[16/10] w-full rounded-6" />
          <div class="mt-3 flex h-7 items-center"><Skeleton class="h-4 w-40" /></div>
          <div class="flex h-5 items-center"><Skeleton class="h-3.5 w-56" /></div>
        </div>
      </div>

      <div
        v-else-if="!items.length"
        class="flex flex-col items-center justify-center gap-3 py-16 text-center"
      >
        <span
          class="grid size-12 place-items-center rounded-full bg-surface-gray-2 text-ink-gray-5"
        >
          <span class="lucide-panels-top-left size-6" aria-hidden="true" />
        </span>
        <p class="text-base-medium text-ink-gray-8">No public prototypes yet</p>
        <p class="max-w-sm text-p-sm text-ink-gray-5">
          A prototype lands here when its owner turns on the public link.
        </p>
      </div>

      <div
        v-else-if="!visible.length"
        class="flex flex-col items-center justify-center gap-3 py-16 text-center"
      >
        <p class="text-base-medium text-ink-gray-8">{{ nothingMatches }}</p>
        <Button label="Clear search" variant="ghost" @click="clearFilters" />
      </div>

      <!--
        The same grid as the gallery: one column on a phone, two from md, three
        from lg, four from 2xl, in the shell's 1240px column.
      -->
      <div v-else class="grid gap-6 md:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
        <FeedCard
          v-for="item in visible"
          :key="`${item.username}/${item.slug}`"
          :prototype="item"
        />
      </div>
    </div>
  </main>
</template>

<style scoped>
/* A few pixels of slow drift, on each logo's own period and phase. Still under reduced motion. */
.agent-drift {
  animation: agent-drift ease-in-out infinite;
}

@keyframes agent-drift {
  0%,
  100% {
    transform: translate(0, 0);
  }
  33% {
    transform: translate(3px, -4px);
  }
  66% {
    transform: translate(-3px, 2px);
  }
}

@media (prefers-reduced-motion: reduce) {
  .agent-drift {
    animation: none;
  }
}
</style>
