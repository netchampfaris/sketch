<script setup lang="ts">
/**
 * The confirm step before a Prototype goes back to an older version.
 *
 * A restore rewrites the whole tree, so the dialog asks first, and it says how
 * much will change. The numbers come from a dry run: the server compares the
 * version's snapshot with the tree as it is now and writes nothing. Confirm
 * then sends the same call with `dry_run: 0`.
 *
 * The restore is saved as a new version, so it can be undone. The caller owns
 * that part (the toast), because it also reloads the history list.
 */
import { computed, ref, watch } from 'vue'
import { Button, Dialog, ErrorMessage, LoadingText, toast, useCall } from 'frappe-ui'
import PrototypeChangeList from './PrototypeChangeList.vue'
import { errorText, method } from '../store'
import type { PrototypeVersion, RestorePreview, RestoreResult } from '../types'

interface RestoreParams {
  slug: string
  sequence: number
  dry_run: 0 | 1
}

const props = defineProps<{ slug: string; version: PrototypeVersion | null }>()
const open = defineModel<boolean>('open', { required: true })
const emit = defineEmits<{ restored: [result: RestoreResult] }>()

// POST for both: the server writes a version on the second, and the first
// shares the method, so one door means one CSRF rule.
const dryRun = useCall<RestorePreview, RestoreParams>({
  url: method('restore_version'),
  method: 'POST',
  immediate: false,
})

const restore = useCall<RestoreResult, RestoreParams>({
  url: method('restore_version'),
  method: 'POST',
  immediate: false,
})

const preview = ref<RestorePreview | null>(null)
const failure = ref('')
const filesOpen = ref(false)

/** Files that differ. Zero means the prototype already matches. */
const changeCount = computed(() => {
  const data = preview.value
  if (!data) return 0
  return data.files_added + data.files_modified + data.files_deleted
})

/** "3 files change: 1 added, 2 changed." Only the parts that are not zero. */
const summary = computed(() => {
  const data = preview.value
  if (!data) return ''

  const parts = [
    data.files_added && `${data.files_added} added`,
    data.files_modified && `${data.files_modified} changed`,
    data.files_deleted && `${data.files_deleted} deleted`,
  ].filter(Boolean)
  const noun = changeCount.value === 1 ? 'file changes' : 'files change'
  return `${changeCount.value} ${noun}: ${parts.join(', ')}.`
})

// The dry run waits for the open, and runs again on every open, because the
// tree may have moved since the last one.
watch(open, (value) => {
  if (value) loadPreview()
})

async function loadPreview(): Promise<void> {
  const target = props.version
  preview.value = null
  failure.value = ''
  filesOpen.value = false
  if (!target) return

  try {
    const result = await dryRun.submit({ slug: props.slug, sequence: target.sequence, dry_run: 1 })
    // A reopen for another version may have started while this one was in
    // flight. The late answer is not for the dialog on screen.
    if (props.version === target) preview.value = result
  } catch (error) {
    failure.value = errorText(error)
  }
}

async function confirm(): Promise<void> {
  if (!props.version) return
  failure.value = ''

  try {
    const result = await restore.submit({
      slug: props.slug,
      sequence: props.version.sequence,
      dry_run: 0,
    })
    open.value = false
    if (result?.recorded) emit('restored', result)
    // The tree changed between the dry run and the click, back to a match.
    else toast.info('Nothing to restore. This version matches the prototype.')
  } catch (error) {
    failure.value = errorText(error)
  }
}

/** Both toggles in the app use the same glyph pair. See the history dialog. */
function chevronFor(isOpen: boolean): string {
  return isOpen ? 'lucide-chevron-down' : 'lucide-chevron-right'
}
</script>

<template>
  <Dialog v-model:open="open" size="md" title="Restore this version?">
    <template #default>
      <div class="min-h-24 space-y-3">
        <LoadingText v-if="dryRun.loading" />

        <ErrorMessage v-else-if="failure" :message="failure" />

        <p v-else-if="preview && !changeCount" class="text-p-base text-ink-gray-7">
          This version matches the prototype as it is now. Nothing to restore.
        </p>

        <template v-else-if="preview && version">
          <p class="text-p-base text-ink-gray-7">
            The prototype goes back to how it was after this request:
          </p>
          <p
            class="line-clamp-2 whitespace-pre-line rounded-4 bg-surface-gray-2 px-3 py-2 text-p-sm text-ink-gray-7"
          >
            &ldquo;{{ version.prompt }}&rdquo;
          </p>

          <div class="space-y-2">
            <div class="flex items-center justify-between gap-2">
              <p class="text-base-medium text-ink-gray-8">{{ summary }}</p>
              <Button
                :icon-left="chevronFor(filesOpen)"
                :label="filesOpen ? 'Hide files' : 'Show files'"
                size="sm"
                variant="ghost"
                @click="filesOpen = !filesOpen"
              />
            </div>
            <PrototypeChangeList v-if="filesOpen" :changes="preview.changes" />
          </div>

          <p class="text-p-sm text-ink-gray-5">
            This is saved as a new version, so you can undo it.
          </p>
        </template>
      </div>
    </template>

    <template #actions="{ close }">
      <div class="flex justify-end gap-2">
        <Button v-if="preview && !changeCount" label="Close" variant="subtle" @click="close" />
        <template v-else>
          <Button
            :disabled="restore.loading"
            label="Cancel"
            variant="subtle"
            @click="close"
          />
          <Button
            :disabled="!preview"
            :loading="restore.loading"
            label="Restore"
            variant="solid"
            @click="confirm"
          />
        </template>
      </div>
    </template>
  </Dialog>
</template>
