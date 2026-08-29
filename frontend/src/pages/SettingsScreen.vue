<script setup lang="ts">
/**
 * Settings: one scroll, two sections (plan v2, step 2.3).
 *
 * Agent connection comes first, then Profile, because connecting an agent is
 * why anyone opens this page. The local nav column and the `?tab=` query are
 * gone. Nothing reads the query now, so an old `/settings?tab=agent` link
 * still lands here and does nothing.
 *
 * Agent connection is one token, not a token list. One user, one token.
 */
import { computed, onMounted, ref, watch } from 'vue'
import {
  Button,
  FormControl,
  PageHeader,
  TabList,
  TabPanel,
  TabTrigger,
  Tabs,
  dialog,
  toast,
  useCall,
} from 'frappe-ui'
import { usePoll } from '../poll'
import { agentToken, copyText, method, session } from '../store'
import type { AgentToken } from '../types'

/** One ready-made block per MCP client. */
interface Harness {
  /** Tab value and tab label. */
  value: string
  /** What the user must do. One sentence. Backticks render as code. */
  help: string
  /** The file to edit. Empty when the snippet is itself a command. */
  paths: string[]
  /** `<token>` and `<endpoint>` are replaced with the live values. */
  snippet: string
  /**
   * True when the snippet is a whole config file rather than a fragment.
   *
   * A user who already runs MCP servers loses every one of them by pasting
   * such a block over the file, so those panels carry a merge line (problem
   * 3.4). Codex is false on purpose: its snippet is a TOML section, and a
   * section appends instead of replacing.
   */
  merge: boolean
  /** The one mistake this client invites. Backticks render as code. */
  note: string
}

/**
 * Every snippet is verified against the vendor's own documentation
 * (.scratch/sketch-onboarding/harnesses.md). The top-level key is the number
 * one setup failure, so each snippet carries its own: VS Code uses `servers`,
 * OpenCode uses `mcp`, Codex uses `mcp_servers`, the rest use `mcpServers`.
 *
 * One data structure, so the eight panels share one piece of markup.
 *
 * VS Code is the one snippet that does not carry the live token. It reads the
 * token from a VS Code input on purpose, so the token never lands in a file.
 */
const harnesses: Harness[] = [
  {
    value: 'Claude Code',
    help: 'Run this once. It adds Sketch to every project on this machine.',
    paths: [],
    snippet:
      'claude mcp add --transport http --scope user sketch <endpoint> --header "Authorization: Bearer <token>"',
    merge: false,
    note: '`--scope user` is not optional. Without it Claude Code binds Sketch to one directory. Check it with `claude mcp list`.',
  },
  {
    value: 'Codex',
    help: 'Add this to the Codex config file, then restart Codex.',
    paths: ['~/.codex/config.toml'],
    snippet: `[mcp_servers.sketch]
url = "<endpoint>"
http_headers = { Authorization = "Bearer <token>" }`,
    merge: false,
    note: '`codex mcp add` has no header flag, so edit the file by hand.',
  },
  {
    value: 'OpenCode',
    help: 'Add this to the OpenCode config file, then restart OpenCode.',
    paths: ['~/.config/opencode/opencode.json'],
    snippet: `{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "sketch": {
      "type": "remote",
      "url": "<endpoint>",
      "enabled": true,
      "oauth": false,
      "headers": { "Authorization": "Bearer <token>" }
    }
  }
}`,
    merge: true,
    note: 'The type is `remote`, not `http`. Keep `oauth` false, or a 401 starts an OAuth flow instead of failing cleanly.',
  },
  {
    value: 'Cursor',
    help: 'Add this to the Cursor config file.',
    paths: ['~/.cursor/mcp.json'],
    snippet: `{
  "mcpServers": {
    "sketch": {
      "url": "<endpoint>",
      "headers": { "Authorization": "Bearer <token>" }
    }
  }
}`,
    merge: true,
    note: 'There is no `type` field. Cursor reads the transport from the URL. Do not use the `auth` object, that is OAuth.',
  },
  {
    value: 'VS Code',
    help: 'Run "MCP: Open User Configuration" and add this there, or add it to a workspace file. VS Code asks for the token the first time and keeps it out of the file, so this block carries no token.',
    paths: ['.vscode/mcp.json'],
    snippet: `{
  "inputs": [
    { "type": "promptString", "id": "sketch-token", "description": "Sketch MCP token", "password": true }
  ],
  "servers": {
    "sketch": {
      "type": "http",
      "url": "<endpoint>",
      "headers": { "Authorization": "Bearer \${input:sketch-token}" }
    }
  }
}`,
    merge: true,
    note: 'The key is `servers`, not `mcpServers`. VS Code is the odd one out.',
  },
  {
    value: 'Claude Desktop',
    help: 'Claude Desktop reads stdio servers only, so it needs the mcp-remote bridge. Add this, then restart Claude Desktop. Node 18 or newer is required.',
    paths: [
      'macOS: ~/Library/Application Support/Claude/claude_desktop_config.json',
      'Windows: %APPDATA%\\Claude\\claude_desktop_config.json',
    ],
    snippet: `{
  "mcpServers": {
    "sketch": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "<endpoint>", "--transport", "http-only",
               "--header", "Authorization:\${AUTH_HEADER}"],
      "env": { "AUTH_HEADER": "Bearer <token>" }
    }
  }
}`,
    merge: true,
    note: 'Write `Authorization:${AUTH_HEADER}` with no space. Claude Desktop, Cursor and Codex all mangle a space inside `args`.',
  },
  {
    value: 'Gemini CLI',
    help: 'Run this once.',
    paths: [],
    snippet:
      'gemini mcp add -s user -t http -H "Authorization: Bearer <token>" sketch <endpoint>',
    merge: false,
    note: 'The scope defaults to `project`, so pass `-s user`. Older documents say to use `httpUrl`; that field is deprecated.',
  },
  {
    value: 'Windsurf',
    help: 'Add this to the Windsurf config file.',
    paths: ['~/.codeium/windsurf/mcp_config.json'],
    snippet: `{
  "mcpServers": {
    "sketch": {
      "serverUrl": "<endpoint>",
      "headers": { "Authorization": "Bearer <token>" }
    }
  }
}`,
    merge: true,
    note: 'The key is `serverUrl`, not `url`.',
  },
]

