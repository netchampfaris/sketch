<script setup lang="ts">
import {
  Avatar,
  Button,
  SettingsBody,
  SettingsHeader,
  SettingsPanel,
} from 'frappe-ui'
import { List, ListCell, ListRow } from 'frappe-ui/list'
import { managedCommunities } from '../../data'
</script>

<template>
  <SettingsPanel value="communities">
    <SettingsHeader title="Communities">
      <template #actions>
        <Button icon-left="lucide-plus">New community</Button>
      </template>
    </SettingsHeader>
    <SettingsBody>
      <List class="-mx-3 pt-4" :row-height="56">
        <ListRow v-for="community in managedCommunities" :key="community.name">
          <ListCell>
            <Avatar
              :image="community.image"
              :label="community.name"
              size="xl"
              shape="square"
            />
          </ListCell>
          <ListCell>
            <div class="min-w-0">
              <div class="truncate text-base text-ink-gray-8">
                {{ community.name }}
              </div>
              <div class="mt-0.5 truncate text-sm text-ink-gray-5">
                {{ community.spaces }} spaces · {{ community.members }} members
              </div>
            </div>
          </ListCell>
          <ListCell class="justify-end">
            <Button
              variant="ghost"
              icon="lucide-ellipsis"
              label="Community options"
            />
          </ListCell>
        </ListRow>
      </List>
    </SettingsBody>
  </SettingsPanel>
</template>
