<script setup lang="ts">
import { RouterView } from 'vue-router'
import { DesktopShell } from 'frappe-ui'
</script>

<template>
  <div class="h-screen w-full bg-surface-base text-ink-gray-9">
    <!-- Compose is a focused screen. The shell carries no rail and no sidebar. -->
    <DesktopShell>
      <RouterView />
    </DesktopShell>
  </div>
</template>
