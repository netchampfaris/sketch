// When to look behind the page's closed dialogs (Discover.vue), so the Demo pill lists the sets inside them on every page
// the dialog opens from. Only while the page has a closed dialog, and again when the page, a pick or a state changes.
import { getCurrentInstance, inject, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { dialogsIn } from './dialogs'
import { choices, sandboxKey, setFound, sets, stateValues, type VSet } from './state'

// Call in Chrome's setup. `job` is the look to run now, drawn as `<Discover :key="job.n" :path="job.path">`, and `onFound`
// takes what it found. Nothing is looked for while `paused()`, or in a frame.
export function useDialogSets(paused: () => boolean) {
  const inFrame = inject(sandboxKey, null) !== null
  const root = getCurrentInstance()!.root
  const route = useRoute()
  const router = useRouter()
  const job = ref<{ n: number; path: string; key: string } | null>(null)
  let n = 0
  let lookedFor = ''
  let timer = 0
  const look = () => {
    clearTimeout(timer)
    timer = window.setTimeout(() => {
      if (inFrame || paused() || job.value) return
      const open = dialogsIn(root.subTree)
      // No dialog at all: nothing is behind one. Every dialog open: what is in them is mounted, and what was found stays.
      if (!open.length) return setFound([], router)
      if (!open.includes(false)) return
      const key = JSON.stringify([route.path, choices, stateValues])
      if (key === lookedFor) return
      job.value = { n: ++n, path: route.fullPath, key }
    }, 150)
  }
  function onFound(list: VSet[]) {
    const done = job.value
    job.value = null
    if (!done) return
    lookedFor = done.key
    setFound(list, router)
    // The page moved on while it looked.
    look()
  }
  if (!inFrame) {
    watch([() => route.path, () => JSON.stringify(choices), () => JSON.stringify(stateValues), () => sets.length, paused], look, { immediate: true })
  }
  onBeforeUnmount(() => clearTimeout(timer))
  return { job, onFound }
}
