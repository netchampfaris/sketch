<script setup lang="ts">
/**
 * Settings: the same app sidebar and header, a narrow local navigation column
 * and a content column (spec 11).
 *
 * Agent connection is one token, not a token list. One user, one token.
 */
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Button, FormControl, PageHeader, toast, useCall } from 'frappe-ui'
import { agentToken, copyText, method, session } from '../store'
import type { AgentToken } from '../types'

const route = useRoute()
const router = useRouter()

const sections = [
  { key: 'profile', label: 'Profile', icon: 'lucide-user-round' },
  { key: 'agent', label: 'Agent connection', icon: 'lucide-plug-zap' },
]

const active = computed(() => (route.query.tab === 'agent' ? 'agent' : 'profile'))

function show(key: string): void {
  router.replace({ query: key === 'profile' ? {} : { tab: key } })
}

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

const config = computed(() =>
  JSON.stringify(
    {
      mcpServers: {
        sketch: {
          type: 'http',
          url: endpoint.value,
          headers: { Authorization: `Bearer ${token.value}` },
        },
      },
    },
    null,
    2,
  ),
)

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
    <div class="grid gap-8 md:grid-cols-[11rem_minmax(0,1fr)]">
      <nav class="space-y-0.5">
        <Button
          v-for="item in sections"
          :key="item.key"
          class="w-full !justify-start"
          :icon-left="item.icon"
          :label="item.label"
          :variant="active === item.key ? 'subtle' : 'ghost'"
          @click="show(item.key)"
        />
      </nav>

      <section v-if="active === 'profile'">
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

      <section v-else>
        <h2 class="text-xl font-semibold text-ink-gray-8">Agent connection</h2>
        <p class="mt-1 text-p-sm text-ink-gray-5">
          Your agent sends this token to the Sketch MCP endpoint. One user, one token.
        </p>

        <div class="mt-5 rounded-6 border border-outline-gray-1 p-5">
          <FormControl
            class="font-mono"
            label="Token"
            :model-value="token"
            readonly
          />
          <div class="mt-3 flex justify-end gap-2">
            <Button
              icon-left="lucide-copy"
              label="Copy token"
              :disabled="!token"
              @click="copy(token, 'Token copied')"
            />
            <Button
              label="Regenerate"
              :loading="regenerate.loading"
              variant="outline"
              @click="regenerate.submit()"
            />
          </div>
        </div>

        <div class="mt-4 rounded-6 bg-surface-gray-1 p-5">
          <div class="flex items-center justify-between gap-3">
            <div class="min-w-0">
              <h3 class="text-base font-medium text-ink-gray-8">Connect endpoint</h3>
              <p class="mt-1 text-p-sm text-ink-gray-5">
                Streamable HTTP. Bearer authentication.
              </p>
            </div>
            <Button
              icon-left="lucide-copy"
              label="Copy config"
              :disabled="!token"
              @click="copy(config, 'Config copied')"
            />
          </div>
          <code
            class="mt-4 block overflow-x-auto rounded-4 bg-surface-base p-3 text-p-sm text-ink-gray-7"
            >{{ endpoint }}</code
          >
        </div>
      </section>
    </div>
  </div>
</template>
