<script setup lang="ts">
import { onMounted } from 'vue'
import { FrappeUIProvider, useColorScheme } from 'frappe-ui'
import AppSidebar from './components/AppSidebar.vue'
import { DesktopShell } from 'frappe-ui'
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
    <div class="h-full w-full bg-surface-base text-ink-gray-9">
      <DesktopShell>
        <template #sidebar>
          <AppSidebar />
        </template>
        <router-view />
      </DesktopShell>
    </div>
  </FrappeUIProvider>
</template>
