<script setup lang="ts">
import { RouterView } from 'vue-router'
import { DesktopShell } from 'frappe-ui'
import AppSettings from './components/AppSettings.vue'
import CommunityRail from './components/CommunityRail.vue'
import SpaceSidebar from './components/SpaceSidebar.vue'
</script>

<template>
  <div class="h-screen w-full bg-surface-base text-ink-gray-9">
    <DesktopShell>
      <template #rail>
        <CommunityRail />
      </template>
      <template #sidebar>
        <SpaceSidebar />
      </template>
      <RouterView />
    </DesktopShell>

    <!-- The rail and the sidebar menu both open this one dialog. -->
    <AppSettings />
  </div>
</template>
