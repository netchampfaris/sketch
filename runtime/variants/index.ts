// `sketch:variants`: a Prototype imports `Variants` and `useDemoState`. `setKeepHandler` is internal,
// for annotate, and is deliberately left out of the skill.
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { mountPill } from './mount'
import { fromQuery, mirrorStates, slugOf, stateValues, states } from './state'

export { default as Variants } from './Variants.vue'
export { setKeepHandler } from './state'

// A global demo value (a persona, a workflow phase). The first option is the default.
export function useDemoState<T extends string>(name: string, options: readonly T[]) {
  const key = slugOf(name)
  const route = useRoute()
  const router = useRouter()
  const entry = states[key]
  if (entry && entry.options.join('\n') !== options.join('\n')) {
    console.warn(`[sketch variants] The state "${name}" is declared with different options in two places.`)
  }
  // Read a link like #/?s=persona.manager on first sight of the state.
  if (!stateValues[key]) {
    const named = fromQuery(route, 's', key)
    const opt = options.find((o) => slugOf(o) === named)
    if (opt) stateValues[key] = opt
  }
  onMounted(() => {
    const e = states[key]
    if (e) e.count++
    else states[key] = { key, label: name, options: [...options], count: 1 }
    mountPill(router)
    mirrorStates(router, route)
  })
  onBeforeUnmount(() => {
    const e = states[key]
    if (!e) return
    if (--e.count <= 0) delete states[key]
  })
  return computed<T>({
    get: () => {
      const v = stateValues[key] as T
      return options.includes(v) ? v : options[0]
    },
    set: (v) => {
      stateValues[key] = v
      mirrorStates(router, route)
    },
  })
}
