<script setup lang="ts">
/**
 * /about: what Sketch is, how to start, and what a prototype can do. Someone
 * new, signed out or just signed in, should get all three in under a minute.
 *
 * It sits in the setup's centred column (`SettingsScreen.vue`, the empty
 * gallery), and its steps are the setup's own (`SetupSteps.vue`), so the
 * three screens tell one story. Plain words: no protocol names outside step
 * 2, where they tell an agent's owner it will work.
 *
 * A Guest reads it with no session (`router.ts`, `meta.public`). For them
 * step 1 is signing in. A signed-in user gets the real Copy button, so the
 * page reads their token, minting it if this is the first place they open;
 * that is the setup on screen, which is the only place a token is minted.
 *
 * Every row of "In a prototype" is a feature the Viewer has: Variants and the
 * Demo pill (`runtime/shell/DemoPill.vue`), notes and comments
 * (`runtime/shell/notes.ts`, `comments.ts`), and the Share dialog's public
 * link (`ShareDialog.vue`) and comments.
 */
import { watch } from 'vue'
import { Button } from 'frappe-ui'
import AgentLogo from '../components/AgentLogo.vue'
import AgentStatus from '../components/AgentStatus.vue'
import CopyPromptButton from '../components/CopyPromptButton.vue'
import GithubMark from '../components/GithubMark.vue'
import SetupSteps from '../components/SetupSteps.vue'
import { connected, heroApps } from '../agents'
import { agentToken, continueWithProvider, prototypes, signedIn } from '../store'

const features = [
  { icon: 'lucide-columns-2', title: 'Compare options', body: 'Your agent can put versions side by side, and you pick one.' },
  {
    icon: 'lucide-users',
    title: 'Switch roles and states',
    body: 'Try the page as a different person or in a different state from the Demo menu.',
  },
  {
    icon: 'lucide-message-square',
    title: 'Leave notes',
    body: 'Point at anything on the page and leave a note for your agent, or a comment for people.',
  },
  { icon: 'lucide-share-2', title: 'Share it', body: 'Send the link to your team so they can try it and leave comments.' },
]

/** The setup is the empty gallery for a user with nothing built, else Settings. The list loads at boot (`App.vue`). */
function setupRoute(): string {
  return prototypes.data?.length ? '/settings' : '/'
}

// The session can land after this page mounts (a direct load), so it waits for it.
watch(
  signedIn,
  (yes) => {
    if (yes && !agentToken.data?.token) agentToken.reload()
  },
  { immediate: true },
)
</script>

<template>
  <!-- The setup's column and top offset (`SettingsScreen.vue`), content left-aligned. -->
  <div class="px-3 pb-10 pt-10 sm:px-5">
    <div class="mx-auto max-w-[620px] py-6 sm:py-12">
      <h1 class="text-2xl-semibold text-ink-gray-8">About Sketch</h1>
      <p class="mt-3 text-p-base text-ink-gray-6">
        Sketch shows the prototypes your AI agent builds. You describe what you want in your agent, and it shows up
        here, live, for you and your team to try.
      </p>

      <section class="mt-10">
        <h2 class="text-base-semibold text-ink-gray-8">How it works</h2>
        <SetupSteps class="mt-3" :signed-out="!signedIn">
          <template #action>
            <CopyPromptButton v-if="signedIn" />
            <Button v-else theme="gray" variant="subtle" @click="continueWithProvider">
              <template #prefix><GithubMark class="size-4" /></template>
              Continue with GitHub
            </Button>
          </template>
        </SetupSteps>
        <!-- The next thing to do, for someone signed in: the setup, or where it stands once done. -->
        <template v-if="signedIn">
          <AgentStatus v-if="connected" class="mt-6" read-only />
          <Button
            v-else
            class="mt-6"
            label="Go to setup"
            :route="setupRoute()"
            theme="gray"
            variant="subtle"
          />
        </template>
      </section>

      <section class="mt-10">
        <h2 class="text-base-semibold text-ink-gray-8">Works with</h2>
        <div class="mt-3 flex flex-wrap gap-4">
          <span
            v-for="app in heroApps"
            :key="app.name"
            :aria-label="app.name"
            class="size-6 text-ink-gray-5"
            role="img"
            :title="app.name"
          >
            <AgentLogo class="size-full" :svg="app.logo" />
          </span>
        </div>
      </section>

      <section class="mt-10">
        <h2 class="text-base-semibold text-ink-gray-8">In a prototype</h2>
        <ul class="mt-3 flex flex-col gap-4">
          <li v-for="feature in features" :key="feature.title" class="flex gap-3">
            <!-- 16px icon in the steps' 24px marker column, so both lists share one x. -->
            <span class="grid size-6 shrink-0 place-items-center">
              <span aria-hidden="true" class="size-4 text-ink-gray-6" :class="feature.icon" />
            </span>
            <div class="min-w-0">
              <p class="text-base-medium text-ink-gray-8">{{ feature.title }}</p>
              <p class="mt-1 text-p-sm text-ink-gray-5">{{ feature.body }}</p>
            </div>
          </li>
        </ul>
      </section>

      <section class="mt-10">
        <h2 class="text-base-semibold text-ink-gray-8">Something is broken</h2>
        <p class="mt-3 text-p-base text-ink-gray-7">
          Open an issue on
          <a
            class="text-ink-blue-link hover:underline"
            href="https://github.com/netchampfaris/sketch"
            rel="noreferrer noopener"
            target="_blank"
            >the Sketch repository</a
          >. Name your agent client and paste the error it printed. Never paste your token.
        </p>
      </section>
    </div>
  </div>
</template>
