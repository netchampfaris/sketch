<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { toast } from 'frappe-ui'
import MailHeader from '../components/MailHeader.vue'
import ThreadList from '../components/ThreadList.vue'
import ThreadView from '../components/ThreadView.vue'
import { mailTabs, threadsFor, viewLabel } from '../data'

// One screen for every mailbox and every label. The route hands the view key
// in, so the sidebar highlight and the pane content stay in step.
const props = defineProps<{ view: string }>()

// Gmail-style tabs belong to the Inbox. Other views hold too little to split.
const isInbox = computed(() => props.view === 'inbox')
const activeTab = ref('Primary')

const threads = computed(() => {
  const rows = threadsFor(props.view)
  return isInbox.value
    ? rows.filter((thread) => thread.category === activeTab.value)
    : rows
})

// The open thread, bound to the list's `v-model:active`. Row values are
// strings, so this is the string id.
const activeId = ref('')
watch(
  threads,
  (rows) => {
    if (rows.some((thread) => String(thread.id) === activeId.value)) return
    activeId.value = rows.length ? String(rows[0].id) : ''
  },
  { immediate: true },
)

const selected = computed(
  () => threads.value.find((thread) => String(thread.id) === activeId.value) ?? null,
)

// The reading-pane subject reads as a reply once a thread has more than one
// message.
const readingSubject = computed(() => {
  if (!selected.value) return viewLabel(props.view)
  return selected.value.messages.length > 1
    ? `Re: ${selected.value.subject}`
    : selected.value.subject
})

const emptyCopy = computed(() => {
  if (props.view === 'drafts')
    return { title: 'No drafts', message: 'A message you save shows up here.' }
  if (isInbox.value)
    return {
      title: `Nothing in ${activeTab.value}`,
      message: 'New mail in this category lands here.',
    }
  return {
    title: `Nothing in ${viewLabel(props.view)}`,
    message: 'Mail you move here shows up in this list.',
  }
})

// The list pane collapses from the reading toolbar, like most mail apps.
const showList = ref(true)
</script>

<template>
  <MailHeader
    :title="viewLabel(view)"
    :subject="readingSubject"
    :show-list="showList"
    :has-thread="Boolean(selected)"
    @toggle-list="showList = !showList"
    @compose="toast.info('Compose is not wired up in this prototype')"
  />

  <!-- The panes carry no headers of their own: each owns its scroll. App.vue
       passes `:scroll="false"` to DesktopShell, so this row fills the height
       below the header and each pane's ScrollArea is the real scroller. -->
  <div class="flex min-h-0 flex-1">
    <ThreadList
      v-show="showList"
      v-model:active="activeId"
      v-model:tab="activeTab"
      :threads="threads"
      :tabs="isInbox ? mailTabs : null"
      :empty-title="emptyCopy.title"
      :empty-message="emptyCopy.message"
    />
    <ThreadView :thread="selected" />
  </div>
</template>
