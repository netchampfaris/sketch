<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  Button,
  PageHeader,
  PageHeaderTitle,
  TabButtons,
} from 'frappe-ui'
import { List, ListCell, ListRow, ListRows } from 'frappe-ui/list'
import {
  accounts,
  accountsTotal,
  cashflowStats,
  currency,
  expenseBreakdown,
  transactions,
} from '../data'

const flowTab = ref('outgoings')
const flowRows = computed(() => transactions[flowTab.value])
</script>

<template>
  <PageHeader>
    <PageHeaderTitle>Cashflow</PageHeaderTitle>
    <div class="flex items-center gap-2">
      <TabButtons
        v-model="flowTab"
        :options="[
          { label: 'Incomings', value: 'incomings' },
          { label: 'Outgoings', value: 'outgoings' },
        ]"
      />
      <Button variant="solid" label="Add transaction" icon-left="lucide-plus" />
    </div>
  </PageHeader>

  <!-- Centred, single-column dashboard: everything stacks in one column capped
       at max-w-4xl, so the layout reads top to bottom rather than spreading
       edge to edge. -->
  <div class="p-4">
    <div class="mx-auto max-w-4xl space-y-6">
      <!-- KPI strip: one row, no per-item cards, just thin vertical dividers.
           Each cell shows the figure and its trend. -->
      <div class="grid grid-cols-4 divide-x divide-outline-gray-2">
        <div
          v-for="stat in cashflowStats"
          :key="stat.label"
          class="px-4 first:pl-0 last:pr-0"
        >
          <div class="text-xs text-ink-gray-5">{{ stat.label }}</div>
          <div
            class="mt-1 text-2xl font-semibold"
            :class="stat.value < 0 ? 'text-ink-red-5' : 'text-ink-gray-9'"
          >
            {{ currency(stat.value) }}
          </div>
          <div class="mt-1 flex items-center gap-1 text-xs text-ink-gray-5">
            <span
              :class="stat.delta >= 0 ? 'lucide-arrow-up' : 'lucide-arrow-down'"
              class="size-3"
              aria-hidden="true"
            />
            <span>{{ Math.abs(stat.delta) }}% vs last month</span>
          </div>
        </div>
      </div>

      <!-- Recent transactions: full width, spanning the whole column. -->
      <section class="space-y-2">
        <div class="flex h-7 items-center justify-between">
          <h3 class="text-sm font-semibold text-ink-gray-8">
            Recent transactions
          </h3>
          <Button variant="ghost" label="View all" />
        </div>
        <!-- list-row-px-0 drops the interactive row's default 0.75rem inset so
             cells sit flush with the panel header and the KPI strip above.
             One shared left and right edge down the page. -->
        <List
          class="list-row-px-0"
          :columns="['8rem', 'minmax(0,1fr)', '8rem']"
          :row-height="44"
        >
          <ListRows :items="flowRows" v-slot="{ item }">
            <ListRow @click="() => {}">
              <ListCell>
                <span class="text-sm text-ink-gray-6">{{ item.date }}</span>
              </ListCell>
              <ListCell>
                <span class="truncate text-sm text-ink-gray-8">
                  {{ item.description }}
                </span>
              </ListCell>
              <ListCell class="justify-end">
                <span
                  class="text-sm"
                  :class="
                    flowTab === 'incomings'
                      ? 'text-ink-green-5'
                      : 'text-ink-gray-8'
                  "
                >
                  {{ flowTab === 'incomings' ? '+' : '-'
                  }}{{ currency(item.amount).replace('-', '') }}
                </span>
              </ListCell>
            </ListRow>
          </ListRows>
        </List>
      </section>

      <!-- Divider between the transactions row above and the two-up widgets
           below. -->
      <div class="border-t border-outline-gray-2" />

      <!-- Bottom row: Cash accounts beside Spend this month. -->
      <div class="grid grid-cols-2 gap-8">
        <section class="space-y-2">
          <div class="flex h-7 items-center justify-between">
            <h3 class="text-sm font-semibold text-ink-gray-8">Cash accounts</h3>
            <span class="text-sm text-ink-gray-6">
              {{ currency(accountsTotal) }}
            </span>
          </div>
          <div class="divide-y divide-outline-gray-1">
            <div
              v-for="account in accounts"
              :key="account.number"
              class="flex items-center justify-between py-2"
            >
              <div class="min-w-0">
                <div class="truncate text-sm text-ink-gray-8">
                  {{ account.name }}
                </div>
                <div class="text-p-xs text-ink-gray-5">
                  {{ account.number }}
                </div>
              </div>
              <span
                class="shrink-0 text-sm"
                :class="
                  account.balance < 0 ? 'text-ink-red-5' : 'text-ink-gray-8'
                "
              >
                {{ currency(account.balance) }}
              </span>
            </div>
          </div>
        </section>

        <section class="space-y-3">
          <div class="flex h-7 items-center">
            <h3 class="text-sm font-semibold text-ink-gray-8">
              Spend this month
            </h3>
          </div>
          <div class="space-y-2.5">
            <div
              v-for="row in expenseBreakdown"
              :key="row.category"
              class="space-y-1"
            >
              <div class="flex items-center justify-between text-sm">
                <span class="truncate text-ink-gray-7">{{ row.category }}</span>
                <span class="text-ink-gray-6">
                  {{ currency(row.amount).replace('.00', '') }}
                </span>
              </div>
              <div class="h-1.5 overflow-hidden rounded-full bg-surface-gray-2">
                <div
                  class="h-full rounded-full bg-surface-gray-6"
                  :style="{ width: `${row.pct}%` }"
                />
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>
