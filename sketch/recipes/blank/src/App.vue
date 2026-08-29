<script setup lang="ts">
/**
 * The shell of a Blank Prototype: one scroll region, no rail and no sidebar.
 *
 * There is one page, so a sidebar would be a nav with one item pointing at the
 * screen the user is already on. The other recipes carry `DesktopShell`
 * because they have routes to move between.
 *
 * `text-ink-gray-8` is the page default and is set here once, so every child
 * inherits it. Gray-9 is reserved for unread titles and KPI figures, which
 * Sketch does not have (conventions.md:30). This is the first tree a new user
 * opens, so it has to model the house style.
 */
import { RouterView } from 'vue-router'
</script>

<template>
  <div class="h-screen w-full overflow-y-auto bg-surface-base text-ink-gray-8">
    <RouterView />
  </div>
</template>
