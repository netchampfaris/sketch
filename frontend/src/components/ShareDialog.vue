<script setup lang="ts">
/**
 * Share: who can add to this prototype, and who can see it.
 *
 * Owner only. The server checks that again on every call (`resolve_owned`),
 * so this dialog never decides who may open it.
 *
 * An invited person's agent adds variants to the owner's prototype, next to
 * the owner's own. It cannot change anything else, and the owner's agent
 * keeps the whole tree. The list below says so in one line while nobody is
 * invited yet, and goes quiet after that.
 *
 * Removing is immediate: it can be undone with one click, so there is no
 * confirm. The variants a removed person made stay in the prototype.
 *
 * The username field matches exactly. Sketch never searches or lists its
 * users, so a name is only ever answered with the person it names or with
 * "No Sketch user called ...".
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import {
  Avatar,
  Button,
  Dialog,
  ErrorMessage,
  FormControl,
  LoadingText,
  Switch,
  toast,
  useCall,
} from 'frappe-ui'
import { copyText, method } from '../store'
import type { Prototype, SharePerson, ShareState } from '../types'

const props = defineProps<{ prototype: Prototype }>()
const open = defineModel<boolean>('open', { required: true })
const emit = defineEmits<{ changed: [] }>()

const state = ref<ShareState | null>(null)
const typed = ref('')
/** What went wrong with the last invite, under the field. The typed name stays. */
const problem = ref('')
/** What went wrong reading the list. It replaces the dialog body. */
const loadFailure = ref('')

const read = useCall<ShareState, { slug: string }>({
  url: method('share_info'),
  immediate: false,
})
const invite = useCall<ShareState, { slug: string; username: string }>({
  url: method('invite_editor'),
  method: 'POST',
  immediate: false,
})
const withdraw = useCall<ShareState, { slug: string; username: string }>({
  url: method('remove_editor'),
  method: 'POST',
  immediate: false,
})
const access = useCall<Prototype, { slug: string; is_public: boolean }>({
  url: method('set_public'),
  method: 'POST',
  immediate: false,
})

const NETWORK = "Couldn't reach Sketch. Check your connection and try again."

/** A refused fetch has the browser's own words. Say what happened instead. */
function words(error: unknown): string {
  // The server's own words come after the exception name: "ValidationError: No Sketch user ...".
  const message = ((error as Error)?.message ?? '').replace(/^\w*(Error|Exception):\s*/, '')
  if (!message || /failed to fetch|network|load failed|timed out/i.test(message)) return NETWORK
  return message
}

/**
 * A press on a toast is outside the dialog, and the dialog closes on that.
 * Removing someone shows a toast with Undo, so the press must not reach the
 * dialog's own listener: the click still lands, the dialog stays.
 */
function keepOpenOnToast(event: PointerEvent): void {
  if ((event.target as Element | null)?.closest?.('[data-sonner-toast]')) event.stopPropagation()
}
onBeforeUnmount(() => window.removeEventListener('pointerdown', keepOpenOnToast, true))

watch(open, (value) => {
  if (!value) {
    window.removeEventListener('pointerdown', keepOpenOnToast, true)
    return
  }
  window.addEventListener('pointerdown', keepOpenOnToast, true)
  typed.value = ''
  problem.value = ''
  load()
})

async function load(): Promise<void> {
  loadFailure.value = ''
  state.value = null
  try {
    state.value = await read.submit({ slug: props.prototype.slug })
  } catch (error) {
    loadFailure.value = words(error)
  }
}

const editors = computed(() => state.value?.editors ?? [])
const owner = computed(() => state.value?.owner ?? null)
const busy = computed(() => invite.loading || withdraw.loading || access.loading)

async function add(): Promise<void> {
  const username = typed.value.trim()
  if (!username || invite.loading) return
  problem.value = ''
  try {
    state.value = await invite.submit({ slug: props.prototype.slug, username })
    typed.value = ''
  } catch (error) {
    // The name stays where it is, so a typo is one key away from fixed.
    problem.value = words(error)
  }
}

async function takeOff(person: SharePerson): Promise<void> {
  if (withdraw.loading) return
  try {
    state.value = await withdraw.submit({ slug: props.prototype.slug, username: person.username })
    problem.value = ''
  } catch (error) {
    toast.error(words(error))
    return
  }
  toast.success(`Removed ${person.full_name}`, {
    action: { label: 'Undo', onClick: () => bringBack(person) },
  })
}

