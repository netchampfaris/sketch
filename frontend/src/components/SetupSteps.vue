<script setup lang="ts">
/**
 * The three steps to a first prototype, one list for the empty gallery,
 * Settings and About, so the three never drift apart.
 *
 * Step 1's control comes in through the `action` slot: the Copy button where
 * the user has a token, "Continue with GitHub" on About for a Guest. A Guest's
 * step 1 is signing in, so `signedOut` swaps its title and drops its line: the
 * button says it all.
 *
 * Each row is a 24px grey number, a title and a muted line, the shape About
 * used for its own steps. The number is a fixed circle, so a two-line
 * description keeps its marker on the first line and every marker sits on one x.
 */
import { computed } from 'vue'

const props = defineProps<{ signedOut?: boolean }>()

const steps = computed(() => [
  props.signedOut
    ? { title: 'Sign in with GitHub', body: '' }
    : { title: 'Copy the setup prompt', body: 'It has your token in it, so keep it to yourself.' },
  {
    title: 'Paste it into your agent',
    body: 'Claude Code, Cursor, Codex, or any agent that can add an MCP server. It sets Sketch up by itself.',
  },
  { title: 'Start building there', body: 'Ask for a prototype. It shows up here, live, as your agent writes it.' },
])
</script>

<template>
  <ol class="flex flex-col gap-4">
    <li v-for="(step, index) in steps" :key="step.title" class="flex gap-3">
      <span
        aria-hidden="true"
        class="grid size-6 shrink-0 place-items-center rounded-full bg-surface-gray-2 text-xs-medium text-ink-gray-7"
      >
        {{ index + 1 }}
      </span>
      <div class="min-w-0">
        <p class="text-base-medium text-ink-gray-8">{{ step.title }}</p>
        <div v-if="index === 0 && $slots.action" class="mt-2"><slot name="action" /></div>
        <p v-if="step.body" class="text-p-sm text-ink-gray-5" :class="index === 0 && $slots.action ? 'mt-2' : 'mt-1'">
          {{ step.body }}
        </p>
      </div>
    </li>
  </ol>
</template>
