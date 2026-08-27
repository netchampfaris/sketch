<script setup lang="ts">
import { RouterView } from 'vue-router'
import {
  DesktopShell,
  Progress,
  ScrollArea,
  Sidebar,
  SidebarHeader,
  SidebarItem,
} from 'frappe-ui'
import { navItems } from './data'
</script>

<template>
  <div class="h-screen w-full bg-surface-base text-ink-gray-9">
    <DesktopShell>
      <template #sidebar>
        <Sidebar width="14rem" class="border-r">
          <SidebarHeader
            title="Files"
            subtitle="kestrel.frappe.cloud"
            logo="https://api.dicebear.com/10.x/disco/svg?seed=Kestrel"
            :menu-items="[
              { label: 'Switch team', icon: 'lucide-arrow-left-right' },
              { label: 'Log out', icon: 'lucide-log-out' },
            ]"
          />

          <ScrollArea class="min-h-0 flex-1" viewport-class="px-2 pt-0.5 pb-10">
            <nav class="space-y-0.5">
              <!-- One route per nav entry. The item lights up from the route. -->
              <SidebarItem
                v-for="item in navItems"
                :key="item.key"
                :to="item.path"
              >
                <template #prefix>
                  <span :class="item.icon" class="size-4" aria-hidden="true" />
                </template>
                <span class="flex-1 truncate text-sm">{{ item.label }}</span>
              </SidebarItem>
            </nav>
          </ScrollArea>

          <div class="mt-auto px-4 pb-4">
            <Progress :value="42" size="sm" label="Storage" hint />
            <div class="mt-1.5 text-xs text-ink-gray-5">4.2 GB of 10 GB used</div>
          </div>
        </Sidebar>
      </template>

      <RouterView />
    </DesktopShell>
  </div>
</template>
