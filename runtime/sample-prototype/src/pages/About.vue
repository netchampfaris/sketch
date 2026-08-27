<script setup lang="ts">
import { ref } from 'vue'
import { Button, FileUploader, PageHeader } from 'frappe-ui'
import { issues } from '../data'

// TypeScript in a template expression: sucrase must strip the cast (ticket 05).
const version = '1.0.0-beta.55' as string

// FileUploader is the one component that calls a server on its own. The Viewer
// stubs /api/method/upload_file, so it resolves without a backend.
const uploaded = ref('')
</script>

<template>
  <PageHeader>
    <h1 class="text-lg font-semibold text-ink-gray-9">About</h1>
  </PageHeader>

  <div class="max-w-xl space-y-4 p-5">
    <div class="rounded-4 border border-outline-gray-1 bg-surface-base p-4">
      <p class="text-base text-ink-gray-8">
        This Prototype renders through the Sketch Runtime. Nothing was built on
        a server. The browser compiled these files.
      </p>
      <dl class="mt-4 grid grid-cols-2 gap-y-2 text-sm">
        <dt class="text-ink-gray-5">Pin</dt>
        <dd class="text-ink-gray-8">{{ version }}</dd>
        <dt class="text-ink-gray-5">Issues</dt>
        <dd class="text-ink-gray-8">{{ (issues.length as number) }}</dd>
      </dl>
    </div>
    <FileUploader @success="(file) => (uploaded = file.file_name)">
      <template #default="{ openFileSelector }">
        <Button variant="subtle" @click="openFileSelector">Attach a file</Button>
      </template>
    </FileUploader>
    <p v-if="uploaded" id="uploaded" class="text-sm text-ink-green-6">
      Uploaded {{ uploaded }}
    </p>

    <p class="text-p-sm text-ink-gray-5">
      Arbitrary value check: <span class="inline-block h-[13px] w-[13px] rounded-full bg-blue-500/30" />
    </p>
  </div>
</template>
