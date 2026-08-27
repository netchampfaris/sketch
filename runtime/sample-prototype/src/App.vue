<script setup lang="ts">
import {
  DesktopShell,
  Sidebar,
  SidebarHeader,
  SidebarItem,
  SidebarLabel,
  SidebarSection,
} from 'frappe-ui'
</script>

<template>
  <div class="h-screen w-full bg-surface-base text-ink-gray-9">
    <DesktopShell>
      <template #sidebar>
        <Sidebar width="14rem" class="border-r">
          <SidebarHeader title="Sketch" subtitle="Prototype" />
          <div class="min-h-0 flex-1 overflow-y-auto px-2 pt-0.5 pb-10">
            <SidebarSection>
              <SidebarItem to="/" icon="lucide-circle-dot" label="Issues" />
              <SidebarItem to="/about" icon="lucide-info" label="About" />
            </SidebarSection>
            <SidebarLabel divider>Filters</SidebarLabel>
            <SidebarSection>
              <SidebarItem icon="lucide-user" label="Assigned to me" suffix="2" />
              <SidebarItem icon="lucide-archive" label="Archived" suffix="0" />
            </SidebarSection>
          </div>
        </Sidebar>
      </template>
      <router-view />
    </DesktopShell>
  </div>
</template>
