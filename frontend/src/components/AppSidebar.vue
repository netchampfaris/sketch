<script setup lang="ts">
/**
 * The persistent 14rem sidebar (spec 11).
 *
 * Identity, navigation, the agent-connection status, then the signed-in User
 * and the theme control in the footer. Every row has a fixed height, so
 * nothing moves while the session loads.
 */
import { computed } from 'vue'
import {
  Avatar,
  ScrollArea,
  Sidebar,
  SidebarHeader,
  SidebarItem,
  SidebarSection,
} from 'frappe-ui'
import ThemeControl from './ThemeControl.vue'
import { session } from '../store'

const connected = computed(() => Boolean(session.data?.has_token))
const fullName = computed(() => session.data?.full_name ?? '')
const username = computed(() => session.data?.username ?? '')
</script>

<template>
  <Sidebar width="14rem" class="border-r border-outline-gray-1">
    <SidebarHeader title="Sketch" subtitle="Prototypes" />

    <ScrollArea class="min-h-0 flex-1" viewport-class="px-2 pt-0.5 pb-10">
      <SidebarSection>
        <SidebarItem to="/" icon="lucide-panels-top-left" label="Prototypes" />
        <SidebarItem to="/settings" icon="lucide-settings-2" label="Settings" />
      </SidebarSection>
    </ScrollArea>

    <div class="shrink-0 px-2 pb-2">
      <div class="flex h-7 items-center gap-2 px-2">
        <span
          class="size-1.5 shrink-0 rounded-full"
          :class="connected ? 'bg-surface-green-7' : 'bg-surface-gray-5'"
          aria-hidden="true"
        />
        <span class="truncate text-sm text-ink-gray-5">
          {{ connected ? 'Agent token ready' : 'No agent token yet' }}
        </span>
      </div>

      <div class="mt-1 flex h-10 items-center gap-2 rounded-4 px-2">
        <Avatar :label="fullName" :image="session.data?.user_image" size="md" />
        <div class="min-w-0 flex-1">
          <div class="truncate text-sm text-ink-gray-8">{{ fullName }}</div>
          <div class="truncate text-xs text-ink-gray-5">
            {{ username ? '@' + username : '' }}
          </div>
        </div>
      </div>

      <ThemeControl />
    </div>
  </Sidebar>
</template>
