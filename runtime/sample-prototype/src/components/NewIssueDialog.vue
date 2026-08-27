<script setup lang="ts">
import { ref } from 'vue'
import { Dialog, FormControl } from 'frappe-ui'
import { addIssue, type Status } from '../data'

const open = defineModel<boolean>('open', { required: true })

const title = ref('')
const owner = ref('Faris')
const status = ref<Status>('open')
const error = ref('')

const statusOptions = [
  { label: 'Open', value: 'open' },
  { label: 'In progress', value: 'in-progress' },
  { label: 'Done', value: 'done' },
]

function submit({ close }: { close: () => void }) {
  if (!title.value.trim()) {
    error.value = 'A title is required'
    return
  }
  addIssue(title.value.trim(), status.value, owner.value)
  title.value = ''
  error.value = ''
  close()
}
</script>

<template>
  <Dialog
    v-model:open="open"
    title="New issue"
    :actions="[
      { label: 'Create', variant: 'solid', theme: 'gray', onClick: submit },
    ]"
  >
    <div class="space-y-4">
      <FormControl
        v-model="title"
        label="Title"
        placeholder="What is broken?"
        required
        :error="error"
      />
      <FormControl
        v-model="status"
        type="select"
        label="Status"
        :options="statusOptions"
      />
      <FormControl v-model="owner" label="Assignee" />
    </div>
  </Dialog>
</template>
