<script setup lang="ts">
import {
  Button,
  ScrollArea,
  Sidebar,
  SidebarHeader,
  SidebarItem,
  SidebarLabel,
} from 'frappe-ui'
import { showSettings, spaces } from '../data'

const menuItems = [
  {
    label: 'Invite people',
    icon: 'lucide-user-plus',
    onClick: () => (showSettings.value = true),
  },
  {
    label: 'Community settings',
    icon: 'lucide-settings-2',
    onClick: () => (showSettings.value = true),
  },
]
</script>

<template>
  <Sidebar width="14rem" class="border-r">
    <!-- No logo here: the left rail already shows the active community avatar,
         so a header logo would only repeat it. -->
    <SidebarHeader
      title="Design"
      subtitle="18 members"
      :show-logo="false"
      :menu-items="menuItems"
    />

    <!-- The app owns the scroll region: ScrollArea keeps the thin, auto-hiding
         overlay scrollbar. -->
    <ScrollArea class="min-h-0 flex-1" viewport-class="px-2 pt-0.5 pb-10">
      <nav class="space-y-0.5">
        <SidebarItem to="/" label="Home">
          <template #prefix>
            <span class="lucide-home size-4" aria-hidden="true" />
          </template>
        </SidebarItem>
        <SidebarItem to="/search" label="Search">
          <template #prefix>
            <span class="lucide-search size-4" aria-hidden="true" />
          </template>
        </SidebarItem>
      </nav>

      <div class="mt-4 flex h-7 items-center justify-between">
        <SidebarLabel>Spaces</SidebarLabel>
        <div class="flex items-center">
          <Button
            variant="ghost"
            size="sm"
            icon="lucide-arrow-up-down text-ink-gray-5"
            label="Sort spaces"
          />
        </div>
      </div>

      <nav class="mt-0.5 space-y-0.5">
        <SidebarItem
          v-for="space in spaces"
          :key="space.name"
          :to="`/spaces/${space.slug}`"
          :label="space.name"
        >
          <template #prefix>
            <span :class="space.icon" class="size-4" aria-hidden="true" />
          </template>
          <template #suffix>
            <span
              v-if="space.unread"
              class="mr-1 grid size-4 place-content-center text-xs text-ink-gray-5"
            >
              {{ space.unread }}
            </span>
          </template>
        </SidebarItem>
      </nav>
    </ScrollArea>
  </Sidebar>
</template>
