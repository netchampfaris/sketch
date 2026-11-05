/**
 * The agent apps Sketch names, and the connection state every screen reads.
 *
 * The feed hero floats the apps' logos (decision 86). The setup block
 * (`AgentConnect.vue`, decision 87) lets the user pick theirs, which changes
 * only the "where to paste" line: the setup prompt is one prompt for every app.
 *
 * The logos are the apps' own marks, monochrome, from the SVGs in
 * `assets/agents/` (each file names its source).
 */
import { computed, ref, watch } from 'vue'
import { toast } from 'frappe-ui'
import claude from './assets/agents/claude.svg?raw'
import codex from './assets/agents/codex.svg?raw'
import copilot from './assets/agents/copilot.svg?raw'
import cursor from './assets/agents/cursor.svg?raw'
import vscode from './assets/agents/vscode.svg?raw'
import windsurf from './assets/agents/windsurf.svg?raw'
import { agentToken, session } from './store'

export interface HeroApp {
  name: string
  logo: string
}

/**
 * The apps on the feed hero, in the order they float. claude.ai is not one: it
 * cannot connect. Nor is OpenCode: its mark is a plain frame, and at 28px it
 * read as an empty box, not an app.
 */
export const heroApps: HeroApp[] = [
  { name: 'Claude Code', logo: claude },
  { name: 'Cursor', logo: cursor },
  { name: 'Codex', logo: codex },
  { name: 'GitHub Copilot in VS Code', logo: copilot },
  { name: 'Windsurf', logo: windsurf },
]

export interface PickerApp {
  id: string
  name: string
  /** A brand mark, or a lucide class for the two rows that have no single brand. */
  logo?: string
  icon?: string
  /** Where to paste the prompt. Null for an app that cannot connect. */
  hint: string | null
}

export const pickerApps: PickerApp[] = [
  { id: 'claude-code', name: 'Claude Code', logo: claude, hint: 'Paste it into Claude Code.' },
  { id: 'cursor', name: 'Cursor', logo: cursor, hint: 'Paste it into Cursor.' },
  { id: 'codex', name: 'Codex', logo: codex, hint: 'Paste it into Codex.' },
  { id: 'vscode', name: 'VS Code', logo: vscode, hint: 'Paste it into Copilot Chat in VS Code.' },
  {
    id: 'other',
    name: 'Other',
    icon: 'lucide-bot',
    hint: "Paste it into your agent's chat. Any agent that can add an MCP server works.",
  },
  // A claude.ai custom connector sends a URL only, with no Authorization
  // header, so it cannot reach /mcp. The row says so where the user looks.
  { id: 'claude-ai', name: 'claude.ai', icon: 'lucide-globe', hint: null },
]

const APP_KEY = 'sketch.agent-app'

function storedApp(): string {
  try {
    return window.localStorage.getItem(APP_KEY) ?? ''
  } catch {
    return ''
  }
}

/** The picked app's id. Remembered per browser; Claude Code until the user picks. */
export const pickedApp = ref(pickerApps.some((app) => app.id === storedApp()) ? storedApp() : 'claude-code')

export function pickApp(id: string): void {
  pickedApp.value = id
  try {
    window.localStorage.setItem(APP_KEY, id)
  } catch {
    // Not remembered. The picker opens on Claude Code next visit.
  }
}

/**
 * The connection, from the freshest reply there is.
 *
 * `agentToken` once it has loaded a token (Settings and the setup block read
 * it, and polling refreshes it), else `session`, which every screen has from
 * boot. Never both mixed: after a reset the token reply says "not connected"
 * while the boot session still holds the old stamp.
 */
const source = computed(() => (agentToken.data?.token ? agentToken.data : session.data))

/** True once an agent has called /mcp with a good token. `last_used` is the one honest signal. */
export const connected = computed(() => Boolean(source.value?.last_used))

export const clients = computed(() => source.value?.clients ?? [])

/** "5 days ago": the newest app's last request, or the token's own stamp for an older connection with no app on record. */
export const lastUsedPretty = computed(
  () => clients.value[0]?.last_used_pretty || source.value?.last_used_pretty || '',
)

/**
 * True after Copy or a reset, until the agent arrives. Module state, so it
 * holds when the user moves between the gallery and Settings.
 */
export const waiting = ref(false)

/** True when this tab saw the connection happen, so the status line skips "used just now". */
export const justConnected = ref(false)

/**
 * The arrival, seen from this tab. It counts only after a token reply here
 * said "not connected yet", so a page that loads already connected never
 * announces it.
 *
 * Module scope, not the setup block's: the gallery swaps that block out the
 * moment the connection lands, before a watcher inside it could run.
 *
 * `last_used` is stamped when the request authenticates and the app's name a
 * moment later in the same request, so a read can land between the two. The
 * toast then waits for one more read to name the app.
 */
let sawUnconnected = false
let unnamed = false
watch(
  () => agentToken.data,
  (reply) => {
    if (!reply?.token) return
    if (!reply.last_used) {
      sawUnconnected = true
      unnamed = false
      return
    }
    if (unnamed) {
      unnamed = false
      announce(reply.clients?.[0]?.name)
      return
    }
    if (!sawUnconnected) return
    sawUnconnected = false
    justConnected.value = true
    waiting.value = false
    if (reply.clients?.length) return announce(reply.clients[0].name)
    unnamed = true
    window.setTimeout(() => agentToken.reload(), 3000)
  },
)

function announce(app?: string): void {
  toast.success(app ? `Connected · ${app}` : 'Connected')
}

/** "Claude Code", "Claude Code and Cursor", "Claude Code, Cursor and Codex". */
export function listNames(names: string[]): string {
  if (names.length < 2) return names[0] ?? ''
  return `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`
}
