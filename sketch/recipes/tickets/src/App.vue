<script setup lang="ts">
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
import { nav, views } from './data'

// The upstream sidebar tracked an `activeNav` ref. Every item is a route now,
// so SidebarItem reads the active state off the current path.
</script>

<template>
  <div class="h-screen w-full bg-surface-base text-ink-gray-9">
    <DesktopShell>
      <template #sidebar>
        <Sidebar width="14rem" class="border-r">
          <SidebarHeader
            title="Tickets"
            subtitle="helpdesk.fernwood.io"
            logo="https://api.dicebear.com/10.x/disco/svg?seed=Fernwood"
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
                :to="item.to"
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
              <SidebarLabel>Views</SidebarLabel>
            </div>
            <nav class="mt-0.5 space-y-0.5">
              <SidebarItem
                v-for="view in views"
                :key="view.label"
                :to="view.to"
              >
                <template #prefix>
                  <span class="lucide-list-filter size-4" aria-hidden="true" />
                </template>
                <span class="flex-1 truncate text-sm">{{ view.label }}</span>
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
