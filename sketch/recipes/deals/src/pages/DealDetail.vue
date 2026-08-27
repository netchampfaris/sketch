<script setup lang="ts">
import { computed } from 'vue'
import {
  Avatar,
  Badge,
  Breadcrumbs,
  Button,
  Dropdown,
  PageHeader,
  ScrollArea,
} from 'frappe-ui'
import { activity, findDeal, logo, owners, statusBadgeTheme } from '../data'

// `props: true` in the route hands the URL parameter in as a prop.
const props = defineProps<{ org: string }>()

const found = computed(() => findDeal(decodeURIComponent(props.org)))
const owner = computed(() =>
  found.value ? owners[found.value.deal.owner] : null,
)

const actions = [
  { label: 'Move stage', icon: 'lucide-arrow-right-left' },
  { label: 'Assign to…', icon: 'lucide-user-plus' },
  { label: 'Mark as lost', icon: 'lucide-circle-x' },
]
</script>

<template>
  <PageHeader>
    <Breadcrumbs
      :items="[
        { label: 'Deals', route: { path: '/list' } },
        { label: found ? found.deal.org : 'Not found' },
      ]"
    />
    <div class="ml-auto flex items-center gap-2">
      <Button label="Edit" icon-left="lucide-pencil" :disabled="!found" />
      <Dropdown :options="actions" align="end">
        <Button variant="ghost" icon="lucide-ellipsis" label="Deal actions" />
      </Dropdown>
    </div>
  </PageHeader>

  <div v-if="found" class="flex min-h-0 flex-1">
    <!-- Content column, then a right panel of label and value rows. -->
    <ScrollArea class="min-h-0 flex-1" viewport-class="px-3 pt-5 pb-10 sm:px-5">
      <div class="mx-auto max-w-[940px]">
        <div class="flex items-center gap-3">
          <Avatar
            :label="found.deal.org"
            :image="logo(found.deal.org)"
            size="2xl"
            shape="square"
          />
          <div class="min-w-0">
            <h1 class="truncate text-2xl text-ink-gray-9">
              {{ found.deal.org }}
            </h1>
            <p class="mt-0.5 text-sm text-ink-gray-5">
              {{ found.deal.value }} · closes {{ found.deal.due }}
            </p>
          </div>
          <Badge
            variant="subtle"
            :theme="statusBadgeTheme[found.theme]"
            :label="found.status"
            class="ml-auto shrink-0"
          />
        </div>

        <p class="mt-5 text-p-base text-ink-gray-7">
          {{ found.deal.org }} came in through {{ found.deal.tag }}. The team
          wants one workspace for the whole sales floor, with reporting the
          finance team can read without help.
        </p>

        <h2 class="mt-8 text-lg-semibold text-ink-gray-8">Activity</h2>
        <ul class="mt-3 divide-y divide-outline-gray-1">
          <li
            v-for="item in activity"
            :key="item.title"
            class="flex items-start gap-3 py-3"
          >
            <span
              class="mt-0.5 rounded-full bg-surface-gray-2 p-1.5 text-ink-gray-6"
            >
              <span :class="item.icon" class="size-3.5" aria-hidden="true" />
            </span>
            <div class="min-w-0 flex-1">
              <p class="text-base text-ink-gray-8">{{ item.title }}</p>
              <p class="mt-0.5 text-p-sm text-ink-gray-5">{{ item.detail }}</p>
            </div>
            <span class="shrink-0 text-sm text-ink-gray-5">{{ item.when }}</span>
          </li>
        </ul>
      </div>
    </ScrollArea>

    <aside class="w-[20rem] shrink-0 border-l border-outline-gray-1">
      <ScrollArea class="h-full min-h-0" viewport-class="px-5 pt-5 pb-10">
        <h2 class="text-sm text-ink-gray-5">Details</h2>
        <dl class="mt-3 space-y-4">
          <div>
            <dt class="text-sm text-ink-gray-6">Owner</dt>
            <dd class="mt-1 flex items-center gap-2">
              <Avatar :label="owner.name" :image="owner.image" size="sm" />
              <span class="truncate text-base text-ink-gray-8">
                {{ owner.name }}
              </span>
            </dd>
          </div>
          <div>
            <dt class="text-sm text-ink-gray-6">Deal value</dt>
            <dd class="mt-1 text-base-semibold text-ink-gray-9">
              {{ found.deal.value }}
            </dd>
          </div>
          <div>
            <dt class="text-sm text-ink-gray-6">Stage</dt>
            <dd class="mt-1">
              <Badge
                variant="subtle"
                :theme="statusBadgeTheme[found.theme]"
                :label="found.status"
              />
            </dd>
          </div>
          <div>
            <dt class="text-sm text-ink-gray-6">Close date</dt>
            <dd class="mt-1 text-base text-ink-gray-8">{{ found.deal.due }}</dd>
          </div>
          <div>
            <dt class="text-sm text-ink-gray-6">Source</dt>
            <dd class="mt-1">
              <Badge variant="outline" :label="found.deal.tag" />
            </dd>
          </div>
          <div>
            <dt class="text-sm text-ink-gray-6">Open deals with owner</dt>
            <dd class="mt-1 text-base text-ink-gray-8">{{ owner.deals }}</dd>
          </div>
        </dl>
      </ScrollArea>
    </aside>
  </div>

  <div
    v-else
    class="flex flex-col items-center justify-center gap-3 py-16 text-center"
  >
    <div class="rounded-full bg-surface-gray-2 p-3 text-ink-gray-5">
      <span class="lucide-search-x size-6" aria-hidden="true" />
    </div>
    <p class="text-base text-ink-gray-7">No such deal</p>
    <p class="text-sm text-ink-gray-5">It may have been renamed or removed.</p>
    <Button
      variant="solid"
      theme="gray"
      label="Back to deals"
      :route="{ path: '/list' }"
      class="mt-2"
    />
  </div>
</template>
