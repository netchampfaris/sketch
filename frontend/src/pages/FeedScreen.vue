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
 * what is new. Past ten public prototypes a search and an owner picker sit
 * above the grid, and the two filters combine.
 *
 * The cards come from `sketch.api.public_prototypes` and are the whole set:
 * the server sorts on a stat walk over every public tree, so a page size would
 * save nothing and would hide rows the page no longer has a line to admit to.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { Avatar, Button, Combobox, Skeleton, TextInput } from 'frappe-ui'
import FeedCard from '../components/FeedCard.vue'
import { openWhatsNew } from '../whatsnew'
import { continueWithProvider, publicPrototypes, sessionSettled, signedIn } from '../store'

// Served by Frappe, not bundled: the same path the top bar's mark uses.
const logo = '/assets/sketch/images/sketch-logo.svg'

const items = computed(() => publicPrototypes.data ?? [])

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

/** The toolbar shows whenever there is anything public to look through. */
const query = ref('')
const owner = ref<string | null>(null)
const showFilters = computed(() => items.value.length > 0)

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
  <section v-if="showIntro" class="px-3 py-12 text-center sm:px-5 sm:py-16">
    <img alt="" aria-hidden="true" class="mx-auto mb-4 size-10 dark:invert" :src="logo" />
    <h1 class="text-2xl-semibold text-ink-gray-8">Design with your agent</h1>
    <p class="mx-auto mt-2 max-w-[560px] text-p-base text-ink-gray-6">
      Sketch renders frappe-ui prototypes that your own agent writes over MCP.
    </p>
    <div class="mt-5 flex flex-col justify-center gap-2 sm:flex-row">
      <Button size="md" theme="gray" variant="solid" @click="continueWithProvider">
        <template #prefix>
          <svg aria-hidden="true" class="size-4" fill="currentColor" viewBox="0 0 16 16">
            <path
              d="M8 0c4.42 0 8 3.58 8 8a8.013 8.013 0 0 1-5.45 7.59c-.4.08-.55-.17-.55-.38 0-.27.01-1.13.01-2.2 0-.75-.25-1.23-.54-1.48 1.78-.2 3.65-.88 3.65-3.95 0-.88-.31-1.59-.82-2.15.08-.2.36-1.02-.08-2.12 0 0-.67-.22-2.2.82-.64-.18-1.32-.27-2-.27-.68 0-1.36.09-2 .27-1.53-1.03-2.2-.82-2.2-.82-.44 1.1-.16 1.92-.08 2.12-.51.56-.82 1.28-.82 2.15 0 3.06 1.86 3.75 3.64 3.95-.23.2-.44.55-.51 1.07-.46.21-1.61.55-2.33-.66-.15-.24-.6-.83-1.23-.82-.67.01-.27.38.01.53.34.19.73.9.82 1.13.16.45.68 1.31 2.69.94 0 .67.01 1.3.01 1.49 0 .21-.15.45-.55.38A7.995 7.995 0 0 1 0 8c0-4.42 3.58-8 8-8Z"
            />
          </svg>
        </template>
        Continue with GitHub
      </Button>
      <Button label="See what's new" size="md" theme="gray" variant="outline" @click="openWhatsNew" />
    </div>
  </section>

  <div class="px-3 pb-10 sm:px-5" :class="showIntro ? '' : 'pt-6'">
    <!--
      The toolbar, whenever anything is public, on the left: a search by title,
      then an owner picker (avatar and name), both 28px. On a phone each takes its own line.
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
</template>
