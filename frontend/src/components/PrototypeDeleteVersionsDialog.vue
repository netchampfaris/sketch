<script setup lang="ts">
/**
 * The confirm step before old versions are deleted.
 *
 * Deleting a version also deletes the files only it kept, which is how the
 * history gets smaller. The dialog runs a dry run on open, so it can say how
 * many versions go and how much space comes back. Confirm sends the same call
 * with `dry_run: 0`. The caller reloads the list and the usage.
 */
import { ref, watch } from 'vue'
import { Button, Dialog, ErrorMessage, LoadingText, useCall } from 'frappe-ui'
import { errorText, method } from '../store'
import type { PrototypeVersion, PruneResult } from '../types'

interface PruneParams {
  slug: string
  sequence: number
  dry_run: 0 | 1
}

const props = defineProps<{ slug: string; version: PrototypeVersion | null }>()
const open = defineModel<boolean>('open', { required: true })
const emit = defineEmits<{ deleted: [result: PruneResult] }>()

const dryRun = useCall<PruneResult, PruneParams>({
  url: method('delete_versions'),
  method: 'POST',
  immediate: false,
})

const prune = useCall<PruneResult, PruneParams>({
  url: method('delete_versions'),
  method: 'POST',
  immediate: false,
})

const preview = ref<PruneResult | null>(null)
const failure = ref('')

watch(open, (value) => {
  if (value) loadPreview()
})

async function loadPreview(): Promise<void> {
  const target = props.version
  preview.value = null
  failure.value = ''
  if (!target) return

  try {
    const result = await dryRun.submit({ slug: props.slug, sequence: target.sequence, dry_run: 1 })
    if (props.version === target) preview.value = result
  } catch (error) {
    failure.value = errorText(error)
  }
}

async function confirm(): Promise<void> {
  if (!props.version) return
  failure.value = ''

  try {
    const result = await prune.submit({
      slug: props.slug,
      sequence: props.version.sequence,
      dry_run: 0,
    })
    open.value = false
    if (result) emit('deleted', result)
  } catch (error) {
    failure.value = errorText(error)
  }
}

/** KB below one megabyte, else MB with one decimal. */
function sizeLabel(bytes: number): string {
  const megabytes = bytes / (1024 * 1024)
  if (megabytes < 1) return `${Math.max(1, Math.round(bytes / 1024))}\u00a0KB`
  return `${megabytes.toFixed(1)}\u00a0MB`
}

function versionLabel(count: number): string {
  return `${count} ${count === 1 ? 'version' : 'versions'}`
}
</script>

<template>
  <Dialog v-model:open="open" size="md" title="Delete older versions?">
    <template #default>
      <div class="min-h-12">
        <LoadingText v-if="dryRun.loading" />

        <ErrorMessage v-else-if="failure" :message="failure" />

        <p v-else-if="preview" class="text-p-base text-ink-gray-7">
          Deletes {{ versionLabel(preview.deleted) }}, from this one back to the first. Frees
          {{ sizeLabel(preview.freed_bytes) }}. This can't be undone.
        </p>
      </div>
    </template>

    <template #actions="{ close }">
      <div class="flex justify-end gap-2">
        <Button :disabled="prune.loading" label="Cancel" variant="subtle" @click="close" />
        <Button
          :disabled="!preview"
          :loading="prune.loading"
          :label="preview ? `Delete ${versionLabel(preview.deleted)}` : 'Delete'"
          theme="red"
          variant="solid"
          @click="confirm"
        />
      </div>
    </template>
  </Dialog>
</template>
