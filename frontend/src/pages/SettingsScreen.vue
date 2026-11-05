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
 * status, the app picker, one Copy button, and the prompt folded away. Reset
 * lives in the status line's ⋯ menu.
 *
 * Still no per-client tabs. There were eight once, with eight config snippets,
 * and the user still had to find the right file and merge into it by hand.
 * The per-client facts now live inside the one setup prompt, which the user's
 * own agent reads: the agent knows which client it runs in. The app picker
 * changes only the "where to paste" line, never the prompt.
 */
import { PageHeader } from 'frappe-ui'
import AgentConnect from '../components/AgentConnect.vue'
</script>

<template>
  <!--
    No rule under the title, and no subtitle. The top bar already draws a line,
    and a second one 12px below it read as a double border.

    `border-b-0` beats `PageHeader.vue`'s own `border-b` on source order, not
    on specificity: Tailwind emits `.border-b-0` after `.border-b`. The
    component hard-codes the border and exposes no prop, and its class lands on
    the same element as ours through `PageHeaderBase`'s `$attrs`.

    `pt-6` matches the body's own top padding below.
  -->
  <PageHeader class="border-b-0 pt-6">
    <h1 class="truncate text-2xl-semibold text-ink-gray-8">Settings</h1>
  </PageHeader>

  <!--
    Unboxed under its heading: one task, not a card of its own. 620px, the
    gallery's setup column, so the steps and the prompt keep a reading line.
  -->
  <div class="max-w-[620px] px-3 pb-10 pt-6 sm:box-content sm:px-5">
    <section>
      <h2 class="text-base-semibold text-ink-gray-8">Agent connection</h2>
      <AgentConnect class="mt-3" />
    </section>
  </div>
</template>
