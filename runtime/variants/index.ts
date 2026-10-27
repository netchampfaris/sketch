// `sketch:variants`: a Prototype imports `Variants` and `useDemoState`. `setKeepHandler`, `enableMakeDefault`,
// `makeDefault` and `Chrome` are internal, for annotate and the Viewer, and are deliberately left out of the skill.
// A state called outside any RouterView (App.vue) is app-wide; inside one it belongs to that page.
import { computed, inject, onBeforeUnmount, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { applyStateLink, hookRouter, idOf, mirrorStates, pageKeyOf, sandboxKey, slugOf, stateValues, states } from './state'

export { default as Variants } from './Variants.vue'
export { default as Chrome } from './Chrome.vue'
export { setKeepHandler } from './state'
export { enableMakeDefault, makeDefault } from './default'

// A demo value (a persona, a workflow phase). The first option is the default.
export function useDemoState<T extends string>(name: string, options: readonly T[]) {
  const key = slugOf(name)
  const path = pageKeyOf()
  const id = idOf(path, key)
  const route = useRoute()
  const router = useRouter()
  const sb = inject(sandboxKey, null)

  // In a frame (a canvas tile): forced values only. Nothing reaches the live registry or the URL.
  if (sb) {
    sb.reg.states.push({ key, label: name, path, options: [...options], count: 1 })
    return computed<T>({
      get: () => (options.includes(sb.states[id] as T) ? (sb.states[id] as T) : options[0]),
      set: (v) => {
        sb.states[id] = v
      },
    })
  }

  const entry = states[id]
  if (entry && entry.options.join('\n') !== options.join('\n')) {
    console.warn(`[sketch variants] The state "${name}" is declared with different options in two places.`)
  }
  hookRouter(router)
  applyStateLink(route, id, key, options)
  // The first navigation may not be done when App.vue sets up.
  router.isReady().then(() => applyStateLink(router.currentRoute.value, id, key, options))

  onMounted(() => {
    const e = states[id]
    if (e) e.count++
    else states[id] = { key, label: name, path, options: [...options], count: 1 }
    mirrorStates(router)
  })
  onBeforeUnmount(() => {
    const e = states[id]
    if (!e) return
    if (--e.count <= 0) delete states[id]
  })
  return computed<T>({
    get: () => (options.includes(stateValues[id] as T) ? (stateValues[id] as T) : options[0]),
    set: (v) => {
      stateValues[id] = v
      mirrorStates(router)
    },
  })
}
