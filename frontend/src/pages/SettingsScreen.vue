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
 * The eight per-client panels are gone. They were eight tabs, eight config
 * snippets and eight notes, and the user still had to find the right file and
 * merge into it by hand. The per-client facts that made those panels worth
 * reading now live inside `SETUP_PROMPT`, which the user's own agent reads.
 * The agent knows which client it runs in, so one prompt covers every client
 * the tabs listed and the clients they did not.
 *
 * The token is never in a field on this page. It appears once, inside the
 * prompt, masked until the user asks for it.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { Button, PageHeader, dialog, toast, useCall } from 'frappe-ui'
import { usePoll } from '../poll'
import { agentToken, copyText, method, session } from '../store'
import type { AgentToken } from '../types'

/**
 * The whole setup, as one instruction to the user's agent.
 *
 * `<endpoint>` and `<token>` are the placeholders `fill()` substitutes, the
 * same pair the old snippets used.
 *
 * The three client facts in the second paragraph are the number one setup
 * failure, and each one is verified against the vendor's own documentation
 * (.scratch/sketch-onboarding/harnesses.md): the top-level key differs per
 * client, a whole-file paste destroys the user's other MCP servers, and a 401
 * starts an OAuth flow in clients that assume OAuth. They must survive
 * verbatim. An agent that guesses these writes a config that loads without an
 * error and serves no tools.
 *
 * The last paragraph asks for a tool call, so the agent proves the connection
 * instead of reporting that it edited a file. It then asks the agent to onboard
 * the user, because Sketch has no editor and no tour: a user whose tools work
 * still does not know what to say next. `get_skill` is the server's own
 * instruction sheet (`sketch/mcp/tools.py:615`), so the agent teaches from the
 * current document and not from memory.
 */
const SETUP_PROMPT = `Add the Sketch MCP server to this client, at user scope so it works in all my projects, not just this one.

  URL: <endpoint>
  Transport: streamable HTTP, POST only
  Header: Authorization: Bearer <token>

Use this client's own way to add an MCP server: its CLI command if it has one, otherwise its MCP config file. Merge the entry into that file, do not overwrite it, or I lose my other MCP servers. The top-level key differs per client: \`servers\` in VS Code, \`mcp\` in OpenCode, \`mcp_servers\` in Codex, \`mcpServers\` in the rest. Sketch authenticates with the static header above, so do not set up OAuth. Restart the client if it reads its config only at start, then call the Sketch tool that lists my prototypes and tell me what it returned.

When that works, onboard me. Call \`get_skill\` to read how Sketch works. Then tell me in a few lines what a prototype is, how I ask you to build or change one, and where I open it. Offer to build a small one now.`

/**
 * The token reads as bullets until the user asks for it (problem C6).
 *
 * A masked field above a clear-text block was false comfort: the token was on
 * screen the whole time in a screen share or a screenshot. One toggle, one
 * place the token can appear.
 */
const revealed = ref(false)

const regenerate = useCall<AgentToken>({
  url: method('regenerate_agent_token'),
  method: 'POST',
  immediate: false,
  onSuccess: () => {
    // `data` on a useCall handle is computed, so the fresh token is read back
    // rather than assigned.
    agentToken.reload()
    session.reload()
    toast.success('Token regenerated')
  },
  onError: (error) => toast.error(error.message),
})

const token = computed(() => agentToken.data?.token ?? '')
const endpoint = computed(() => agentToken.data?.endpoint ?? '')

/**
 * The mask is the token's own length, so revealing it cannot rewrap the block
 * and move everything below it.
 */
const maskedToken = computed(() => '•'.repeat(token.value.length))

/**
 * The connection state. `last_used` is stamped only by a good token on /mcp,
 * so it is the one honest signal that an agent arrived (plan v2, step 1.5).
 * Both replies may carry it, and an older reply carries neither, so read it
 * defensively and fall back to "not yet".
 */
const lastUsed = computed(
  () => agentToken.data?.last_used_pretty || session.data?.last_used_pretty || '',
)

