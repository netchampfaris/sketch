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
import { labels, mailboxes, unreadCount } from './data'
</script>

<template>
  <div class="h-screen w-full bg-surface-base text-ink-gray-9">
    <!-- `:scroll="false"` lets the two panes own their own scroll. -->
    <DesktopShell :scroll="false">
      <template #sidebar>
        <Sidebar width="14rem" class="border-r">
          <SidebarHeader
            title="Northwind"
            subtitle="support@northwind.io"
            logo="https://api.dicebear.com/10.x/disco/svg?seed=Northwind"
            :menu-items="[
              { label: 'Switch mailbox', icon: 'lucide-arrow-left-right' },
              { label: 'Settings', icon: 'lucide-settings' },
              { label: 'Log out', icon: 'lucide-log-out' },
            ]"
          />

          <ScrollArea class="min-h-0 flex-1" viewport-class="px-2 pt-0.5 pb-10">
            <nav class="space-y-0.5">
              <SidebarItem>
                <template #prefix>
                  <span class="lucide-search size-4" aria-hidden="true" />
                </template>
                <span class="flex-1 truncate text-sm">Search</span>
                <template #suffix>
                  <Badge variant="ghost" label="⌘K" />
                </template>
              </SidebarItem>

              <!-- One route per mailbox. The item lights up from the route. -->
              <SidebarItem
                v-for="box in mailboxes"
                :key="box.key"
                :to="box.path"
              >
                <template #prefix>
                  <span :class="box.icon" class="size-4" aria-hidden="true" />
                </template>
                <span class="flex-1 truncate text-sm">{{ box.label }}</span>
                <template #suffix>
                  <Badge
                    v-if="unreadCount(box.key)"
                    variant="ghost"
                    :label="String(unreadCount(box.key))"
                  />
                </template>
              </SidebarItem>
            </nav>

            <div class="mt-4 flex h-7 items-center">
              <SidebarLabel>Labels</SidebarLabel>
            </div>
            <nav class="mt-0.5 space-y-0.5">
              <SidebarItem
                v-for="tag in labels"
                :key="tag.key"
                :to="tag.path"
              >
                <template #prefix>
                  <span
                    class="lucide-tag size-4 text-ink-gray-5"
                    aria-hidden="true"
                  />
                </template>
                <span class="flex-1 truncate text-sm">{{ tag.label }}</span>
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
