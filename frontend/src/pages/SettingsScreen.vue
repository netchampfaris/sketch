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
import { computed, onMounted, ref } from 'vue'
import {
  Alert,
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
import { agentToken, copyText, method, session } from '../store'
import type { AgentToken } from '../types'

/** One ready-made block per MCP client. */
interface Harness {
  /** Tab value and tab label. */
  value: string
  /** What the user must do. One sentence. */
  help: string
  /** The file to edit. Empty when the snippet is itself a command. */
  paths: string[]
  /** `<token>` and `<endpoint>` are replaced with the live values. */
  snippet: string
  /** The one mistake this client invites. */
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
    note: '`--scope user` is not optional. Without it Claude Code binds Sketch to one directory. Check it with `claude mcp list`.',
  },
  {
    value: 'Codex',
    help: 'Add this to the Codex config file, then restart Codex.',
    paths: ['~/.codex/config.toml'],
    snippet: `[mcp_servers.sketch]
url = "<endpoint>"
http_headers = { Authorization = "Bearer <token>" }`,
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
    note: 'There is no `type` field. Cursor reads the transport from the URL. Do not use the `auth` object, that is OAuth.',
  },
  {
    value: 'VS Code',
    help: 'Run "MCP: Open User Configuration", then add this. VS Code asks for the token the first time and keeps it out of the file, so this is the one block below that carries no token.',
    paths: ['.vscode/mcp.json, or the user configuration file'],
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
    note: 'Write `Authorization:${AUTH_HEADER}` with no space. Claude Desktop, Cursor and Codex all mangle a space inside `args`.',
  },
  {
    value: 'Gemini CLI',
    help: 'Run this once.',
    paths: [],
    snippet:
      'gemini mcp add -s user -t http -H "Authorization: Bearer <token>" sketch <endpoint>',
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
    note: 'The key is `serverUrl`, not `url`.',
  },
]

const client = ref(harnesses[0].value)
/** The token reads as bullets until the user asks for it (problem C6). */
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

onMounted(() => agentToken.reload())

const token = computed(() => agentToken.data?.token ?? '')
const endpoint = computed(() => agentToken.data?.endpoint ?? '')
const username = computed(() => session.data?.username ?? '')

/**
 * The connection state. `last_used` is stamped only by a good token on /mcp,
 * so it is the one honest signal that an agent arrived (plan v2, step 1.5).
 * Both replies may carry it, and an older reply carries neither, so read it
 * defensively and fall back to "not yet".
 */
const lastUsed = computed(
  () => agentToken.data?.last_used_pretty || session.data?.last_used_pretty || '',
)

/** Put the live token and endpoint into a snippet. */
function fill(text: string): string {
  let out = text
  if (endpoint.value) out = out.split('<endpoint>').join(endpoint.value)
  if (token.value) out = out.split('<token>').join(token.value)
  return out
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

async function copy(text: string, done: string): Promise<void> {
  await copyText(text)
  toast.success(done)
}
</script>

<template>
  <PageHeader>
    <div class="min-w-0">
      <h1 class="truncate text-lg font-semibold text-ink-gray-8">Settings</h1>
      <p class="text-xs text-ink-gray-5">Account and connection</p>
    </div>
  </PageHeader>

  <div class="max-w-4xl px-3 pb-10 pt-6 sm:px-5">
    <section>
      <h2 class="text-xl font-semibold text-ink-gray-8">Agent connection</h2>
      <p class="mt-1 text-p-sm text-ink-gray-5">
        Your agent talks to Sketch over MCP. Copy the token, then paste one block
        below into your client.
      </p>

      <div class="mt-5 rounded-6 border border-outline-gray-1 p-5">
        <FormControl
          class="[&_input]:font-mono"
          description="One user, one token. Anyone who holds it can write your prototypes."
          label="Token"
          readonly
          :model-value="token"
          :type="revealed ? 'text' : 'password'"
        />
        <!-- Fixed height, so the line does not move when the state arrives. -->
        <p class="mt-2 h-5 text-p-xs text-ink-gray-5">
          <template v-if="lastUsed">Last agent request: {{ lastUsed }}</template>
          <template v-else>No agent has connected yet.</template>
        </p>
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

      <h3 class="mt-8 text-lg font-semibold text-ink-gray-8">Set up your client</h3>
      <p class="mt-1 text-p-sm text-ink-gray-5">
        Every block below already holds your token and your endpoint.
      </p>

      <!--
        A side rail, not a strip. Eight clients across the top crowd the line
        and leave the panel a wide, short box. The rail is eight rows high, so
        it also carries most of the reserve below.
      -->
      <Tabs v-model="client" class="mt-4 flex gap-6" vertical>
        <TabList class="w-40 shrink-0">
          <TabTrigger
            v-for="item in harnesses"
            :key="item.value"
            :label="item.value"
            :value="item.value"
          />
        </TabList>
        <!--
          The panels run 151px to 331px. The rail is 250px, so most of that
          range is already absorbed. The min-height covers the rest, and the
          section keeps one height whichever client is picked.
        -->
        <TabPanel
          v-for="item in harnesses"
          :key="item.value"
          class="min-h-[22.6rem] min-w-0 flex-1"
          :value="item.value"
        >
          <p class="text-p-sm text-ink-gray-7">{{ item.help }}</p>
          <p
            v-for="path in item.paths"
            :key="path"
            class="mt-1 font-mono text-p-xs text-ink-gray-5"
          >
            {{ path }}
          </p>
          <div class="mt-3 flex justify-end">
            <Button
              icon-left="lucide-copy"
              label="Copy"
              @click="copy(fill(item.snippet), 'Copied')"
            />
          </div>
          <pre
            class="mt-2 overflow-x-auto rounded-4 bg-surface-gray-1 p-3 text-xs text-ink-gray-8"
          >{{ fill(item.snippet) }}</pre>
          <p class="mt-3 text-p-xs text-ink-gray-5">{{ item.note }}</p>
        </TabPanel>
      </Tabs>

      <Alert
        class="mt-6"
        description="A claude.ai custom connector takes a URL only. It cannot send the Authorization header Sketch needs. Sketch will support claude.ai when OAuth ships. Use Claude Code, Codex, OpenCode, Cursor, VS Code, Claude Desktop, Gemini CLI or Windsurf today."
        theme="amber"
        title="claude.ai connectors do not work yet"
      />

      <p class="mt-6 text-p-sm text-ink-gray-5">
        After setup, ask the agent to list your prototypes. If the token is wrong,
        Sketch answers with JSON that names the mistake.
      </p>
    </section>

    <section class="mt-10">
      <h2 class="text-xl font-semibold text-ink-gray-8">Profile</h2>
      <p class="mt-1 text-p-sm text-ink-gray-5">
        This name is in every public prototype link.
      </p>
      <div class="mt-5 max-w-md">
        <FormControl
          description="3–30 characters. Use lowercase letters, numbers, and hyphens. Start with a letter."
          label="Username"
          readonly
          :model-value="username"
        />
        <p class="mt-2 text-p-xs text-ink-gray-5">
          Set at signup and frozen after it, because a shared link must never point
          at somebody else.
        </p>
      </div>
      <div class="mt-5 max-w-md">
        <FormControl
          label="Email"
          :model-value="session.data?.user ?? ''"
          readonly
        />
      </div>
    </section>
  </div>
</template>
