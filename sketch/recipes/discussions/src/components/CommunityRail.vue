<script setup lang="ts">
import { RouterLink } from 'vue-router'
import { Avatar, Dropdown, Rail, RailItem } from 'frappe-ui'
import { activeCommunity, communities, showSettings } from '../data'

const userMenu = [
  { label: 'My profile', icon: 'lucide-user' },
  {
    label: 'Settings',
    icon: 'lucide-settings',
    onClick: () => (showSettings.value = true),
  },
  { label: 'Log out', icon: 'lucide-log-out' },
]
</script>

<template>
  <Rail class="border-r">
    <!-- Home is a bespoke link, not a RailItem: the workspace mark fills the
         whole cell and carries no tooltip of its own. -->
    <RouterLink
      to="/"
      class="flex size-7 items-center justify-center rounded-[7px] transition hover:opacity-90 focus-visible:ring-0 focus-visible:focus-ring"
      aria-label="Home"
    >
      <Avatar label="Frappe" shape="square" size="lg" class="size-7" />
    </RouterLink>

    <div class="flex w-full flex-1 flex-col items-center gap-3 pt-3">
      <RailItem
        v-for="c in communities"
        :key="c.id"
        :label="c.name"
        :active="activeCommunity === c.id"
        :badge="c.unread"
        badge-style="count"
        @click="activeCommunity = c.id"
      >
        <Avatar
          :image="c.image"
          :label="c.name"
          size="lg"
          shape="square"
          class="size-7"
        />
      </RailItem>
    </div>

    <!-- Bottom cluster: the extra gap keeps the utility items and the account
         avatar from crowding each other at the foot of the rail. -->
    <div class="flex flex-col items-center gap-2.5">
      <RailItem label="Search" variant="ghost" icon="lucide-search" to="/search" />
      <RailItem
        label="Settings"
        variant="ghost"
        icon="lucide-settings"
        @click="showSettings = true"
      />

      <!-- User menu: a Dropdown whose trigger is the avatar cell at the foot
           of the rail. -->
      <Dropdown :options="userMenu">
        <template #trigger="{ open }">
          <button
            type="button"
            class="flex size-7 items-center justify-center rounded-full transition focus-visible:ring-0 focus-visible:focus-ring"
            :class="open ? '' : 'hover:opacity-90'"
            aria-label="Account"
          >
            <Avatar
              image="https://avatars.githubusercontent.com/u/499550?v=4"
              label="Evan You"
              size="lg"
              class="size-7"
            />
          </button>
        </template>
      </Dropdown>
    </div>
  </Rail>
</template>