const client = ref(harnesses[0].value)

/**
 * The token reads as bullets until the user asks for it (problem C6).
 *
 * One toggle drives the field and every snippet (problem 3.3). A masked field
 * above a clear-text block was false comfort: the token was on screen the
 * whole time in a screen share or a screenshot.
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
const username = computed(() => session.data?.username ?? '')

/**
 * The mask is the token's own length, so revealing it cannot rewrap a block
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

/**
 * Its own flag, not `agentToken.loading`: that one flips on every poll tick,
 * so the button would spin every five seconds without anybody pressing it.
 */
const testing = ref(false)

/**
 * Test connection re-reads the state. It never calls /mcp itself, because a
 * browser request carrying the token would stamp `last_used` and make the page
 * report a connection the user's agent never made.
 */
async function testConnection(): Promise<void> {
  testing.value = true
  await agentToken.reload()
  testing.value = false
  if (agentToken.error) {
    toast.error('Could not reach Sketch. Try again.')
    return
  }
  if (lastUsed.value) {
    toast.success(`Your agent is connected. Last request: ${lastUsed.value}`)
    return
  }
  toast.info(
    'No agent has called Sketch yet. Set up your client below, then ask it to list your prototypes.',
  )
}

/** Put the live token and endpoint into a snippet. This is what Copy sends. */
function fill(text: string): string {
  let out = text
  if (endpoint.value) out = out.split('<endpoint>').join(endpoint.value)
  if (token.value) out = out.split('<token>').join(token.value)
  return out
}

/**
 * What a block shows. Copy calls `fill`, so a masked block still puts the real
 * token on the clipboard.
 */
function shown(text: string): string {
  const filled = fill(text)
  if (revealed.value || !token.value) return filled
  return filled.split(token.value).join(maskedToken.value)
}

/**
 * Split a line on backticks, so the template can draw the odd runs as `<code>`
 * (problem 3.10). The source strings keep their markdown, which is how they
 * read in a diff, and the page never prints a raw backtick.
 */
