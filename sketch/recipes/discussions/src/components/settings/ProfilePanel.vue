<script setup lang="ts">
import {
  Avatar,
  Button,
  SettingsBody,
  SettingsHeader,
  SettingsPanel,
  SettingsRow,
  Textarea,
  TextInput,
} from 'frappe-ui'
import { bio, firstName, fullName, lastName, userImage } from '../../data'
</script>

<template>
  <SettingsPanel value="profile">
    <SettingsHeader title="Profile" />
    <SettingsBody>
      <div class="space-y-11 pt-6">
        <section class="space-y-6">
          <div class="flex items-center gap-4">
            <Avatar :image="userImage" :label="fullName" class="size-16" />
            <div>
              <div class="text-base-medium text-ink-gray-8">Profile picture</div>
              <p class="text-p-sm text-ink-gray-5">Helps people recognise you</p>
            </div>
          </div>

          <div class="grid gap-6 sm:grid-cols-2">
            <TextInput v-model="firstName" label="First name" class="w-full" />
            <TextInput v-model="lastName" label="Last name" class="w-full" />
          </div>

          <Textarea v-model="bio" label="Bio" class="w-full" maxlength="280" />
        </section>

        <section>
          <h2 class="text-lg-semibold text-ink-gray-8">Account</h2>
          <div class="mt-2 divide-y divide-outline-gray-1">
            <SettingsRow
              title="Public profile"
              description="View your public page or customize its card layout"
            >
              <div class="flex gap-2">
                <Button icon-left="lucide-user">View</Button>
                <Button icon-left="lucide-layout-dashboard">Customize</Button>
              </div>
            </SettingsRow>
            <SettingsRow
              title="Password"
              description="Manage password and account access"
            >
              <Button>Update Password</Button>
            </SettingsRow>
          </div>
        </section>
      </div>
    </SettingsBody>
  </SettingsPanel>
</template>
