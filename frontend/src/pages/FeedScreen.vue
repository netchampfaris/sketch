<script setup lang="ts">
/**
 * /feed: every public Prototype on the site, newest first.
 *
 * It is the front door. `sketch/www/sketch.py` sends a signed-out visitor at
 * `/` here, so a Guest is served the bundle for this route and for /about, and
 * for no other (`router.ts`, `meta.public`).
 *
 * No page title and no count line. The grid is the page: a heading that said
 * "Public prototypes" over a wall of public prototypes, and a line under it
 * that counted them, both said what the reader could already see.
 *
 * The one thing a Guest cannot see is what Sketch is, so that sentence and the
 * way in stay, above the grid and only while there is no session.
 *
 * The cards come from `sketch.api.public_prototypes` and are the whole set:
 * the server sorts on a stat walk over every public tree, so a page size would
 * save nothing and would hide rows the page no longer has a line to admit to.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { Button, Skeleton } from 'frappe-ui'
import FeedCard from '../components/FeedCard.vue'
import { goToLogin, publicPrototypes, sessionSettled, signedIn } from '../store'

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
    prototype action; this page has neither, so the grid starts at the same
    `pt-6` the gallery body uses and the top bar's rule is the only line above
    it.
  -->
  <div class="px-3 pb-10 pt-6 sm:px-5">
    <!--
      Problem 8.1, in one sentence. The root used to answer a signed-out
      visitor with a login form for a product they had never read a line
      about. `sketch/www/login.html` prints this same sentence, word for word,
      so a visitor reads one description of Sketch and not two versions of it.

      `max-w-[640px]` is the reading measure the web pages use. The grid below
      takes the full 940px column, because a two-column grid of 16:10 pictures
      inside a reading measure draws cards a third the width of the gallery's.
    -->
    <section v-if="showIntro" class="max-w-[640px] pb-8">
      <p class="text-p-base text-ink-gray-7">
        Sketch renders frappe-ui prototypes that your own agent writes over MCP.
      </p>
      <Button
        class="mt-4"
        icon-left="lucide-log-in"
        label="Sign in"
        theme="gray"
        variant="subtle"
        @click="goToLogin"
      />
      <p class="mt-2 text-p-xs text-ink-gray-5">
        Sketch signs you in with GitHub. The same button makes your account.
      </p>
    </section>

    <!--
      The placeholder repeats the loaded card's own height and margin classes
      and replaces only the text, so the grid does not resize when the rows
      arrive. The blocks match FeedCard.vue one for one: the picture, then the
      two `h-7` rows. Change a row here only with the matching row there.
    -->
    <div v-if="firstLoad" class="grid gap-6 md:grid-cols-2">
      <div v-for="n in 4" :key="n">
        <Skeleton class="aspect-[16/10] w-full rounded-6" />
        <div class="mt-3 flex h-7 items-center"><Skeleton class="h-4 w-40" /></div>
        <div class="flex h-7 items-center"><Skeleton class="h-3.5 w-56" /></div>
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

    <!--
      Two columns, never three. The shell centres the page in a 940px column,
      so a third column only makes each card narrower and the picture inside
      it unreadable.
    -->
    <div v-else class="grid gap-6 md:grid-cols-2">
      <FeedCard
        v-for="item in items"
        :key="`${item.username}/${item.slug}`"
        :prototype="item"
      />
    </div>
  </div>
</template>
