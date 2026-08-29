<script setup lang="ts">
/**
 * Your prototypes: the Prototype gallery (spec 11).
 *
 * The header holds the count and the one primary action. The body is a
 * responsive grid of cards, each with a live preview of the Prototype.
 */
import { computed, onMounted, ref } from 'vue'
import { Button, LoadingText, PageHeader } from 'frappe-ui'
import NewPrototypeDialog from '../components/NewPrototypeDialog.vue'
import PrototypeCard from '../components/PrototypeCard.vue'
import { prototypes, session } from '../store'

const showPicker = ref(false)

const items = computed(() => prototypes.data ?? [])
const count = computed(() => items.value.length)
const firstLoad = computed(() => prototypes.loading && !prototypes.isFinished)

/**
 * True once an agent has called /mcp with a good token (plan v2, step 1.5).
 *
 * Read from `session`, never from `get_agent_token`: that call mints a token
 * as a side effect, and rendering a screen must never mint one. `has_token`
 * is the wrong signal for the same reason.
 */
const connected = computed(() => Boolean(session.data?.last_used))

onMounted(() => {
  if (!prototypes.isFinished) prototypes.reload()
})
</script>

<template>
  <PageHeader>
    <div class="min-w-0">
      <h1 class="truncate text-lg font-semibold text-ink-gray-8">Your prototypes</h1>
      <p class="text-xs text-ink-gray-5">
        {{ count }} {{ count === 1 ? 'prototype' : 'prototypes' }}
      </p>
    </div>
    <Button
      icon-left="lucide-plus"
      label="New prototype"
      theme="gray"
      variant="subtle"
      @click="showPicker = true"
    />
  </PageHeader>

  <div class="px-3 pb-10 pt-6 sm:px-5">
    <!--
      Two columns, never three. The shell centres the page in a 940px column,
      so a third column only makes each card narrower: 284px against 438px.
      The card scales a 1280px iframe to its own width, so a narrow card makes
      the preview unreadable. A wider screen changes nothing, because the
      column does not grow.
    -->
    <div v-if="firstLoad" class="grid gap-6 md:grid-cols-2">
      <div v-for="n in 3" :key="n">
        <div class="aspect-[16/10] w-full rounded-6 bg-surface-gray-2" />
        <div class="mt-3 h-10"><LoadingText :lines="2" /></div>
      </div>
    </div>

    <div
      v-else-if="!count"
      class="flex flex-col items-center justify-center gap-3 py-16 text-center"
    >
      <div class="rounded-full bg-surface-gray-2 p-3 text-ink-gray-5">
        <span class="lucide-panels-top-left size-6" aria-hidden="true" />
      </div>
      <p class="text-base text-ink-gray-7">No prototypes yet</p>
      <!--
        The empty state names the one thing a new user must do first
        (problem B1). Sketch has no editor, so a prototype only appears after
        an agent writes one.
      -->
      <p class="max-w-sm text-sm text-ink-gray-5">
        Sketch has no editor. Your own agent writes the prototypes over MCP.
      </p>
      <p v-if="!connected" class="max-w-sm text-sm text-ink-gray-5">
        Connect an agent first, then ask it to build something.
      </p>
      <div class="mt-2 flex flex-wrap items-center justify-center gap-2">
        <!--
          `Connect your agent` leads here, and only here. The header keeps
          the one `New prototype` action (spec 11). No button is solid: subtle
          leads, outline follows. An agent that has
          already called /mcp needs no invitation, so the button goes.
        -->
        <Button
          v-if="!connected"
          icon-left="lucide-plug-zap"
          label="Connect your agent"
          route="/settings"
          theme="gray"
          variant="subtle"
        />
        <Button
          icon-left="lucide-plus"
          label="New prototype"
          theme="gray"
          variant="outline"
          @click="showPicker = true"
        />
      </div>
    </div>

    <div v-else class="grid gap-6 md:grid-cols-2">
      <PrototypeCard
        v-for="item in items"
        :key="item.name"
        :prototype="item"
        @changed="prototypes.reload()"
        @removed="prototypes.reload()"
      />
    </div>
  </div>

  <NewPrototypeDialog v-model:open="showPicker" @created="prototypes.reload()" />
</template>
