<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { FrappeUIProvider, useColorScheme } from 'frappe-ui'
import AppTopBar from './components/AppTopBar.vue'
import { goToLogin, prototypes, session, sessionSettled } from './store'

// Restores the saved preference and writes localStorage["theme"], which the
// Viewer reads to theme the iframe (spec 12).
useColorScheme()

const router = useRouter()

/**
 * One session read at boot, and what a failed one means.
 *
 * `get_session` throws for a Guest, and on a public route that is the ordinary
 * answer, not an error: /feed and /about render with no session
 * (`router.ts`, `meta.public`). Every other route needs one, so the browser
 * leaves for /login and comes back to the path it asked for.
 *
 * `router.isReady()` comes first and is not optional. Every route component is
 * a lazy import, so at `onMounted` the first navigation has not resolved yet
 * and `currentRoute` is still the router's initial location, whose `meta` is
 * empty. Reading it there sent a Guest on /feed to /login about half the time.
 *
 * The gallery is only loaded for a signed-in user. A Guest on /feed reads
 * `public_prototypes` instead, which the feed screen owns.
 */
onMounted(async () => {
  await router.isReady()
  await session.reload()
  sessionSettled.value = true
  if (session.error) {
    if (!router.currentRoute.value.meta.public) goToLogin()
    return
  }
  prototypes.reload()
})
</script>

<template>
  <FrappeUIProvider>
    <!--
      No DesktopShell and no sidebar. Two screens and one action did not need a
      nav column, so the shell is one sticky bar over one scroll region.

      This div owns the only overflow, and the bar scrolls inside it as a
      sticky element. Both then measure the same content width, so a scrollbar
      shifts the bar and the page column by the same amount. It is also the
      element PageHeaderBase's `getScrollParent` finds, so a header click
      scrolls the page to the top.
    -->
    <!--
      `text-ink-gray-8` is the page default and it is set once, here. TOKENS.md
      > Hierarchy keeps gray-9 for the strongest values on a screen, unread row
      titles and KPI figures. Sketch draws neither, so gray-9 as the page
      default left nothing above the body copy.
    -->
    <div class="h-full w-full overflow-y-auto bg-surface-base text-ink-gray-8">
      <AppTopBar />
      <!--
        The centred column. With no sidebar the content would otherwise run the
        full width of a wide monitor. 940px is the reading-page width in
        DESIGN.md > Geometry.

        No horizontal padding here: PageHeader and every page body already
        apply the `px-3 sm:px-5` gutter, so a second one would double it.
      -->
      <div class="mx-auto w-full max-w-[940px]">
        <router-view />
      </div>
    </div>
  </FrappeUIProvider>
</template>