function runs(text: string): { text: string; code: boolean }[] {
  return text
    .split('`')
    .map((part, index) => ({ text: part, code: index % 2 === 1 }))
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
      'Every agent that holds the old token stops working at once. You must paste the new token into each client again.',
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
  <PageHeader>
    <div class="min-w-0">
      <h1 class="truncate text-2xl-semibold text-ink-gray-8">Settings</h1>
      <p class="text-p-xs text-ink-gray-5">Account and connection</p>
    </div>
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
        Your agent talks to Sketch over MCP. Copy the token, then paste one block
        below into your client.
      </p>

      <div class="mt-4 rounded-6 border border-outline-gray-1 p-5">
        <FormControl
          class="[&_input]:font-mono"
          label="Token"
          readonly
          :model-value="token"
          :type="revealed ? 'text' : 'password'"
        />
        <!--
          A sibling paragraph, not FormControl's `description` prop: that prop
          renders 13px and cannot be retuned, so the card held two helper sizes
          (problem 3.15).
        -->
        <p class="mt-2 text-p-xs text-ink-gray-5">
          One user, one token. Anyone who holds it can write your prototypes.
        </p>
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
          <!--
            Disabled without a token, like "Copy token" and "Copy endpoint"
            below. There is nothing to test until the token lands, and pressing
            it early answered with a toast that read as a failure of the agent
            rather than of the page.
          -->
          <Button
            :disabled="!token"
            icon-left="lucide-refresh-cw"
            label="Test connection"
            :loading="testing"
            @click="testConnection()"
          />
        </div>
        <div class="mt-3 flex flex-wrap justify-end gap-2">
          <Button
            icon-left="lucide-copy"
            label="Copy token"
            :disabled="!token"
            @click="copy(token, 'Token copied')"
          />
          <Button
            :icon-left="revealed ? 'lucide-eye-off' : 'lucide-eye'"
            :label="revealed ? 'Hide' : 'Show'"
            @click="revealed = !revealed"
          />
          <Button
            label="Regenerate"
            :loading="regenerate.loading"
            variant="outline"
            @click="askToRegenerate()"
          />
        </div>
      </div>

      <div class="mt-4 rounded-6 border border-outline-gray-1 p-5">
        <FormControl
          class="[&_input]:font-mono"
          label="Endpoint"
          readonly
          :model-value="endpoint"
        />
        <div class="mt-3 space-y-1 text-p-xs text-ink-gray-5">
          <p>Transport: streamable HTTP. POST only.</p>
          <p>Header name: Authorization</p>
          <p>Header value: Bearer &lt;token&gt;</p>
        </div>
        <div class="mt-3 flex justify-end">
          <Button
            icon-left="lucide-copy"
            label="Copy endpoint"
            :disabled="!endpoint"
            @click="copy(endpoint, 'Endpoint copied')"
          />
        </div>
      </div>

      <h3 class="mt-8 text-base-semibold text-ink-gray-8">Set up your client</h3>
      <p class="mt-1 text-p-sm text-ink-gray-7">
        Every block below already holds your token and your endpoint.
      </p>

      <!--
        A side rail, not a strip. Eight clients across the top crowd the line
        and leave the panel a wide, short box.

        `self-start` stops the flex row from stretching the rail to the panel's
        height, which used to run the rail border 111px past the last tab
        (problem 3.6).
      -->
      <Tabs v-model="client" class="mt-4 flex gap-6" vertical>
        <TabList class="w-40 shrink-0 self-start">
          <!--
            The vertical underline rail marks the active tab with a 1px line
            and an ink step, which read as nothing on screen (problem 3.1).
            These classes are the active nav item from TOKENS, the same pair
            SidebarItem paints: elevation-3 with shadow-sm. `data-state` sits
            on the trigger shell, so the class merges onto the element that
            already carries the state.
          -->
          <TabTrigger
            v-for="item in harnesses"
            :key="item.value"
            class="rounded-4 transition-colors data-[state=active]:bg-surface-elevation-3 data-[state=active]:shadow-sm data-[state=inactive]:hover:bg-surface-gray-2"
            :label="item.value"
            :value="item.value"
          />
        </TabList>
        <!--
          `min-h-80` (320px) holds the panel taller than the 250px rail, so the
          rail never hangs below its own panel. It is a scale value: the old
          reserve was an invented 361.6px and left 225px empty (problem 3.7).

          It is a floor, not a full reserve. The block below wraps now, so a
          panel's height depends on the column width and no static number can
          cover the tallest one. Switching client reflows, which finding 3.7
          allows.
        -->
        <TabPanel
          v-for="item in harnesses"
          :key="item.value"
          class="min-h-80 min-w-0 flex-1"
          :value="item.value"
        >
          <p class="text-p-sm text-ink-gray-7">
            <template v-for="(run, index) in runs(item.help)" :key="index">
              <code
                v-if="run.code"
                class="rounded-1 bg-surface-gray-2 px-1 font-mono text-ink-gray-7"
                >{{ run.text }}</code
              >
              <template v-else>{{ run.text }}</template>
            </template>
          </p>
          <p v-if="item.merge" class="mt-1 text-p-sm text-ink-gray-7">
            Merge the
            <code class="rounded-1 bg-surface-gray-2 px-1 font-mono">sketch</code>
            entry into your existing file. Do not replace it.
          </p>
          <!--
            Paths only. A sentence in this slot rendered as monospace prose
            (problem 3.14); the prose lives in the help line above.
          -->
          <p
            v-for="path in item.paths"
            :key="path"
            class="mt-1 truncate font-mono text-xs text-ink-gray-5"
          >
            {{ path }}
          </p>
          <!--
            The copy action sits above the block, never over it: the block wraps
            now, so text reaches the top-right corner a floating button would
            cover.
          -->
          <div class="mt-3 flex justify-end">
            <Button
              icon-left="lucide-copy"
              label="Copy"
              @click="copy(fill(item.snippet), 'Copied')"
            />
          </div>
          <!--
            Wrap, never scroll sideways. The Claude Code line measured 1241px
            against a 672px box, so the `Bearer <token>` tail was off screen
            (problem 3.2). `text-p-xs` gives 12px at paragraph leading, which
            the 12-line JSON blocks need (problem 3.9).
          -->
          <pre
            class="mt-2 whitespace-pre-wrap break-all rounded-4 bg-surface-gray-1 p-3 font-mono text-p-xs text-ink-gray-8"
          >{{ shown(item.snippet) }}</pre>
          <p class="mt-3 text-p-xs text-ink-gray-5">
            <template v-for="(run, index) in runs(item.note)" :key="index">
              <code
                v-if="run.code"
                class="rounded-1 bg-surface-gray-2 px-1 font-mono text-ink-gray-7"
                >{{ run.text }}</code
              >
              <template v-else>{{ run.text }}</template>
            </template>
          </p>
        </TabPanel>
      </Tabs>

      <!--
        Built from tokens, not `Alert`. Alert's container is always gray, so
        `theme="amber"` coloured the 16px icon and nothing else, and the warning
        read as a note (problem 3.11). This is the one tinted block on the page.
      -->
      <div
        class="mt-4 flex gap-2 rounded-6 border border-outline-amber-3 bg-surface-amber-2 p-3 text-ink-amber-7"
      >
        <span class="lucide-triangle-alert mt-0.5 size-4 shrink-0" aria-hidden="true" />
        <div class="min-w-0">
          <p class="text-base-medium">claude.ai connectors do not work yet</p>
          <p class="mt-1 text-p-sm">
            A claude.ai custom connector takes a URL only. It cannot send the
            Authorization header Sketch needs. Sketch will support claude.ai when
            OAuth ships. Use Claude Code, Codex, OpenCode, Cursor, VS Code, Claude
            Desktop, Gemini CLI or Windsurf today.
          </p>
        </div>
      </div>

      <p class="mt-4 text-p-sm text-ink-gray-7">
        After setup, ask the agent to list your prototypes. If the token is wrong,
        Sketch answers with JSON that names the mistake.
      </p>
      <!--
        The viewer already polls and reloads itself while the agent writes
        (runtime/viewer/boot.js:116-166). Nothing said so, and users closed and
        reopened the tab after every agent turn (problem 3.17).
      -->
      <p class="mt-1 text-p-sm text-ink-gray-7">
        Keep a prototype open while you work. It reloads itself as your agent
        writes.
      </p>
    </section>

    <section class="mt-10">
      <h2 class="text-lg-semibold text-ink-gray-8">Profile</h2>
      <p class="mt-1 text-p-sm text-ink-gray-7">
        This name is in every public prototype link.
      </p>
      <!--
        The same card shell as the connection cards above. The fields were
        `max-w-md` under 856px cards, so the right edge zig-zagged down the page
        (problem 3.18).
      -->
      <div class="mt-4 rounded-6 border border-outline-gray-1 p-5">
        <FormControl label="Username" readonly :model-value="username" />
        <p class="mt-2 text-p-xs text-ink-gray-5">
          3–30 characters. Use lowercase letters, numbers, and hyphens. Start with
          a letter.
        </p>
        <p class="mt-1 text-p-xs text-ink-gray-5">
          Set at signup and frozen after it, because a shared link must never point
          at somebody else.
        </p>
      </div>
      <div class="mt-4 rounded-6 border border-outline-gray-1 p-5">
        <FormControl
          label="Email"
          :model-value="session.data?.user ?? ''"
          readonly
        />
      </div>
    </section>
  </div>
</template>