/**
 * The state only ever changes on the server, so the page has to ask for it
 * (problem 2.2). Without this the screen still said "No agent has connected
 * yet." after the agent connected, and the one success signal in the whole
 * funnel sat behind a reload the user had no reason to do.
 *
 * The loop is `poll.ts`, shared with the gallery. It chains from the end of
 * one read to the start of the next, so a slow reply cannot stack requests
 * the way the old `setInterval` could. A hidden tab asks for nothing, and the
 * page catches up with one immediate read when the tab comes back. A failed
 * read backs off, so a dead endpoint no longer costs a request every five
 * seconds for as long as the tab stays open.
 *
 * It retires on the first confirmed connection. After that `last_used` only
 * ages, and re-reading the server to move "2 minutes ago" to "3 minutes ago"
 * is not worth a request. `lastUsed` may already be set on arrival, in which
 * case the poll never runs at all. Retirement is not final: the watcher below
 * arms the loop again when the connection state goes away.
 */
const POLL_MS = 5000

const poll = usePoll(
  async () => {
    await agentToken.reload()
    // `reload()` resolves on a failed request, so the error ref is the only
    // signal. False starts the backoff.
    return !agentToken.error
  },
  { interval: POLL_MS, done: () => Boolean(lastUsed.value) },
)

/**
 * Regenerate clears `last_used` on the server, because the old token is dead
 * and the stamp it left claims a connection that is gone
 * (`sketch_token.regenerate`, review 2.3). The screen then says "No agent has
 * connected yet." again and has to watch for the new token's first request.
 *
 * The poll retired on the old connection, and `done` cannot bring it back:
 * the loop reads `done` and there is no loop left to read it. So the screen
 * says it. Only an empty state arms it, so a live connection still costs no
 * requests.
 */
watch(lastUsed, (value) => {
  if (!value) poll.restart()
})

onMounted(() => agentToken.reload())

/** Put the live token and endpoint into the prompt. This is what Copy sends. */
function fill(text: string): string {
  let out = text
  if (endpoint.value) out = out.split('<endpoint>').join(endpoint.value)
  if (token.value) out = out.split('<token>').join(token.value)
  return out
}

/**
 * What the screen shows. Copy calls `fill`, so a masked block still puts the
 * real token on the clipboard.
 */
function shown(text: string): string {
  const filled = fill(text)
  if (revealed.value || !token.value) return filled
  return filled.split(token.value).join(maskedToken.value)
}

/**
 * Regenerate breaks every connected agent at once, so it asks first
 * (problem C5). Returning the call keeps the dialog open until the server
 * answers.
 */
function askToRegenerate(): void {
  dialog.confirm({
    title: 'Regenerate token?',
    message:
      'Every agent that holds the old token stops working at once. You must run the setup prompt again in each client.',
    confirmLabel: 'Regenerate',
    theme: 'red',
    onConfirm: () => regenerate.submit(),
  })
}

/**
 * `copyText` shows its own error toast and rethrows (store.ts), so the only
 * work left here is the success message. The catch stops a refused clipboard
 * write from surfacing as an unhandled rejection.
 */
async function copy(text: string, done: string): Promise<void> {
  try {
    await copyText(text)
  } catch {
    return
  }
  toast.success(done)
}
</script>

