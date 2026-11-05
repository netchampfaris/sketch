<script setup lang="ts">
/**
 * Connect your agent: the one setup block, on the empty gallery and on
 * Settings (decision 87).
 *
 * Top to bottom: the status line, the app picker, one Copy button with three
 * plain steps under it, and the prompt itself folded away behind "See what
 * your agent will read". The picker changes only step 2, "where to paste": the
 * setup prompt is one prompt for every app (`setupPrompt.ts`).
 *
 * Mounting it reads `get_agent_token`, which mints the token on first read.
 * That is the point of this block, so it mints only where it is drawn: on
 * Settings, and on an empty gallery whose agent never connected.
 *
 * The token is never on screen unless the prompt is unfolded and Show is on.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { Button, ErrorMessage } from 'frappe-ui'
import AgentLogo from './AgentLogo.vue'
import AgentStatus from './AgentStatus.vue'
import { connected, pickApp, pickedApp, pickerApps, waiting } from '../agents'
import { usePoll } from '../poll'
import { fillPrompt } from '../setupPrompt'
import { agentToken, copyText } from '../store'

const token = computed(() => agentToken.data?.token ?? '')
const prompt = computed(() => fillPrompt(token.value, agentToken.data?.endpoint ?? ''))

/** A failed first read with no token in hand. A failed poll after that keeps the block as it was. */
const failed = computed(() => Boolean(agentToken.error) && !token.value)

const app = computed(() => pickerApps.find((one) => one.id === pickedApp.value) ?? pickerApps[0])

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
      class="mt-4"
      message="Couldn't load your setup prompt. Reload the page to try again."
    />

    <template v-else>
      <!--
        One row of chips, wrapping on a phone. The six need about 610px, which
        is why the setup column is 620px wide. The choice only changes step 2.
      -->
      <div aria-label="Your agent app" class="mt-4 flex flex-wrap gap-1.5" role="radiogroup">
        <Button
          v-for="one in pickerApps"
          :key="one.id"
          :aria-checked="one.id === app.id"
          role="radio"
          theme="gray"
          :variant="one.id === app.id ? 'subtle' : 'outline'"
          @click="pickApp(one.id)"
        >
          <template #prefix>
            <AgentLogo class="size-4" :icon="one.icon" :svg="one.logo" />
          </template>
          {{ one.name }}
        </Button>
      </div>

      <p v-if="!app.hint" class="mt-5 text-p-sm text-ink-gray-7">
        claude.ai can't connect to Sketch yet. Use Claude Code or Cursor instead.
      </p>

      <template v-else>
        <!--
          Disabled until the token lands. A copy sent early carries the literal
          `<token>` placeholder, and the agent then writes a config that fails
          with a 401 the user cannot explain.
        -->
        <Button
          class="mt-5"
          :disabled="!token"
          :icon-left="copied ? 'lucide-check' : 'lucide-copy'"
          :label="copied ? 'Copied' : 'Copy setup prompt'"
          size="md"
          theme="gray"
          variant="solid"
          @click="copy"
        />
        <ol class="mt-3 space-y-1 text-p-sm text-ink-gray-7">
          <li class="flex gap-2"><span class="w-3 shrink-0 tabular-nums text-ink-gray-5">1</span>Copy the prompt</li>
          <li class="flex gap-2"><span class="w-3 shrink-0 tabular-nums text-ink-gray-5">2</span>{{ app.hint }}</li>
          <li class="flex gap-2">
            <span class="w-3 shrink-0 tabular-nums text-ink-gray-5">3</span>Come back here. This page shows when it's
            connected.
          </li>
        </ol>
      </template>

      <!-- Closed by default: the prompt is for the agent, and the token sits inside it. -->
      <div class="mt-5">
        <Button
          :aria-expanded="open"
          :icon-right="open ? 'lucide-chevron-up' : 'lucide-chevron-down'"
          label="See what your agent will read"
          theme="gray"
          variant="ghost"
          class="-ml-2"
          @click="open = !open"
        />
        <div v-if="open" class="mt-2">
          <!--
            Wrap, never scroll sideways: the endpoint line alone runs past the
            box. `break-words` leaves words whole and still breaks the one
            string that cannot fit, the token. Show and Hide sit above the
            text, never over it, so no line hides under the button.
          -->
          <div class="flex h-7 items-center justify-between gap-3">
            <p class="text-p-sm text-ink-gray-5">Setup prompt</p>
            <Button
              :icon-left="revealed ? 'lucide-eye-off' : 'lucide-eye'"
              :label="revealed ? 'Hide' : 'Show'"
              theme="gray"
              variant="ghost"
              @click="revealed = !revealed"
            />
          </div>
          <pre
            class="mt-2 whitespace-pre-wrap break-words rounded-4 bg-surface-gray-1 p-3 font-mono text-p-xs text-ink-gray-8"
          >{{ shown }}</pre>
        </div>
      </div>
    </template>
  </div>
</template>
