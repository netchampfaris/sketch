<script setup lang="ts">
/**
 * "Select a Recipe" — the only place a Recipe is chosen (spec 10).
 *
 * A Recipe with no vendored tree is still listed and disabled, so a missing
 * tree reads as missing instead of disappearing.
 */
import { computed, ref, watch } from 'vue'
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
        variant: 'solid',
        theme: 'gray',
        disabled: !canCreate,
        onClick: submit,
      },
    ]"
    size="xl"
    title="Select a Recipe"
  >
    <template #default>
      <FormControl
        v-model="title"
        label="Name"
        description="The link is made from this name once, and never moves."
        placeholder="Issue tracker"
        required
        @keyup.enter="submit"
      />

      <p class="mt-5 text-sm text-ink-gray-6">Recipe</p>
      <div class="mt-2 h-80 overflow-y-auto">
        <LoadingText v-if="recipes.loading && !recipes.data?.length" :lines="4" />
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
    </template>
  </Dialog>
</template>
