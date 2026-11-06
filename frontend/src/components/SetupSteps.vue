<script setup lang="ts">
/**
 * The three steps to a first prototype, one list for the empty gallery,
 * Settings and About, so the three never drift apart.
 *
 * Step 1's control comes in through the `action` slot: the Copy button where
 * the user has a token, "Sign in with GitHub" on About for a Guest. A step
 * whose slot is filled has no title: the button is its first row, with the
 * number centred on it, and the line follows.
 *
 * `signedOut` is About's Guest version. Step 1 is signing in, with no line:
 * the button says it all. Step 2 then cannot say "paste it", since nothing
 * has been copied yet, so it folds copying and pasting into one step.
 *
 * A user who is connected has done the first two steps, so Settings and About
 * list those two and leave "Start building there" out.
 *
 * Each row is a 24px grey number, a title and a muted line, the shape About
 * used for its own steps. The number is a fixed circle, so a two-line
 * description keeps its marker on the first line and every marker sits on one
 * x. A title is 24px tall (`leading-6`), so its centre is the number's.
 */
import { computed, useSlots } from 'vue'
import { connected } from '../agents'

const props = defineProps<{ signedOut?: boolean }>()

const slots = useSlots()

const build = { title: 'Start building there', body: 'Ask for a prototype. It shows up here, live, as your agent writes it.' }

const all = computed(() =>
  props.signedOut
    ? [
        { title: 'Sign in with GitHub', body: '' },
        {
          title: 'Connect your agent',
          body: 'Copy the setup prompt from Sketch and paste it into Claude Code, Cursor, Codex, or any agent that can add an MCP server. It does the rest.',
        },
        build,
      ]
    : [
        { title: 'Copy the setup prompt', body: 'It has your token in it, so keep it to yourself.' },
        {
          title: 'Paste it into your agent',
          body: 'Claude Code, Cursor, Codex, or any agent that can add an MCP server. It does the rest.',
        },
        build,
      ],
)

const steps = computed(() => (connected.value ? all.value.slice(0, 2) : all.value))

/** Step 1 is the control when the slot is filled, and has no title then. */
const isAction = (index: number): boolean => index === 0 && Boolean(slots.action)
</script>

<template>
  <ol class="flex flex-col gap-4">
    <li v-for="(step, index) in steps" :key="step.title" class="flex gap-3">
      <span
        aria-hidden="true"
        class="grid size-6 shrink-0 place-items-center rounded-full bg-surface-gray-2 text-xs-medium text-ink-gray-7"
        :class="isAction(index) && 'mt-0.5'"
      >
        {{ index + 1 }}
      </span>
      <div class="min-w-0">
        <slot v-if="isAction(index)" name="action" />
        <p v-else class="text-base-medium leading-6 text-ink-gray-8">{{ step.title }}</p>
        <p v-if="step.body" class="mt-1 text-p-sm text-pretty text-ink-gray-5">{{ step.body }}</p>
      </div>
    </li>
  </ol>
</template>
