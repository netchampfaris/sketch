<script setup lang="ts">
import { Avatar, Button, Dropdown } from 'frappe-ui'
import {
  List,
  ListCell,
  ListGroup,
  ListHeader,
  ListHeaderCell,
  ListHeaderCellSort,
  ListRow,
} from 'frappe-ui/list'
import {
  childrenOf,
  fileActions,
  folderActions,
  relativeLabel,
  type FileItem,
} from '../data'

type Group = { key: string; label: string; items: FileItem[] }

const props = defineProps<{
  groups: Group[]
  sortField: string
  sortDirection: 'asc' | 'desc'
}>()

defineEmits<{
  sort: [field: string]
  open: [item: FileItem]
}>()

function directionFor(field: string) {
  return props.sortField === field ? props.sortDirection : null
}
</script>

<template>
  <!-- -mx-3 pairs with list-row-px-3: the row padding insets the content back
       to the toolbar edge while the hover surface bleeds into the gutter, so
       headers and rows stay aligned with the controls above. -->
  <List
    class="-mx-3 list-row-px-3"
    :columns="['minmax(0,1fr)', '11rem', '7.5rem', '5.5rem', '3rem']"
    :row-height="40"
  >
    <ListHeader class="sticky top-0 z-10 bg-surface-base">
      <ListHeaderCellSort
        :direction="directionFor('name')"
        @click="$emit('sort', 'name')"
      >
        Name
      </ListHeaderCellSort>
      <ListHeaderCell>Owner</ListHeaderCell>
      <ListHeaderCellSort
        :direction="directionFor('modified')"
        @click="$emit('sort', 'modified')"
      >
        Modified
      </ListHeaderCellSort>
      <!-- Right-aligned column: `align="end"` right-aligns the header and moves
           the sort glyph to the leading side, so "Size" stays flush with the
           values below. -->
      <ListHeaderCellSort
        :direction="directionFor('size')"
        align="end"
        @click="$emit('sort', 'size')"
      >
        Size
      </ListHeaderCellSort>
      <ListHeaderCell />
    </ListHeader>

    <!-- ListGroup wraps each time bucket in a labelled `role="rowgroup"` and
         keeps the rows as direct children, so the row dividers survive within
         a group. Folders and files interleave, ordered by the active sort. -->
    <ListGroup
      v-for="group in groups"
      :key="group.key"
      :label="group.label"
    >
      <ListRow
        v-for="item in group.items"
        :key="item.id"
        @click="$emit('open', item)"
      >
        <ListCell>
          <span :class="item.icon" class="size-4 shrink-0 text-ink-gray-5" />
          <span class="ml-3 truncate text-base text-ink-gray-8">
            {{ item.name }}
          </span>
        </ListCell>
        <ListCell>
          <Avatar :label="item.owner" :image="item.ownerImage" size="sm" />
          <span class="ml-2 truncate text-base text-ink-gray-7">
            {{ item.owner }}
          </span>
        </ListCell>
        <ListCell>
          <span class="text-base text-ink-gray-6">
            {{ relativeLabel(item.daysAgo) }}
          </span>
        </ListCell>
        <ListCell class="justify-end">
          <span class="text-base text-ink-gray-6">
            {{
              item.type === 'folder'
                ? `${childrenOf(item.id).length} items`
                : item.sizeLabel
            }}
          </span>
        </ListCell>
        <ListCell class="justify-end">
          <Dropdown
            :options="item.type === 'folder' ? folderActions : fileActions"
          >
            <Button
              variant="ghost"
              icon="lucide-ellipsis"
              :label="
                item.type === 'folder' ? 'Folder actions' : 'File actions'
              "
            />
          </Dropdown>
        </ListCell>
      </ListRow>
    </ListGroup>
  </List>
</template>
