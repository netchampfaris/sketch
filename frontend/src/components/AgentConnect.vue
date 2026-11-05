<script setup lang="ts">
/**
 * Connect your agent: the one setup block, on the empty gallery and on
 * Settings (decision 87).
 *
 * Top to bottom, 24px apart: the status line, three steps whose first is the
 * Copy button itself, and the prompt folded away behind "See what your agent
 * will read". One prompt works in every agent app (`setupPrompt.ts`), so the
 * block never asks which one the user has.
 *
 * Mounting it reads `get_agent_token`, which mints the token on first read.
 * That is the point of this block, so it mints only where it is drawn: on
 * Settings, and on an empty gallery whose agent never connected.
 *
 * The token is never on screen unless the prompt is unfolded and Show is on.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { Button, ErrorMessage } from 'frappe-ui'
import AgentStatus from './AgentStatus.vue'
import { connected, waiting } from '../agents'
import { usePoll } from '../poll'
import { fillPrompt } from '../setupPrompt'
import { agentToken, copyText } from '../store'

const token = computed(() => agentToken.data?.token ?? '')
const prompt = computed(() => fillPrompt(token.value, agentToken.data?.endpoint ?? ''))

/** A failed first read with no token in hand. A failed poll after that keeps the block as it was. */
const failed = computed(() => Boolean(agentToken.error) && !token.value)

const copied = ref(false)
let copiedTimer: number | undefined

/**
 * "Copied" holds for two seconds, then the status turns to waiting. `copyText`
 * shows its own error toast and rethrows (store.ts), so a refused copy changes
 * nothing here.
 */
async function copy(): Promise<void> {
  try {
    await copyText(prompt.value)
  } catch {
    return
  }
  copied.value = true
  window.clearTimeout(copiedTimer)
  copiedTimer = window.setTimeout(() => {
    copied.value = false
    if (!connected.value) waiting.value = true
  }, 2000)
}

const open = ref(false)
const revealed = ref(false)

/** The mask is the token's own length, so revealing it cannot rewrap the block. */
const shown = computed(() =>
  revealed.value || !token.value ? prompt.value : prompt.value.split(token.value).join('•'.repeat(token.value.length)),
)

/**
 * Watch for the agent's first request (`poll.ts`, the loop the gallery uses
 * too). It retires on the connection: after that `last_used` only ages.
 *
 * A read finds the connection already there when the session landed after
 * the loop armed, which is every direct load. It then returns at once, and
 * the loop retires instead of reading the token a second time.
 */
const poll = usePoll(
  async () => {
    if (connected.value) return
    await agentToken.reload()
    // `reload()` resolves on a failed request, so the error ref is the only signal.
    return !agentToken.error
  },
  { interval: 5000, done: () => connected.value },
)

/** A reset clears the connection on the server; the retired loop cannot see that, so this arms it again. */
watch(connected, (value) => {
  if (!value) poll.restart()
})

onMounted(() => agentToken.reload())
</script>

<template>
  <div>
    <AgentStatus />

    <ErrorMessage
      v-if="failed"
      class="mt-6"
      message="Couldn't load your setup prompt. Reload the page to try again."
    />

    <template v-else>
      <!--
        Step 1 is the Copy button itself.
      -->
      <ol class="mt-6 space-y-3 text-p-sm text-ink-gray-7">
        <li class="flex items-center gap-2">
          <span class="w-3 shrink-0 tabular-nums text-ink-gray-5">1</span>
          <!--
            Disabled until the token lands. A copy sent early carries the
            literal `<token>` placeholder, and the agent then writes a config
            that fails with a 401 the user cannot explain.
          -->
          <Button
            :disabled="!token"
            :icon-left="copied ? 'lucide-check' : 'lucide-copy'"
            :label="copied ? 'Copied' : 'Copy setup prompt'"
            theme="gray"
            variant="subtle"
            @click="copy"
          />
        </li>
        <li class="flex gap-2"><span class="w-3 shrink-0 tabular-nums text-ink-gray-5">2</span>Paste it into your agent.</li>
        <li class="flex gap-2">
          <span class="w-3 shrink-0 tabular-nums text-ink-gray-5">3</span>
          Start building there, and watch it live here.
        </li>
      </ol>

      <!-- Closed by default: the prompt is for the agent, and the token sits inside it. -->
      <div class="mt-6">
        <Button :aria-expanded="open" class="-ml-2" theme="gray" variant="ghost" @click="open = !open">
          <span class="text-p-sm text-ink-gray-6">See what your agent will read</span>
          <template #suffix>
            <span
              aria-hidden="true"
              class="size-3.5 text-ink-gray-6"
              :class="open ? 'lucide-chevron-up' : 'lucide-chevron-down'"
            />
          </template>
        </Button>
        <div v-if="open" class="mt-2">
          <!--
            Wrap, never scroll sideways: the endpoint line alone runs past the
            box. `break-words` leaves words whole and still breaks the one
            string that cannot fit, the token. Show and Hide sit above the
            text, never over it, so no line hides under the button; -mr-2
            lines the label up with the box's right edge.
          -->
          <div class="flex h-7 items-center justify-between gap-3">
            <p class="text-p-sm text-ink-gray-5">Setup prompt</p>
            <!-- The text goes in the slot, not `label`: Button names itself from `label` over `aria-label`. -->
            <Button
              :aria-label="revealed ? 'Hide token' : 'Show token'"
              class="-mr-2"
              :icon-left="revealed ? 'lucide-eye-off' : 'lucide-eye'"
              theme="gray"
              variant="ghost"
              @click="revealed = !revealed"
            >
              {{ revealed ? 'Hide' : 'Show' }}
            </Button>
          </div>
          <pre
            class="mt-2 whitespace-pre-wrap break-words rounded-4 bg-surface-gray-1 p-3 font-mono text-p-xs text-ink-gray-8"
          >{{ shown }}</pre>
        </div>
      </div>
    </template>
  </div>
</template>
