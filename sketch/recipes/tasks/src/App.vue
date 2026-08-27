<script setup lang="ts">
import { RouterView } from 'vue-router'
import { DesktopShell } from 'frappe-ui'
import AppSidebar from './components/AppSidebar.vue'
</script>

<template>
  <div class="h-screen w-full bg-surface-base text-ink-gray-9">
    <DesktopShell>
      <template #sidebar>
        <AppSidebar />
      </template>
      <RouterView />
    </DesktopShell>
  </div>
</template>
