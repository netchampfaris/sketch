<script setup lang="ts">
/**
 * The connection's status line, with "Reset token…" in a ⋯ menu right after it.
 *
 * It tops the setup block (`AgentConnect.vue`), and stands alone over the
 * starter requests on an empty gallery whose agent already connected.
 *
 * The dot carries the state at a glance and the sentence names it: gray and
 * still before Copy, gray and pulsing while Sketch waits for the agent's first
 * request, green once it arrived. The row is at least h-7, so a poll landing
 * never moves what sits under it; on a phone a long line wraps, with the dot
 * and ⋯ on its first line, rather than cutting the apps off.
 */
import { computed, ref } from 'vue'
import { Button, Dropdown, dialog, toast, useCall, type ImperativeDialogAction } from 'frappe-ui'
import { clients, connected, justConnected, lastUsedPretty, listNames, waiting } from '../agents'
import { fillPrompt } from '../setupPrompt'
import { agentToken, errorText, method, session } from '../store'
import type { AgentToken } from '../types'

/** About shows the line alone: no ⋯, since resetting a token is Settings' job. */
const props = defineProps<{ readOnly?: boolean }>()

const names = computed(() => clients.value.map((client) => client.name))

const text = computed(() => {
  if (connected.value) {
    // The moment it connects, the app is the news; "used just now" would only repeat it.
    const used = !justConnected.value && lastUsedPretty.value ? `used ${lastUsedPretty.value}` : ''
    // One app is a short label, "Connected · Claude Code". Several are a sentence, so the apps read as a list.
    if (names.value.length > 1) return [`Connected to ${listNames(names.value)}`, used].filter(Boolean).join(', ')
    return ['Connected', names.value[0], used].filter(Boolean).join(' · ')
  }
  return waiting.value ? 'Waiting for your agent…' : 'Not connected yet'
})

const regenerate = useCall<AgentToken>({
  url: method('regenerate_agent_token'),
  method: 'POST',
  immediate: false,
})

const menu = [{ label: 'Reset token…', icon: 'lucide-rotate-ccw', onClick: askToReset }]

/**
 * A reset breaks every connected app at once, so it asks first, and names the
 * apps it breaks. Returning the call keeps the dialog open until the server
 * answers.
 *
 * The dialog opens on Cancel, the safe answer, and however it closes, focus
 * goes back to ⋯: the menu item that opened it is gone by then.
 */
function askToReset(): void {
  dialog.danger({
    title: 'Reset token?',
    message: names.value.length
      ? `${listNames(names.value)} will stop working until you paste the new prompt into ${names.value.length > 1 ? 'them' : 'it'}.`
      : 'A prompt you already copied will stop working.',
    actions: [
      // `autofocus` falls through to the button, and frappe-ui's Dialog focuses it on open.
      { label: 'Cancel', variant: 'outline', autofocus: true, onClick: refocus } as ImperativeDialogAction,
      { label: 'Reset token', variant: 'solid', theme: 'red', onClick: () => reset().finally(refocus) },
    ],
    onCancel: refocus,
  })
}

const options = ref<{ $el: HTMLElement } | null>(null)

/** Keeps ⋯ after a reset here, so focus has somewhere to return and a second reset stays one click away. */
const wasReset = ref(false)

/** After the dialog has left the page; its focus scope hands focus to the page body on the way out. */
function refocus(): void {
  const started = performance.now()
  const tick = () => {
    if (document.querySelector('[role="dialog"]') && performance.now() - started < 1000) {
      requestAnimationFrame(tick)
      return
    }
    window.setTimeout(() => options.value?.$el.focus())
  }
  requestAnimationFrame(tick)
}

/**
 * The server clears `last_used` and the apps with the token
 * (`sketch_token.regenerate`), so the status goes back to waiting, and the
 * setup block's poll arms again when it sees the connection go.
 *
 * The new prompt goes to the clipboard straight away, since pasting it again
 * is the only next step. The clipboard is written directly, not through
 * `copyText`: a refused copy gets the reset's own message, not a second toast
 * that prints the prompt.
 */
async function reset(): Promise<void> {
  let fresh: AgentToken | null
  try {
    fresh = await regenerate.submit()
  } catch (error) {
    toast.error(errorText(error))
    return
  }
  if (!fresh) return
  justConnected.value = false
  waiting.value = true
  wasReset.value = true
  await Promise.all([agentToken.reload(), session.reload()])
  try {
    await navigator.clipboard.writeText(fillPrompt(fresh.token, fresh.endpoint))
    toast.success('New prompt copied. Paste it into each app again.')
  } catch {
    toast.success('Token reset. Copy the new prompt and paste it into each app again.')
  }
}
</script>

<template>
  <div class="flex min-h-7 w-fit max-w-full items-start gap-2">
    <p class="flex min-w-0 items-start gap-2 py-1 text-p-sm text-pretty" :class="connected ? 'text-ink-gray-8' : 'text-ink-gray-5'">
      <span
        aria-hidden="true"
        class="mt-1.5 size-2 shrink-0 rounded-full"
        :class="
          connected
            ? 'bg-surface-green-7'
            : waiting
              ? 'animate-pulse bg-surface-gray-5 motion-reduce:animate-none'
              : 'bg-surface-gray-4'
        "
      />
      <!-- Polite, so a screen reader hears "Connected" arrive without a focus move. -->
      <span aria-live="polite">{{ text }}</span>
    </p>
    <!-- Only once an app connected: before that, there is nothing a reset would fix. -->
    <Dropdown v-if="!props.readOnly && (connected || wasReset)" align="end" :options="menu">
      <Button ref="options" icon="lucide-ellipsis" label="Connection options" theme="gray" variant="ghost" />
    </Dropdown>
  </div>
</template>
