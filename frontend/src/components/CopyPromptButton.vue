<script setup lang="ts">
/**
 * "Copy setup prompt": step 1 of the setup, on the setup block and on About.
 *
 * It reads the token from `agentToken` and never loads it: the page that
 * draws it does, so the token is minted only where the setup is on screen.
 */
import { computed, ref } from 'vue'
import { Button } from 'frappe-ui'
import { connected, waiting } from '../agents'
import { fillPrompt } from '../setupPrompt'
import { agentToken, copyText } from '../store'

const token = computed(() => agentToken.data?.token ?? '')

const copied = ref(false)
const button = ref<{ $el: HTMLElement } | null>(null)

/** The idle label's width, held while "Copied" shows, so the button never changes size under the pointer. */
const width = ref<number | undefined>()
let copiedTimer: number | undefined

/**
 * "Copied" holds for two seconds, then the status turns to waiting. `copyText`
 * shows its own error toast and rethrows (store.ts), so a refused copy changes
 * nothing here.
 */
async function copy(): Promise<void> {
  try {
    await copyText(fillPrompt(token.value, agentToken.data?.endpoint ?? ''))
  } catch {
    return
  }
  if (!copied.value) width.value = button.value?.$el.offsetWidth
  copied.value = true
  window.clearTimeout(copiedTimer)
  copiedTimer = window.setTimeout(() => {
    copied.value = false
    if (!connected.value) waiting.value = true
  }, 2000)
}
</script>

<template>
  <!--
    Disabled until the token lands. A copy sent early carries the literal
    `<token>` placeholder, and the agent then writes a config that fails with
    a 401 the user cannot explain.
  -->
  <Button
    ref="button"
    :disabled="!token"
    :icon-left="copied ? 'lucide-check' : 'lucide-copy'"
    :label="copied ? 'Copied' : 'Copy setup prompt'"
    theme="gray"
    :style="{ minWidth: width && `${width}px` }"
    variant="subtle"
    @click="copy"
  />
  <!-- The label change alone is not announced, so the live region says it. -->
  <span aria-live="polite" class="sr-only">{{ copied ? 'Copied' : '' }}</span>
</template>
