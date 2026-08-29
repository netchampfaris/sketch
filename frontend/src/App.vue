<script setup lang="ts">
import { onMounted } from 'vue'
import { FrappeUIProvider, useColorScheme } from 'frappe-ui'
import AppTopBar from './components/AppTopBar.vue'
import { goToLogin, prototypes, session } from './store'

// Restores the saved preference and writes localStorage["theme"], which the
// Viewer reads to theme the iframe (spec 12).
useColorScheme()

onMounted(async () => {
  await session.reload()
  if (session.error) {
    goToLogin()
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
    <div class="h-full w-full overflow-y-auto bg-surface-base text-ink-gray-9">
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
