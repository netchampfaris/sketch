<script setup lang="ts">
import { ref } from 'vue'
import { RouterView } from 'vue-router'
import {
  Badge,
  DesktopShell,
  ScrollArea,
  Sidebar,
  SidebarCollapseToggle,
  SidebarHeader,
  SidebarItem,
  SidebarLabel,
} from 'frappe-ui'
import { nav } from './data'

// Deals is the routed screen: the board and the list are its two routes. The
// other nav items have no screen upstream, so they keep the upstream click
// state.
const activeNav = ref('Deals')
</script>

<template>
  <div class="h-screen w-full bg-surface-base text-ink-gray-9">
    <DesktopShell :scroll="false">
      <template #sidebar>
        <Sidebar width="14rem" class="border-r">
          <SidebarHeader
            title="Deals"
            subtitle="brightloom.frappe.cloud"
            logo="https://api.dicebear.com/10.x/disco/svg?seed=Brightloom"
            :menu-items="[
              { label: 'Switch team', icon: 'lucide-arrow-left-right' },
              { label: 'Log out', icon: 'lucide-log-out' },
            ]"
          />

          <ScrollArea class="min-h-0 flex-1" viewport-class="px-2 pt-0.5 pb-10">
            <nav class="space-y-0.5">
              <SidebarItem
                v-for="item in nav"
                :key="item.label"
                :to="item.label === 'Deals' ? '/' : undefined"
                :active="activeNav === item.label"
                @click="activeNav = item.label"
              >
                <template #prefix>
                  <span :class="item.icon" class="size-4" aria-hidden="true" />
                </template>
                <span class="flex-1 truncate text-sm">{{ item.label }}</span>
                <template #suffix>
                  <Badge
                    v-if="item.count"
                    variant="ghost"
                    :label="String(item.count)"
                  />
                </template>
              </SidebarItem>
            </nav>

            <div class="mt-4 flex h-7 items-center">
              <SidebarLabel>Pinned views</SidebarLabel>
            </div>
            <nav class="mt-0.5 space-y-0.5">
              <SidebarItem>
                <template #prefix>
                  <span class="lucide-star size-4" aria-hidden="true" />
                </template>
                <span class="flex-1 truncate text-sm">My open deals</span>
              </SidebarItem>
              <SidebarItem>
                <template #prefix>
                  <span class="lucide-star size-4" aria-hidden="true" />
                </template>
                <span class="flex-1 truncate text-sm">Closing this month</span>
              </SidebarItem>
            </nav>
          </ScrollArea>

          <div class="mt-auto px-2 pb-2">
            <SidebarCollapseToggle />
          </div>
        </Sidebar>
      </template>

      <RouterView />
    </DesktopShell>
  </div>
</template>
