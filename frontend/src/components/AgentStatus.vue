<script setup lang="ts">
/**
 * The connection's status line, with "Reset token…" in a ⋯ menu on its right.
 *
 * It tops the setup block (`AgentConnect.vue`), and stands alone over the
 * starter requests on an empty gallery whose agent already connected.
 *
 * The dot carries the state at a glance and the sentence names it: gray and
 * still before Copy, gray and pulsing while Sketch waits for the agent's first
 * request, green once it arrived. The row is a fixed h-7, so a poll landing
 * never moves what sits under it.
 */
import { computed } from 'vue'
import { Button, Dropdown, dialog, toast, useCall } from 'frappe-ui'
import { clients, connected, justConnected, lastUsedPretty, listNames, waiting } from '../agents'
import { fillPrompt } from '../setupPrompt'
import { agentToken, errorText, method, session } from '../store'
import type { AgentToken } from '../types'

const names = computed(() => clients.value.map((client) => client.name))

const text = computed(() => {
  if (connected.value) {
    // The moment it connects, the app is the news; "used just now" would only repeat it.
    const parts = ['Connected', names.value.join(', ')]
    if (!justConnected.value && lastUsedPretty.value) parts.push(`used ${lastUsedPretty.value}`)
    return parts.filter(Boolean).join(' · ')
  }
  return waiting.value ? 'Waiting for your agent…' : 'Not connected yet'
})

/** A token exists once anything minted one; before that there is nothing to reset. */
const hasToken = computed(() => Boolean(agentToken.data?.token) || Boolean(session.data?.has_token))

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
 */
function askToReset(): void {
  const apps = names.value.length ? listNames(names.value) : 'Every app you connected'
  dialog.danger({
    title: 'Reset token?',
    message: `${apps} will stop working until you paste the new prompt into them.`,
    confirmLabel: 'Reset token',
    onConfirm: reset,
  })
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
  let fresh: AgentToken
  try {
    fresh = await regenerate.submit()
  } catch (error) {
    toast.error(errorText(error))
    return
  }
  justConnected.value = false
  waiting.value = true
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
  <div class="flex h-7 items-center justify-between gap-3">
    <p class="flex min-w-0 items-center gap-2 text-p-sm" :class="connected ? 'text-ink-gray-8' : 'text-ink-gray-5'">
      <span
        aria-hidden="true"
        class="size-2 shrink-0 rounded-full"
        :class="
          connected
            ? 'bg-surface-green-7'
            : waiting
              ? 'animate-pulse bg-surface-gray-5 motion-reduce:animate-none'
              : 'bg-surface-gray-4'
        "
      />
      <!-- Polite, so a screen reader hears "Connected" arrive without a focus move. -->
      <span aria-live="polite" class="truncate" :title="text">{{ text }}</span>
    </p>
    <Dropdown v-if="hasToken" align="end" :options="menu">
      <Button icon="lucide-ellipsis" label="Connection options" theme="gray" variant="ghost" />
    </Dropdown>
  </div>
</template>
