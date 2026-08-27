<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Breadcrumbs, Button, PageHeader } from 'frappe-ui'
import FileTable from '../components/FileTable.vue'
import FilesToolbar from '../components/FilesToolbar.vue'
import {
  categoryOf,
  itemsById,
  itemsFor,
  timeBuckets,
  viewLabel,
  type FileItem,
} from '../data'

// One page serves every sidebar route. The route passes the view key as a
// static prop, so no route parameter is needed.
const props = defineProps<{ view: string }>()

const router = useRouter()

// The id of the open folder inside Home (null = root).
const currentFolderId = ref<string | null>(null)
const searchQuery = ref('')
const selectedType = ref('all')
const sortField = ref('modified')
const sortDirection = ref<'asc' | 'desc'>('asc')

// Leaving Home closes the open folder and clears the search.
watch(
  () => props.view,
  (view) => {
    if (view !== 'home') currentFolderId.value = null
    searchQuery.value = ''
  },
)

// A folder opens in Home, wherever the row was clicked.
function openFolder(folderId: string | null) {
  currentFolderId.value = folderId
  searchQuery.value = ''
  if (props.view !== 'home') router.push('/')
}

function onRowClick(item: FileItem) {
  if (item.type === 'folder') openFolder(item.id)
  // Files would open a preview here; no-op in this recipe.
}

// Home shows one crumb per ancestor. The other views show their own name.
const breadcrumbs = computed(() => {
  if (props.view !== 'home') return [{ label: viewLabel(props.view) }]
  const trail: FileItem[] = []
  let node = currentFolderId.value
    ? itemsById.get(currentFolderId.value)
    : undefined
  while (node) {
    trail.unshift(node)
    node = node.parent ? itemsById.get(node.parent) : undefined
  }
  return [
    { label: 'Home', onClick: () => openFolder(null) },
    ...trail.map((folder) => ({
      label: folder.name,
      onClick: () => openFolder(folder.id),
    })),
  ]
})

const isFiltering = computed(
  () => !!searchQuery.value.trim() || selectedType.value !== 'all',
)

function toggleSort(field: string) {
  if (sortField.value === field) {
    sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortField.value = field
    sortDirection.value = 'asc'
  }
}

// Folders have no byte size, so a size sort treats them as 0 and they cluster
// at the light end. A name tiebreaker keeps ties from shuffling on re-sort.
function compareRows(a: FileItem, b: FileItem) {
  const factor = sortDirection.value === 'desc' ? -1 : 1
  if (sortField.value === 'name') return factor * a.name.localeCompare(b.name)
  if (sortField.value === 'size') {
    return (
      factor * ((a.size ?? 0) - (b.size ?? 0)) || a.name.localeCompare(b.name)
    )
  }
  return factor * (a.daysAgo - b.daysAgo) || a.name.localeCompare(b.name)
}

// The time buckets are the primary structure; the active column sort only
// orders rows within each bucket. Group order stays chronological either way.
const groups = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  const visible = itemsFor(props.view, currentFolderId.value).filter((item) => {
    const matchesType =
      selectedType.value === 'all' || categoryOf(item) === selectedType.value
    const matchesQuery = !query || item.name.toLowerCase().includes(query)
    return matchesType && matchesQuery
  })
  const sorted = [...visible].sort(compareRows)
  return timeBuckets
    .map((bucket) => ({
      key: bucket.key,
      label: bucket.label,
      items: sorted.filter((item) => bucket.match(item.daysAgo)),
    }))
    .filter((group) => group.items.length)
})
</script>

<template>
  <PageHeader>
    <Breadcrumbs :items="breadcrumbs" />
    <div class="flex items-center gap-2">
      <Button label="New folder" icon-left="lucide-folder-plus" />
      <Button variant="solid" label="Upload" icon-left="lucide-upload" />
    </div>
  </PageHeader>

  <div class="px-3 pt-4 pb-10 sm:px-5">
    <FilesToolbar
      :query="searchQuery"
      :type="selectedType"
      @update:query="searchQuery = $event"
      @update:type="selectedType = $event"
    />

    <FileTable
      :groups="groups"
      :sort-field="sortField"
      :sort-direction="sortDirection"
      @sort="toggleSort"
      @open="onRowClick"
    />

    <div
      v-if="!groups.length"
      class="flex flex-col items-center gap-1 py-16 text-center"
    >
      <span
        :class="isFiltering ? 'lucide-search-x' : 'lucide-folder-open'"
        class="size-6 text-ink-gray-4"
        aria-hidden="true"
      />
      <p class="text-base font-medium text-ink-gray-7">
        {{ isFiltering ? 'No files found' : 'This folder is empty' }}
      </p>
      <p class="text-p-sm text-ink-gray-5">
        {{
          isFiltering
            ? 'Try a different search or file type.'
            : 'Upload a file or create a folder to get started.'
        }}
      </p>
    </div>
  </div>
</template>
