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
 * Each editor row ends in a role column, "Editor" with a menu that holds
 * Remove, the way a share dialog elsewhere reads. The owner's row says "Owner"
 * there. A new invite lands right under the owner's row, flashes once and
 * scrolls into view, so twenty people never hide it.
 *
 * Under the Public link switch, while it is off, a line names the people who
 * commented and are not invited: they lose access with the link, and their
 * comments stay for the owner and the editors, marked "No access".
 *
 * Removing is immediate: it can be undone with one click, so there is no
 * confirm. The variants a removed person made stay in the prototype.
 *
 * The username field matches exactly. Sketch never searches or lists its
 * users, so a name is only ever answered with the person it names or with
 * "No Sketch user called ...".
 */
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import {
  Avatar,
  Button,
  Dialog,
  Dropdown,
  ErrorMessage,
  FormControl,
  LoadingText,
  Switch,
  toast,
  useCall,
} from 'frappe-ui'
import { avatarTheme } from '../../../runtime/shared/avatarTheme'
import { copyText, errorText, method, signedOut } from '../store'
import type { Prototype, SharePerson, ShareState } from '../types'

const props = defineProps<{ prototype: Prototype }>()
const open = defineModel<boolean>('open', { required: true })
const emit = defineEmits<{ changed: [] }>()

const state = ref<ShareState | null>(null)
const form = ref<HTMLElement | null>(null)
const list = ref<HTMLElement | null>(null)
/** The person invited last. Their row is lit for a moment, then fades. */
const fresh = ref('')
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

/** A refused fetch has the browser's own words. Say what happened instead; a signed-out session says so (store.ts). */
function words(error: unknown): string {
  const message = errorText(error)
  if (!signedOut.value && /failed to fetch|network|load failed|timed out/i.test(message)) return NETWORK
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
    return
  }
  // The body only exists now, after the dialog took focus for its Close button.
  await nextTick()
  form.value?.querySelector('input')?.focus()
}

/** Newest invite first, so a new person is right under the owner. */
const editors = computed(() => [...(state.value?.editors ?? [])].reverse())
const owner = computed(() => state.value?.owner ?? null)
/**
 * Said while the link is still on, before the switch is turned off: "Turning this off removes access for Arohi and
 * Faris, who commented." With three or more, "for Arohi, Faris and 2 others, who commented." Nothing once it is off.
 */
const loseAccess = computed(() => {
  const list = state.value?.commenters ?? []
  if (!state.value?.is_public || !list.length) return ''
  const first = (p: { full_name: string; username: string }) => p.full_name.split(/\s+/)[0] || p.username
  const rest = list.length - 2
  const names =
    list.length <= 2
      ? list.map(first).join(' and ')
      : `${first(list[0])}, ${first(list[1])} and ${rest} ${rest === 1 ? 'other' : 'others'}`
  return `Turning this off removes access for ${names}, who commented.`
})
const busy = computed(() => invite.loading || withdraw.loading || access.loading)

async function add(): Promise<void> {
  const username = typed.value.trim()
  if (!username || invite.loading) return
  problem.value = ''
  try {
    state.value = await invite.submit({ slug: props.prototype.slug, username })
    typed.value = ''
    emit('changed')
    await show(username)
  } catch (error) {
    // The name stays where it is, so a typo is one key away from fixed.
    problem.value = words(error)
  }
}

/** Light the row of the person just added and bring it into view. */
async function show(username: string): Promise<void> {
  const row = state.value?.editors.find((p) => p.username === username)
  if (!row) return
  fresh.value = row.username
  await nextTick()
  if (list.value) list.value.scrollTop = 0
  // One frame lit, then the class goes and the colour fades out over its transition.
  setTimeout(() => (fresh.value = ''), 120)
}

