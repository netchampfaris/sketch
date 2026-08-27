<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  Button,
  DateRangePicker,
  PageHeader,
  PageHeaderTitle,
  ScrollArea,
  TabButtons,
} from 'frappe-ui'
import {
  List,
  ListCell,
  ListHeader,
  ListHeaderCell,
  ListRow,
  ListRows,
} from 'frappe-ui/list'
import { currency, months, pnlRows } from '../data'

// The picked window as [start, end] YYYY-MM-DD. It defaults to the full year.
const fyStart = months[0].date
const fyEnd = months[months.length - 1].date
const dateRange = ref([fyStart, fyEnd])
const period = ref('monthly')

// Preset windows for the picker's #actions column.
const rangePresets = [
  { label: 'Financial year', range: [fyStart, fyEnd] },
  { label: 'Last 6 months', range: [months[6].date, fyEnd] },
  { label: 'Last quarter', range: [months[9].date, fyEnd] },
  { label: 'Last month', range: [fyEnd, fyEnd] },
]

// Map the picked date window onto column indices by comparing YYYY-MM
// prefixes. A partial selection falls back to the whole year.
const visibleIndices = computed(() => {
  const [from, to] = dateRange.value
  if (!from || !to) return months.map((_, i) => i)
  const [lo, hi] = [from.slice(0, 7), to.slice(0, 7)].sort()
  return months.flatMap((m, i) => {
    const ym = m.date.slice(0, 7)
    return ym >= lo && ym <= hi ? [i] : []
  })
})

// A bucket is a labelled set of month indices: one per month for Monthly, or
// one per group of three for Quarterly. Both the columns and every cell derive
// from it, so one code path renders any range at either granularity.
const buckets = computed(() => {
  const idxs = visibleIndices.value
  if (period.value === 'monthly') {
    return idxs.map((i) => ({ label: months[i].label, idx: [i] }))
  }
  const groups = []
  for (let i = 0; i < idxs.length; i += 3) {
    const idx = idxs.slice(i, i + 3)
    const span = `${months[idx[0]].label}–${months[idx[idx.length - 1]].label}`
    groups.push({ label: span, idx })
  }
  return groups
})

const cellValue = (row: any, bucket: any) =>
  bucket.idx.reduce((sum: number, i: number) => sum + row.values[i], 0)

// The first column is the line-item label, then one flexible track per bucket.
const pnlColumns = computed(() => [
  'minmax(9rem,1.4fr)',
  ...buckets.value.map(() => 'minmax(4.5rem,1fr)'),
])
</script>

<template>
  <PageHeader>
    <PageHeaderTitle>Profit &amp; Loss</PageHeaderTitle>
    <div class="flex items-center gap-2">
      <Button variant="ghost" label="Compare" icon-left="lucide-git-compare" />
      <Button variant="solid" label="Export" icon-left="lucide-download" />
    </div>
  </PageHeader>

  <!-- `absolute inset-0` fills the shell's scroll region, whose ScrollArea root
       is `position: relative` with a definite height. That gives this page its
       own bounded height, so the filter bar and the column header stay put
       while only the rows scroll. The inner ScrollArea owns the scrolling. -->
  <div class="absolute inset-0 flex flex-col p-4">
    <!-- Filter bar: the date range picks the window, the period toggle sets the
         granularity, and both flow into the table columns below. -->
    <div class="mb-3 flex shrink-0 flex-wrap items-center gap-2">
      <DateRangePicker
        v-model="dateRange"
        dual-pane
        format="MMM YYYY"
        :min="fyStart"
        :max="fyEnd"
      >
        <template #prefix>
          <span
            class="lucide-calendar-range size-4 text-ink-gray-5"
            aria-hidden="true"
          />
        </template>
        <template #actions="{ setRange, close }">
          <Button
            v-for="preset in rangePresets"
            :key="preset.label"
            variant="ghost"
            size="sm"
            class="w-full !justify-start"
            :label="preset.label"
            @click="
              () => {
                setRange(preset.range)
                close()
              }
            "
          />
        </template>
      </DateRangePicker>
      <TabButtons
        v-model="period"
        :options="[
          { label: 'Monthly', value: 'monthly' },
          { label: 'Quarterly', value: 'quarterly' },
        ]"
      />
      <Button variant="ghost" label="Add filter" icon-left="lucide-filter" />
    </div>

    <ScrollArea orientation="both" class="min-h-0 flex-1">
      <List :columns="pnlColumns" :row-height="40">
        <!-- Pinned to the scroll viewport's top. An opaque background lets the
             rows scroll under it, and z-10 keeps it above them. -->
        <ListHeader class="sticky top-0 z-10 bg-surface-base">
          <ListHeaderCell>Line item</ListHeaderCell>
          <ListHeaderCell
            v-for="bucket in buckets"
            :key="bucket.label"
            class="justify-end"
          >
            {{ bucket.label }}
          </ListHeaderCell>
        </ListHeader>
        <ListRows :items="pnlRows" v-slot="{ item }">
          <ListRow v-if="item.type === 'section'">
            <ListCell>
              <span class="text-sm font-semibold text-ink-gray-7">
                {{ item.label }}
              </span>
            </ListCell>
          </ListRow>
          <ListRow v-else>
            <ListCell>
              <span class="truncate text-base text-ink-gray-8">
                {{ item.label }}
              </span>
            </ListCell>
            <ListCell
              v-for="bucket in buckets"
              :key="bucket.label"
              class="justify-end"
            >
              <span class="text-base text-ink-gray-7">
                {{ currency(cellValue(item, bucket)).replace('.00', '') }}
              </span>
            </ListCell>
          </ListRow>
        </ListRows>
      </List>
    </ScrollArea>
  </div>
</template>
