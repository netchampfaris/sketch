# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""A Prototype whose elements hide when something closes: a Filters popover with a collapsible Certificate group
inside it, a collapsible Documents card, tabs with words on the second, and a <details> block. Below them, enough
course cards that the page scrolls. Used by test_pins_reveal.py."""

HOME = """<script setup lang="ts">
import { ref } from 'vue'
import { Badge, Button, Checkbox, Popover, TabList, TabPanel, TabTrigger, Tabs } from 'frappe-ui'

const certOpen = ref(false)
const docsOpen = ref(true)
const certified = ref(false)
const tab = ref('overview')
const courses = ['Design basics', 'Frappe in a week', 'Writing for screens', 'Shipping small', 'Reading code', 'Data to decisions']
</script>

<template>
  <div class="mx-auto max-w-3xl space-y-6 p-8">
    <header class="flex items-center justify-between">
      <h1 class="text-2xl font-semibold text-ink-gray-9">Courses</h1>
      <Popover>
        <template #trigger><Button label="Filters" icon-left="lucide-filter" /></template>
        <div class="w-64 space-y-1 p-2">
          <button
            type="button"
            class="flex w-full items-center justify-between rounded px-2 py-1.5 text-base text-ink-gray-8 hover:bg-surface-gray-2"
            aria-controls="filter-certificate"
            :aria-expanded="certOpen"
            @click="certOpen = !certOpen"
          >
            Certificate <span class="text-ink-gray-5">{{ certOpen ? '−' : '+' }}</span>
          </button>
          <div v-if="certOpen" id="filter-certificate" class="px-2 py-1.5">
            <Checkbox v-model="certified" label="Certificate available" />
          </div>
        </div>
      </Popover>
    </header>

    <section class="rounded-lg border border-outline-gray-2">
      <button
        type="button"
        class="flex w-full items-center justify-between px-4 py-3 text-left text-base font-medium text-ink-gray-9"
        aria-controls="documents-body"
        :aria-expanded="docsOpen"
        @click="docsOpen = !docsOpen"
      >
        Documents <span class="text-sm font-normal text-ink-gray-5">{{ docsOpen ? 'Hide' : 'Show' }}</span>
      </button>
      <div v-show="docsOpen" id="documents-body" class="border-t border-outline-gray-2 px-4 py-3">
        <p class="text-sm text-ink-gray-6">Signed agreements, ID proofs and certificates for each learner.</p>
      </div>
    </section>

    <Tabs v-model="tab">
      <TabList>
        <TabTrigger value="overview" label="Overview" />
        <TabTrigger value="reviews" label="Reviews" />
      </TabList>
      <TabPanel value="overview"><p class="py-4 text-sm text-ink-gray-7">Six courses, two with certificates.</p></TabPanel>
      <TabPanel value="reviews"><p class="py-4 text-sm text-ink-gray-7">Clear and short. The exercises were the best part.</p></TabPanel>
    </Tabs>

    <details class="rounded-lg border border-outline-gray-2 px-4 py-3">
      <summary class="cursor-pointer text-base font-medium text-ink-gray-9">Refund policy</summary>
      <p class="pt-2 text-sm text-ink-gray-6">Full refund within 14 days of enrolling.</p>
    </details>

    <div class="grid grid-cols-2 gap-4">
      <div v-for="(c, i) in courses" :key="c" class="h-40 rounded-lg border border-outline-gray-2 p-4">
        <Badge v-if="i % 2" label="Featured" theme="blue" />
        <p class="mt-2 text-base font-medium text-ink-gray-9">{{ c }}</p>
      </div>
    </div>
  </div>
</template>
"""

TREE = {
	"src/App.vue": (
		"<script setup lang='ts'>\nimport { RouterView } from 'vue-router'\n</script>\n\n"
		"<template>\n  <div class='min-h-screen w-full bg-surface-base text-ink-gray-8'>\n"
		"    <RouterView />\n  </div>\n</template>\n"
	),
	"src/pages/Home.vue": HOME,
	"src/router.ts": (
		"import type { RouteRecordRaw } from 'vue-router'\nimport Home from './pages/Home.vue'\n\n"
		"const routes: RouteRecordRaw[] = [{ path: '/', name: 'Home', component: Home, meta: { title: 'Courses' } }]\n\n"
		"export default routes\n"
	),
}
