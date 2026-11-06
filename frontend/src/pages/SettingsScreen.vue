<script setup lang="ts">
/**
 * Settings: one section, because connecting an agent is the only reason
 * anyone opens this page. Agent connection is one token, not a token list.
 * One user, one token.
 *
 * There is no Profile section. It held two read-only fields and no control
 * that changed anything: the username is frozen at signup, and the email is
 * the account. `AppTopBar.vue` already prints `@username` as the account menu
 * label, so the one fact worth reading was already on screen.
 *
 * The section is `AgentConnect.vue`, the same block a new user meets on the
 * empty gallery (decision 87), so reconnecting looks like connecting: the
 * status, one Copy button, and the prompt folded away. Reset lives in the
 * status line's ⋯ menu. The page sits in the gallery setup's own centred
 * column, so the block is in the same place on both screens.
 *
 * Still no per-client tabs. There were eight once, with eight config snippets,
 * and the user still had to find the right file and merge into it by hand.
 * The per-client facts now live inside the one setup prompt, which the user's
 * own agent reads: the agent knows which client it runs in.
 */
import AgentConnect from '../components/AgentConnect.vue'
</script>

<template>
  <!--
    The gallery's setup column: 620px, centred, its content left-aligned, so
    the steps and the prompt keep a reading line. The title sits inside it,
    with no page header and no rule: the top bar already draws a line.

    The top matches the gallery's setup heading, 88px under the bar (64px on
    a phone): the gallery's 24px page padding, its 16px toolbar gap, then the
    column's own 48px (24px).
  -->
  <main class="px-3 pb-10 pt-10 sm:px-5">
    <div class="mx-auto max-w-[620px] py-6 sm:py-12">
      <h1 class="text-xl-semibold text-ink-gray-8">Settings</h1>
      <!-- Unboxed under the title: one task, not a card of its own. -->
      <section class="mt-6">
        <h2 class="text-base-semibold text-ink-gray-8">Agent connection</h2>
        <AgentConnect class="mt-3" />
      </section>
    </div>
  </main>
</template>
