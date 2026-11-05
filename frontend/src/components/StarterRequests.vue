<script setup lang="ts">
/**
 * What to ask for first, on an empty gallery whose agent already connected
 * (decision 87). Three requests the user can copy into their agent, then a
 * live line that says the gallery is watching: the gallery's own poll brings
 * the first card in and this whole block gives way to it.
 */
import { Button, Tooltip, toast } from 'frappe-ui'
import { List, ListCell, ListRow } from 'frappe-ui/list'
import { copyText } from '../store'

const starters = [
  { text: 'Build a leave request form for an HR app' },
  { text: 'Make a CRM deals list with filters and a detail panel' },
  { text: 'Turn this screenshot into a prototype', hint: 'attach a screenshot in your agent' },
]

/** `copyText` shows its own error toast and rethrows (store.ts). */
async function copy(text: string): Promise<void> {
  try {
    await copyText(text)
  } catch {
    return
  }
  toast.success('Copied')
}
</script>

<template>
  <div>
    <p class="text-p-sm text-ink-gray-7">Ask your agent something like:</p>
    <List class="mt-2" :columns="['minmax(0,1fr)', '2rem']" divider="full">
      <ListRow v-for="one in starters" :key="one.text" :value="one.text">
        <ListCell>
          <div class="min-w-0 py-2">
            <p class="text-p-base text-ink-gray-8">{{ one.text }}</p>
            <p v-if="one.hint" class="mt-0.5 text-p-sm text-ink-gray-5">{{ one.hint }}</p>
          </div>
        </ListCell>
        <ListCell class="justify-end">
          <Tooltip text="Copy">
            <Button
              icon="lucide-copy"
              :label="`Copy “${one.text}”`"
              theme="gray"
              variant="ghost"
              @click="copy(one.text)"
            />
          </Tooltip>
        </ListCell>
      </ListRow>
    </List>

    <p class="mt-6 flex items-center gap-2 text-p-sm text-ink-gray-5">
      <span aria-hidden="true" class="size-2 shrink-0 animate-pulse rounded-full bg-surface-gray-5 motion-reduce:animate-none" />
      Watching for your first prototype…
    </p>
  </div>
</template>
