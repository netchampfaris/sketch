<script setup lang="ts">
/**
 * "New prototype" — the only place a Recipe is chosen (spec 10).
 *
 * The dialog is titled after the thing it makes, not after its second field.
 * Name is the only required input, so it leads and it takes focus on open.
 *
 * A Recipe with no vendored tree is still listed and disabled, so a missing
 * tree reads as missing instead of disappearing.
 */
import { computed, ref, useId, watch } from 'vue'
import { Dialog, FormControl, LoadingText, toast, useCall } from 'frappe-ui'
import { List, ListCell, ListRow } from 'frappe-ui/list'
import { method, recipes } from '../store'
import type { Prototype } from '../types'

/**
 * Tailwind builds a `lucide-*` class only when it reads the literal string in
 * this project's source, so the icon names live here and not in the API
 * response.
 */
const ICONS: Record<string, string> = {
  blank: 'lucide-file',
  discussions: 'lucide-messages-square',
  compose: 'lucide-pen-line',
  deals: 'lucide-handshake',
  tickets: 'lucide-life-buoy',
  mail: 'lucide-mail',
  files: 'lucide-folder',
  tasks: 'lucide-square-check-big',
  accounting: 'lucide-landmark',
}

function iconFor(slug: string): string {
  return ICONS[slug] ?? 'lucide-file'
}

const open = defineModel<boolean>('open', { required: true })
const emit = defineEmits<{ created: [prototype: Prototype] }>()

const title = ref('')
const recipe = ref('blank')

/**
 * The helper lines are siblings, not `FormControl`'s `description` prop, so
 * both render at the same size. `InputDescription.vue:3` hard-codes
 * `text-p-sm` (13px) and takes no class, while the Recipe helper below the
 * picker is plain markup at 12px. Owning both keeps one helper size in the
 * dialog. The ids restore the wiring the prop would have given us: TextInput
 * binds `aria-describedby` before it spreads attrs (`TextInput.vue:43,48`),
 * so ours wins.
 */
const nameHelpId = useId()
const recipeLabelId = useId()
const recipeHelpId = useId()

const create = useCall<Prototype, { title: string; recipe: string }>({
  url: method('create_prototype'),
  method: 'POST',
  immediate: false,
  onSuccess: (data) => {
    toast.success(`${data.title} created`)
    open.value = false
    emit('created', data)
  },
  onError: (error) => toast.error(error.message),
})

watch(open, (value) => {
  if (!value) return
  title.value = ''
  recipe.value = 'blank'
  recipes.reload()
})

const canCreate = computed(() => title.value.trim().length > 0)

// A recipe with no vendored tree cannot be built from. Falling back to Blank
// keeps the picker honest instead of failing at create time.
watch(recipe, (slug) => {
  const picked = (recipes.data ?? []).find((item) => item.slug === slug)
  if (picked && !picked.available) recipe.value = 'blank'
})

async function submit(): Promise<void> {
  if (!canCreate.value) return
  await create.submit({ title: title.value.trim(), recipe: recipe.value })
}
</script>

<template>
  <Dialog
    v-model:open="open"
    :actions="[
      {
        label: 'Create prototype',
        variant: 'subtle',
        theme: 'gray',
        disabled: !canCreate,
        onClick: submit,
      },
    ]"
    size="xl"
    title="New prototype"
  >
    <template #default>
      <!--
        `autofocus` is read by frappe-ui, not by the browser. `Dialog.vue:368`
        prevents reka's own focus trap when it finds an `[autofocus]`
        descendant, and `useAutofocusOnOpen.ts:54` then focuses the first
        focusable node inside it on every open. FormControl passes stray attrs
        down to the `<input>` (`FormControl.vue:98` into `TextInput.vue:48`),
        so the marker lands on the field itself. Without it focus opens on the
        Close button, which is the one control that throws the work away.
      -->
      <FormControl
        v-model="title"
        :aria-describedby="nameHelpId"
        autofocus
        label="Name"
        placeholder="Issue tracker"
        required
        @keyup.enter="submit"
      />
      <p :id="nameHelpId" class="mt-2 text-p-xs text-ink-gray-5">
        The link is made from this name once, and never moves.
      </p>

      <!--
        A hand-written label, because the picker is a `List` and not a form
        control. It copies what `InputLabel.vue:39` renders for the Name field
        above, and the 6px below it is `TextInput.vue:4`'s `space-y-1.5`, so
        the two fields read as one ladder.
      -->
      <p :id="recipeLabelId" class="mt-5 block text-base text-ink-gray-5">Recipe</p>
      <div
        :aria-describedby="recipeHelpId"
        :aria-labelledby="recipeLabelId"
        class="mt-1.5 h-80 overflow-y-auto"
        role="group"
      >
        <LoadingText v-if="recipes.loading && !recipes.data?.length" />
        <List
          v-else
          v-model:active="recipe"
          class="-mx-2 list-row-px-2"
          :row-height="52"
        >
          <ListRow
            v-for="item in recipes.data ?? []"
            :key="item.slug"
            :value="item.slug"
          >
            <ListCell>
              <span
                class="grid size-8 shrink-0 place-items-center rounded-4 bg-surface-gray-2 text-ink-gray-7"
              >
                <span :class="[iconFor(item.slug), 'size-4']" aria-hidden="true" />
              </span>
            </ListCell>
            <ListCell>
              <div class="min-w-0">
                <div class="truncate text-base text-ink-gray-8">{{ item.label }}</div>
                <div class="mt-1 truncate text-sm text-ink-gray-5">
                  {{ item.available ? item.description : 'Not vendored yet' }}
                </div>
              </div>
            </ListCell>
            <ListCell class="justify-end">
              <span
                v-if="recipe === item.slug"
                class="lucide-check size-4 text-ink-gray-7"
                aria-hidden="true"
              />
            </ListCell>
          </ListRow>
        </List>
      </div>
      <p :id="recipeHelpId" class="mt-2 text-p-xs text-ink-gray-5">
        A recipe is the starting set of files. Your agent changes them from there.
      </p>
    </template>
  </Dialog>
</template>
