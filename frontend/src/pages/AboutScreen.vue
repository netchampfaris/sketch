<script setup lang="ts">
/**
 * /about: what Sketch is, and the three steps to a first prototype.
 *
 * It replaces /help. That page was a symptom list: four client config keys,
 * three `/mcp` error codes and a warning about claude.ai connectors. It read
 * as a manual for a product the reader had not started yet. The route a
 * stranger follows off the feed has one job, which is to get them signed in
 * and connected, so that is all this page does.
 *
 * A Guest reads it with no session (`router.ts`, `meta.public`), so it asks
 * for nothing and every step is written for somebody who has not signed in.
 *
 * The setup itself is not repeated here. Settings holds the prompt with the
 * user's own token in it (`SettingsScreen.vue`, SETUP_PROMPT), and a second
 * copy of it would drift from the first.
 */
import { computed } from 'vue'
import { Button, PageHeader } from 'frappe-ui'
import { goToLogin, signedIn } from '../store'

/** The three steps, in the order a new user takes them. */
const steps = [
  {
    title: 'Sign in with GitHub',
    body: 'The same button makes your account. Sketch asks for nothing else.',
  },
  {
    title: 'Connect your agent',
    body: 'Settings carries a setup prompt with your token in it. Paste that into your agent, and the agent does the rest.',
  },
  {
    title: 'Ask it to build something',
    body: 'Your agent writes the files over MCP. Keep the prototype tab open: it reloads itself on every write.',
  },
]

const action = computed(() =>
  signedIn.value
    ? { label: 'Open settings', icon: 'lucide-settings', route: '/settings' }
    : { label: 'Sign in', icon: 'lucide-log-in', route: '' },
)
</script>

<template>
  <PageHeader class="border-b-0 pt-6">
    <div class="min-w-0">
      <h1 class="truncate text-2xl-semibold text-ink-gray-8">About Sketch</h1>
    </div>
  </PageHeader>

  <!-- The reading measure, not the 940px column: this page is prose. -->
  <div class="max-w-[640px] px-3 pb-10 pt-6 sm:px-5">
    <p class="text-p-base text-ink-gray-7">
      Sketch renders frappe-ui prototypes that your own agent writes over MCP.
      There is no editor here and no agent panel: you bring your own agent, and
      Sketch gives it somewhere to write and something to render.
    </p>

    <section class="mt-10">
      <h2 class="text-lg-semibold text-ink-gray-8">Start</h2>
      <ol class="mt-4 flex flex-col gap-4">
        <li v-for="(step, index) in steps" :key="step.title" class="flex gap-3">
          <!--
            The number is a fixed 24px circle, so a step with two lines of body
            copy keeps its marker on the first line and every marker sits on
            one x.
          -->
          <span
            aria-hidden="true"
            class="grid size-6 shrink-0 place-items-center rounded-full bg-surface-gray-2 text-xs-medium text-ink-gray-7"
          >
            {{ index + 1 }}
          </span>
          <div class="min-w-0">
            <p class="text-base-medium text-ink-gray-8">{{ step.title }}</p>
            <p class="mt-1 text-p-sm text-ink-gray-5">{{ step.body }}</p>
          </div>
        </li>
      </ol>

      <!--
        One action, and it is the next step the reader can actually take: the
        way in for a Guest, the token for somebody already signed in.
      -->
      <Button
        v-if="signedIn"
        class="mt-6"
        :icon-left="action.icon"
        :label="action.label"
        :route="action.route"
        theme="gray"
        variant="subtle"
      />
      <Button
        v-else
        class="mt-6"
        :icon-left="action.icon"
        :label="action.label"
        theme="gray"
        variant="subtle"
        @click="goToLogin"
      />
    </section>

    <section class="mt-10">
      <h2 class="text-lg-semibold text-ink-gray-8">Something is broken</h2>
      <p class="mt-1 text-p-base text-ink-gray-7">
        Open an issue on
        <a
          class="text-ink-blue-link hover:underline"
          href="https://github.com/netchampfaris/sketch"
          rel="noreferrer noopener"
          target="_blank"
          >the Sketch repository</a
        >. Name your agent client and paste the error it printed. Never paste
        your token.
      </p>
    </section>
  </div>
</template>
