<script setup lang="ts">
import { RouterView } from 'vue-router'
import {
  DesktopShell,
  ScrollArea,
  Sidebar,
  SidebarHeader,
  SidebarItem,
  SidebarLabel,
} from 'frappe-ui'
import { navGroups } from './data'
</script>

<template>
  <div class="h-screen w-full bg-surface-base text-ink-gray-9">
    <DesktopShell>
      <template #sidebar>
        <Sidebar width="15rem" class="border-r">
          <SidebarHeader
            title="Everdusk Trading"
            subtitle="everdusk.frappe.cloud"
            logo="https://api.dicebear.com/10.x/disco/svg?seed=Everdusk"
            :menu-items="[
              { label: 'Switch company', icon: 'lucide-arrow-left-right' },
              { label: 'Import data', icon: 'lucide-upload' },
              { label: 'Settings', icon: 'lucide-settings-2' },
            ]"
          />

          <ScrollArea class="min-h-0 flex-1" viewport-class="px-2 pt-0.5 pb-10">
            <div v-for="group in navGroups" :key="group.label" class="mb-3">
              <div class="flex h-7 items-center">
                <SidebarLabel>{{ group.label }}</SidebarLabel>
              </div>
              <nav class="mt-0.5 space-y-0.5">
                <SidebarItem
                  v-for="item in group.items"
                  :key="item.key"
                  :to="item.to"
                >
                  <template #prefix>
                    <span :class="item.icon" class="size-4" aria-hidden="true" />
                  </template>
                  <span class="flex-1 truncate text-sm">{{ item.label }}</span>
                  <!-- Marks the items backed by a real screen, not a stub.
                       Gray per Gameplan's no-colour rule. -->
                  <template v-if="item.page" #suffix>
                    <span
                      class="mr-2 size-1.5 rounded-full bg-surface-gray-5"
                      aria-hidden="true"
                    />
                  </template>
                </SidebarItem>
              </nav>
            </div>
          </ScrollArea>
        </Sidebar>
      </template>

      <RouterView />
    </DesktopShell>
  </div>
</template>