async function takeOff(person: SharePerson): Promise<void> {
  if (withdraw.loading) return
  try {
    state.value = await withdraw.submit({ slug: props.prototype.slug, username: person.username })
    problem.value = ''
    emit('changed')
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
    emit('changed')
    await show(person.username)
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
  <Dialog v-model:open="open" size="md" title="Share" position="top">
    <template #default>
      <div v-if="loadFailure" class="flex flex-col items-start gap-2">
        <ErrorMessage :message="loadFailure" />
        <Button label="Try again" variant="subtle" @click="load" />
      </div>

      <div v-else-if="!state || !owner" class="min-h-24"><LoadingText /></div>

      <div v-else class="flex flex-col gap-5">
        <form ref="form" class="flex flex-col gap-1.5" @submit.prevent="add">
          <div class="flex items-end gap-2">
            <FormControl
              v-model="typed"
              class="min-w-0 flex-1"
              label="Invite by GitHub username"
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
          <!--
            The note and a failed invite's reason share one cell, so the dialog is as tall with the
            reason as without it. The note comes back when the name is edited.
          -->
          <div class="grid">
            <p class="col-start-1 row-start-1 text-xs text-ink-gray-5" :class="problem ? 'invisible' : ''">
              Editors' variants run as code in your prototype. Invite people you trust.
            </p>
            <ErrorMessage v-if="problem" class="col-start-1 row-start-1 !text-xs" :message="problem" />
          </div>
        </form>

        <div class="flex flex-col gap-2">
          <!-- Twenty people scroll inside the dialog, not past it. The 268px cut leaves row 7 half in view. -->
          <ul
            ref="list"
            class="-mx-2 flex max-h-[268px] flex-col gap-0.5 overflow-y-auto px-2"
            aria-label="People"
          >
            <li class="-mx-1 flex items-center gap-3 px-1 py-2">
              <Avatar :image="owner.user_image" :label="owner.full_name" :theme="avatarTheme(owner.username)" size="md" />
              <!-- "(you)" is the one word this row exists for, so it never gives way to a long name. -->
              <span class="flex min-w-0 flex-1 items-baseline text-p-base text-ink-gray-8" :title="`${owner.full_name} (you)`">
                <span class="min-w-0 truncate">{{ owner.full_name }}</span>
                <span class="shrink-0 whitespace-pre"> (you)</span>
              </span>
              <span class="shrink-0 text-p-sm text-ink-gray-5">Owner</span>
            </li>
            <li
              v-for="person in editors"
              :key="person.username"
              class="-mx-1 flex items-center gap-3 rounded-4 px-1 py-2 transition-colors duration-[1500ms] ease-out motion-reduce:transition-none"
              :class="fresh === person.username ? 'bg-surface-gray-3' : ''"
            >
              <Avatar :image="person.user_image" :label="person.full_name" :theme="avatarTheme(person.username)" size="md" />
              <!-- Name and handle share one line at every width, so every row is as tall as the owner's. -->
              <span class="flex min-w-0 flex-1 items-baseline gap-1.5">
                <span class="min-w-0 truncate text-p-base text-ink-gray-8" :title="person.full_name">
                  {{ person.full_name }}
                </span>
                <span
                  class="max-w-[40%] shrink-0 truncate text-p-sm text-ink-gray-5"
                  :title="`@${person.username}`"
                >
                  @{{ person.username }}
                </span>
              </span>
              <!-- The role is the control: its menu holds Remove. -6px lines the text up with Invite and the switch. -->
              <span class="-mr-1.5 flex shrink-0">
                <Dropdown
                  :options="[{ label: 'Remove', onClick: () => takeOff(person) }]"
                  placement="bottom-end"
                >
                  <!-- Slot content, not `label`: Button lets `label` replace the aria-label. -->
                  <Button variant="ghost" size="xs" :aria-label="`${person.full_name}: Editor`" :disabled="busy">
                    Editor
                    <template #suffix><span class="lucide-chevron-down size-3.5" aria-hidden="true" /></template>
                  </Button>
                </Dropdown>
              </span>
            </li>
          </ul>
          <p v-if="!editors.length" class="text-p-sm text-ink-gray-5">
            Invite people to add their own variants. They can't change yours.
          </p>
        </div>

        <Switch
          :model-value="state.is_public"
          label="Public link"
          :description="
            state.is_public
              ? 'Anyone with the link can view and comment'
              : 'Only you and invited people'
          "
          :disabled="access.loading"
          @update:model-value="setPublic"
        />
        <p v-if="loseAccess" class="-mt-3 text-p-sm text-ink-gray-6" role="status">{{ loseAccess }}</p>

        <div>
          <Button label="Copy link" icon-left="lucide-link" variant="subtle" @click="copyLink" />
        </div>
      </div>
    </template>
  </Dialog>
</template>
