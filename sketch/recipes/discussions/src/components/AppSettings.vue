<script setup lang="ts">
import {
  Avatar,
  SettingsContent,
  SettingsDialog,
  SettingsNavGroup,
  SettingsNavItem,
  SettingsSidebar,
} from 'frappe-ui'
import CommunitiesPanel from './settings/CommunitiesPanel.vue'
import EmojisPanel from './settings/EmojisPanel.vue'
import NotificationsPanel from './settings/NotificationsPanel.vue'
import PreferencesPanel from './settings/PreferencesPanel.vue'
import ProfilePanel from './settings/ProfilePanel.vue'
import UsersPanel from './settings/UsersPanel.vue'
import { fullName, settingsTab, showSettings, userImage } from '../data'
</script>

<template>
  <SettingsDialog v-model:open="showSettings" v-model:tab="settingsTab" size="5xl">
    <SettingsSidebar>
      <SettingsNavGroup label="User settings">
        <SettingsNavItem value="profile">
          <template #prefix>
            <Avatar
              size="xs"
              :image="userImage"
              :label="fullName"
              class="shrink-0"
            />
          </template>
          Profile
        </SettingsNavItem>
        <SettingsNavItem value="preferences">
          <template #prefix>
            <span
              class="lucide-sliders-horizontal size-4 shrink-0 text-ink-gray-6"
            />
          </template>
          Preferences
        </SettingsNavItem>
        <SettingsNavItem value="notifications">
          <template #prefix>
            <span class="lucide-bell size-4 shrink-0 text-ink-gray-6" />
          </template>
          Notifications
        </SettingsNavItem>
      </SettingsNavGroup>
      <SettingsNavGroup label="App settings">
        <SettingsNavItem value="communities">
          <template #prefix>
            <span class="lucide-building-2 size-4 shrink-0 text-ink-gray-6" />
          </template>
          Communities
        </SettingsNavItem>
        <SettingsNavItem value="emojis">
          <template #prefix>
            <span class="lucide-smile-plus size-4 shrink-0 text-ink-gray-6" />
          </template>
          Emojis
        </SettingsNavItem>
      </SettingsNavGroup>
      <SettingsNavGroup label="Administration">
        <SettingsNavItem value="users">
          <template #prefix>
            <span class="lucide-users size-4 shrink-0 text-ink-gray-6" />
          </template>
          Users
        </SettingsNavItem>
      </SettingsNavGroup>
    </SettingsSidebar>

    <SettingsContent>
      <ProfilePanel />
      <PreferencesPanel />
      <NotificationsPanel />
      <CommunitiesPanel />
      <EmojisPanel />
      <UsersPanel />
    </SettingsContent>
  </SettingsDialog>
</template>
