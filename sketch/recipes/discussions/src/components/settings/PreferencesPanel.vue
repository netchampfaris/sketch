<script setup lang="ts">
import {
  Button,
  Select,
  SettingsBody,
  SettingsHeader,
  SettingsPanel,
  SettingsRow,
  Switch,
} from 'frappe-ui'
import {
  badgeStyle,
  cursorStyle,
  hideInactiveSpaces,
  spaceSort,
  theme,
} from '../../data'
</script>

<template>
  <SettingsPanel value="preferences">
    <SettingsHeader title="Preferences" />
    <SettingsBody>
      <div class="space-y-11 pt-6">
        <section>
          <div class="divide-y divide-outline-gray-1">
            <SettingsRow
              title="Appearance"
              description="Choose a light, dark, or system-matched interface"
            >
              <!-- Sketch owns the real theme. This control is a fixture. -->
              <Select
                v-model="theme"
                :options="[
                  { label: 'Light', value: 'light' },
                  { label: 'Dark', value: 'dark' },
                  { label: 'System Default', value: 'system' },
                ]"
              >
                <template #item-prefix="{ item }">
                  <div
                    v-if="item.value === 'system'"
                    class="flex size-3 overflow-hidden rounded-full border border-outline-gray-2"
                  >
                    <div class="w-1/2 bg-surface-gray-1" />
                    <div class="w-1/2 bg-surface-gray-9" />
                  </div>
                  <div
                    v-else
                    class="size-3 rounded-full border border-outline-gray-2"
                    :class="
                      item.value === 'light' ? 'bg-surface-gray-1' : 'bg-surface-gray-9'
                    "
                  />
                </template>
              </Select>
            </SettingsRow>
            <SettingsRow
              title="Cursor"
              description="Show the pointer on everything clickable, or only on external links"
            >
              <Select
                v-model="cursorStyle"
                :options="[
                  { label: 'Pointer', value: 'pointer' },
                  { label: 'Normal', value: 'normal' },
                ]"
              />
            </SettingsRow>
          </div>
        </section>

        <section>
          <h2 class="text-lg-semibold text-ink-gray-8">Sidebar</h2>
          <div class="mt-2 divide-y divide-outline-gray-1">
            <SettingsRow
              title="Unread badge"
              description="Show unread activity as a dot or a count"
            >
              <Select v-model="badgeStyle" :options="['Dot', 'Unread count']" />
            </SettingsRow>
            <SettingsRow
              title="Communities"
              description="Show, hide, and reorder communities in the left rail"
            >
              <Button>Customize</Button>
            </SettingsRow>
            <SettingsRow
              title="Space sorting"
              description="Choose how spaces are ordered in the current community sidebar"
            >
              <Select
                v-model="spaceSort"
                :options="['Recent activity', 'Alphabetical']"
              />
            </SettingsRow>
            <SettingsRow
              title="Inactive spaces"
              description="Hide spaces with no activity for the last 2 months"
            >
              <Switch v-model="hideInactiveSpaces" />
            </SettingsRow>
          </div>
        </section>
      </div>
    </SettingsBody>
  </SettingsPanel>
</template>
