<script setup lang="ts">
import {
  Select,
  SettingsBody,
  SettingsHeader,
  SettingsPanel,
  SettingsRow,
  Switch,
} from 'frappe-ui'
import { digestDay, digestFrequency, emailDigestEnabled } from '../../data'
</script>

<template>
  <SettingsPanel value="notifications">
    <SettingsHeader title="Notifications" />
    <SettingsBody>
      <div class="space-y-11 pt-6">
        <section>
          <div class="divide-y divide-outline-gray-1">
            <SettingsRow
              title="Enable email digests"
              description="Send a summary of missed activity"
            >
              <Switch v-model="emailDigestEnabled" />
            </SettingsRow>
            <SettingsRow
              v-if="emailDigestEnabled"
              title="Digest frequency"
              description="Choose how often you receive your digest"
            >
              <Select
                v-model="digestFrequency"
                :options="['Weekly', 'Fortnightly', 'Monthly']"
              />
            </SettingsRow>
            <SettingsRow
              v-if="emailDigestEnabled"
              title="Send on"
              description="Choose the weekday for your digest"
            >
              <Select
                v-model="digestDay"
                :options="['Monday', 'Wednesday', 'Friday']"
              />
            </SettingsRow>
            <SettingsRow
              title="Last sent"
              description="The most recent digest sent to you"
            >
              <div class="text-base text-ink-gray-6">28 Jun 2026</div>
            </SettingsRow>
          </div>
        </section>
      </div>
    </SettingsBody>
  </SettingsPanel>
</template>
