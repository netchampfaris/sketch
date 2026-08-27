<script setup lang="ts">
import { Button, SettingsBody, SettingsHeader, SettingsPanel } from 'frappe-ui'
import { customEmojis } from '../../data'
</script>

<template>
  <SettingsPanel value="emojis">
    <SettingsHeader
      title="Emojis"
      description="Custom emojis are available to everyone in reactions"
    >
      <template #actions>
        <Button icon-left="lucide-plus">Add emoji</Button>
      </template>
    </SettingsHeader>
    <SettingsBody>
      <div class="flex flex-wrap gap-2 pt-6">
        <div
          v-for="emoji in customEmojis"
          :key="emoji"
          class="grid size-10 place-content-center rounded-6 border text-xl"
        >
          {{ emoji }}
        </div>
      </div>
    </SettingsBody>
  </SettingsPanel>
</template>
