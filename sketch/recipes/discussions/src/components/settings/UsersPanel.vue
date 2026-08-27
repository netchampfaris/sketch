<script setup lang="ts">
import {
  Avatar,
  Button,
  SettingsBody,
  SettingsHeader,
  SettingsPanel,
} from 'frappe-ui'
import {
  List,
  ListCell,
  ListHeader,
  ListHeaderCell,
  ListRow,
  ListRows,
} from 'frappe-ui/list'
import { members } from '../../data'
</script>

<template>
  <SettingsPanel value="users">
    <SettingsHeader title="Users">
      <template #actions>
        <Button icon-left="lucide-user-plus">Invite</Button>
      </template>
    </SettingsHeader>
    <SettingsBody>
      <List
        class="-mx-3 pt-4"
        :columns="['minmax(0,1fr)', '6rem', '3rem']"
        :row-height="56"
      >
        <ListHeader>
          <ListHeaderCell>Member</ListHeaderCell>
          <ListHeaderCell>Role</ListHeaderCell>
          <ListHeaderCell />
        </ListHeader>
        <ListRows :items="members" v-slot="{ item: member }">
          <ListRow>
            <ListCell>
              <Avatar :image="member.image" :label="member.name" size="xl" />
              <div class="ml-3 min-w-0">
                <div class="truncate text-base text-ink-gray-8">
                  {{ member.name }}
                </div>
                <div class="mt-0.5 truncate text-sm text-ink-gray-5">
                  {{ member.email }}
                </div>
              </div>
            </ListCell>
            <ListCell>
              <span class="text-base text-ink-gray-7">{{ member.role }}</span>
            </ListCell>
            <ListCell class="justify-end">
              <Button
                variant="ghost"
                icon="lucide-ellipsis"
                label="Member options"
              />
            </ListCell>
          </ListRow>
        </ListRows>
      </List>
    </SettingsBody>
  </SettingsPanel>
</template>