async function bringBack(person: SharePerson): Promise<void> {
  try {
    state.value = await invite.submit({ slug: props.prototype.slug, username: person.username })
  } catch (error) {
    toast.error(`Couldn't undo. ${words(error)}`)
  }
}

async function setPublic(value: boolean): Promise<void> {
  if (!state.value || access.loading) return
  try {
    await access.submit({ slug: props.prototype.slug, is_public: value })
    state.value = { ...state.value, is_public: value }
    emit('changed')
  } catch (error) {
    toast.error(words(error))
  }
}

async function copyLink(): Promise<void> {
  if (!state.value) return
  try {
    await copyText(state.value.public_url)
  } catch {
    // `copyText` shows the text to copy by hand before it rejects.
    return
  }
  toast.success('Link copied')
}
</script>

<template>
  <Dialog v-model:open="open" size="md" title="Share">
    <template #default>
      <div v-if="loadFailure" class="flex flex-col items-start gap-2">
        <ErrorMessage :message="loadFailure" />
        <Button label="Try again" variant="subtle" @click="load" />
      </div>

      <div v-else-if="!state || !owner" class="min-h-24"><LoadingText /></div>

      <div v-else class="flex flex-col gap-5">
        <form class="flex flex-col gap-1.5" @submit.prevent="add">
          <div class="flex items-end gap-2">
            <FormControl
              v-model="typed"
              class="min-w-0 flex-1"
              label="Invite by Sketch username"
              autocomplete="off"
              autocapitalize="off"
              spellcheck="false"
              @update:model-value="problem = ''"
            />
            <Button
              type="submit"
              label="Invite"
              variant="subtle"
              :loading="invite.loading"
              :disabled="!typed.trim()"
            />
          </div>
          <ErrorMessage v-if="problem" :message="problem" />
        </form>

        <div class="flex flex-col gap-2">
          <!-- Twenty people scroll inside the dialog, not past it. -->
          <ul class="-mx-1 flex max-h-60 flex-col gap-0.5 overflow-y-auto px-1" aria-label="People">
            <li class="flex items-center gap-3 py-1.5">
              <Avatar :image="owner.user_image" :label="owner.full_name" size="md" />
              <span class="min-w-0 flex-1 truncate text-p-base text-ink-gray-8" :title="owner.full_name">
                {{ owner.full_name }}
              </span>
              <span class="shrink-0 text-p-sm text-ink-gray-5">You &middot; Owner</span>
              <span class="w-[4.5rem] shrink-0" aria-hidden="true" />
            </li>
            <li v-for="person in editors" :key="person.username" class="flex items-center gap-3 py-1.5">
              <Avatar :image="person.user_image" :label="person.full_name" size="md" />
              <!-- On a phone the handle goes under the name, so neither is cut to a few letters. -->
              <span class="flex min-w-0 flex-1 flex-col sm:flex-row sm:items-baseline sm:gap-1.5">
                <span class="truncate text-p-base text-ink-gray-8" :title="person.full_name">
                  {{ person.full_name }}
                </span>
                <span class="truncate text-p-sm text-ink-gray-5" :title="`@${person.username}`">
                  @{{ person.username }}
                </span>
              </span>
              <span class="shrink-0 text-p-sm text-ink-gray-5">Editor</span>
              <span class="flex w-[4.5rem] shrink-0 justify-end">
                <Button
                  variant="ghost"
                  size="sm"
                  label="Remove"
                  :aria-label="`Remove ${person.full_name}`"
                  :disabled="busy"
                  @click="takeOff(person)"
                />
              </span>
            </li>
          </ul>
          <p v-if="!editors.length" class="text-p-sm text-ink-gray-5">
            Invite people to add their own variants. They can't change yours.
          </p>
        </div>

        <Switch
          :model-value="state.is_public"
          :label="state.is_public ? 'Public' : 'Private'"
          :description="
            state.is_public
              ? 'Anyone with the link can view and comment'
              : 'Only you and invited people'
          "
          :disabled="access.loading"
          @update:model-value="setPublic"
        />

        <div>
          <Button label="Copy link" icon-left="lucide-link" variant="subtle" @click="copyLink" />
        </div>
      </div>
    </template>
  </Dialog>
</template>