<template>
  <!--
    No rule under the title, and no subtitle. The top bar already draws a line,
    and a second one 12px below it read as a double border.

    `border-b-0` beats `PageHeader.vue`'s own `border-b` on source order, not
    on specificity: Tailwind emits `.border-b-0` after `.border-b`. The
    component hard-codes the border and exposes no prop, and its class lands on
    the same element as ours through `PageHeaderBase`'s `$attrs`.

    `pt-6` matches the body's own top padding below. Same header as
    `PrototypesScreen.vue`, so the title sits at the same height on both.
  -->
  <PageHeader class="border-b-0 pt-6">
    <h1 class="truncate text-2xl-semibold text-ink-gray-8">Settings</h1>
  </PageHeader>

  <!--
    No width cap here. App.vue already centres the column at 940px, and a second
    cap of `max-w-4xl` (896px) stopped the body 44px short of the header border
    above it (problem 3.8).
  -->
  <div class="px-3 pb-10 pt-6 sm:px-5">
    <section>
      <h2 class="text-lg-semibold text-ink-gray-8">Agent connection</h2>
      <p class="mt-1 text-p-sm text-ink-gray-7">
        Paste this prompt into your agent session. The agent sets Sketch up by
        itself.
      </p>

      <div class="mt-4 rounded-6 border border-outline-gray-1 p-5">
        <!--
          Fixed height, so Show and Hide swapping labels cannot move the block.
          The actions sit above the code, never over it: the block wraps, so
          text reaches the top-right corner a floating button would cover
          (problem 3.2).
        -->
        <div class="flex h-7 items-center justify-between gap-3">
          <p class="min-w-0 truncate text-p-sm text-ink-gray-8">Setup prompt</p>
          <div class="flex shrink-0 items-center gap-2">
            <Button
              :icon-left="revealed ? 'lucide-eye-off' : 'lucide-eye'"
              :label="revealed ? 'Hide' : 'Show'"
              @click="revealed = !revealed"
            />
            <!--
              Disabled until the token lands. A copy sent early carries the
              literal `<token>` placeholder, and the agent then writes a config
              that fails with a 401 the user cannot explain.
            -->
            <Button
              :disabled="!token"
              icon-left="lucide-copy"
              label="Copy"
              @click="copy(fill(SETUP_PROMPT), 'Prompt copied')"
            />
          </div>
        </div>
        <!--
          Wrap, never scroll sideways: the endpoint line alone runs past the
          box (problem 3.2). `text-p-xs` gives 12px at paragraph leading, so do
          not add a leading class on top (problem 3.9).

          `break-words`, not the `break-all` the old snippets used. Most of this
          block is sentences now, and `break-all` splits an ordinary word at
          whatever character hits the edge. `break-words` leaves words whole and
          still breaks the one string that cannot fit, the token.
        -->
        <pre
          class="mt-2 whitespace-pre-wrap break-words rounded-4 bg-surface-gray-1 p-3 font-mono text-p-xs text-ink-gray-8"
        >{{ shown(SETUP_PROMPT) }}</pre>
        <!--
          Fixed height, so the row does not move when a poll lands. The dot
          carries the state at a glance and the sentence names it, which is the
          payoff the funnel was hiding (problem 2.2).
        -->
        <div class="mt-3 flex h-8 items-center justify-between gap-3">
          <p class="flex min-w-0 items-center gap-2 text-p-xs text-ink-gray-5">
            <span
              aria-hidden="true"
              class="size-2 shrink-0 rounded-full"
              :class="lastUsed ? 'bg-surface-green-7' : 'bg-surface-gray-4'"
            />
            <span class="truncate">
              <template v-if="lastUsed">Last agent request: {{ lastUsed }}</template>
              <template v-else>No agent has connected yet.</template>
            </span>
          </p>
          <Button
            label="Regenerate"
            :loading="regenerate.loading"
            variant="outline"
            @click="askToRegenerate()"
          />
        </div>
      </div>

      <!--
        Two sentences, not a tinted block. The claude.ai warning (problem 3.11)
        was a full amber panel, which is the loudest treatment on the page for
        the rarest client. /help carries the same warning and this paragraph
        links to it. The failure is no longer silent either: paste the prompt
        above into claude.ai and the model answers that it cannot add an MCP
        server, so the reader gets an explanation without this page.
      -->
      <p class="mt-4 text-p-sm text-ink-gray-7">
        A claude.ai custom connector cannot reach Sketch. It sends a URL only,
        with no Authorization header.
      </p>
      <!--
        A plain anchor. /help is a server-rendered page (`sketch/www/help.html`)
        and the SPA router does not declare it, so a RouterLink or a Button
        `route` prop would call `router.push()` and 404 inside the app.
        `AppTopBar.vue` carries the same note for the same reason.
      -->
      <p class="mt-1 text-p-sm text-ink-gray-7">
        Is your connection still quiet?
        <a class="text-ink-blue-link hover:underline" href="/help">Help</a>
        lists what to check.
      </p>
    </section>
  </div>
</template>
