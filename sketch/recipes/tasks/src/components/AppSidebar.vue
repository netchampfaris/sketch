<script setup lang="ts">
import { useRouter } from 'vue-router'
import {
  Badge,
  Button,
  ScrollArea,
  Sidebar,
  SidebarHeader,
  SidebarItem,
  SidebarLabel,
} from 'frappe-ui'
import { MY_TASKS, openCount, projects } from '../data'
import { openView, view } from '../lib/view'

const router = useRouter()

// Switching the view always returns to the list route.
function select(name: string) {
  openView(name)
  router.push('/')
}
</script>

<template>
  <Sidebar width="14rem" class="border-r">
    <SidebarHeader
      title="Halcyon Studio"
      subtitle="Workspace"
      logo="https://api.dicebear.com/10.x/disco/svg?seed=Halcyon"
      :menu-items="[
        { label: 'Invite members', icon: 'lucide-user-plus' },
        { label: 'Workspace settings', icon: 'lucide-settings-2' },
        { label: 'Log out', icon: 'lucide-log-out' },
      ]"
    />

    <ScrollArea class="min-h-0 flex-1" viewport-class="px-2 pt-0.5 pb-10">
      <nav class="space-y-0.5">
        <SidebarItem>
          <template #prefix>
            <span class="lucide-inbox size-4" aria-hidden="true" />
          </template>
          <span class="flex-1 truncate text-sm">Inbox</span>
          <template #suffix>
            <span class="mr-1 text-xs text-ink-gray-5">4</span>
          </template>
        </SidebarItem>
        <SidebarItem
          :active="view.active === MY_TASKS"
          @click="select(MY_TASKS)"
        >
          <template #prefix>
            <span class="lucide-list-todo size-4" aria-hidden="true" />
          </template>
          <span class="flex-1 truncate text-sm">My tasks</span>
        </SidebarItem>
        <SidebarItem>
          <template #prefix>
            <span class="lucide-search size-4" aria-hidden="true" />
          </template>
          <span class="flex-1 truncate text-sm">Search</span>
        </SidebarItem>
      </nav>

      <div class="mt-4 flex h-7 items-center justify-between">
        <SidebarLabel>Projects</SidebarLabel>
        <Button
          variant="ghost"
          size="sm"
          icon="lucide-plus text-ink-gray-5"
          label="New project"
        />
      </div>
      <nav class="mt-0.5 space-y-0.5">
        <SidebarItem
          v-for="project in projects"
          :key="project.name"
          :active="view.active === project.name"
          @click="select(project.name)"
        >
          <template #prefix>
            <span :class="project.icon" class="size-4" aria-hidden="true" />
          </template>
          <span class="flex-1 truncate text-sm">{{ project.name }}</span>
          <template #suffix>
            <Badge
              v-if="openCount(project.name)"
              variant="ghost"
              :label="String(openCount(project.name))"
            />
          </template>
        </SidebarItem>
      </nav>
    </ScrollArea>
  </Sidebar>
</template>
