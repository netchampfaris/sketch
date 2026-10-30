// `sketch:variants`: a Prototype imports `Variants` and `useDemoState`. `enableMakeDefault`,
// `makeDefault` and `Chrome` are internal, for annotate and the Viewer, and are deliberately left out of the skill.
// A state called outside any RouterView (App.vue) is app-wide; inside one it belongs to that page.
import { computed, defineComponent, h, inject, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Variants from './Variants.vue'
import { applyStateLink, hookRouter, humanise, idOf, mirrorStates, pageKeyOf, readOptions, sandboxKey, slugOf, stateValues, states } from './state'

export { Variants }
export { default as Chrome } from './Chrome.vue'
export { enableMakeDefault, makeDefault } from './default'
export { enableVariantEdit } from './edit'
export { registerExtras, registerSeen } from './extras'
export { badges, hasUnreadThreads, initBadges, isNew, lookAt, readThread, setUnread } from './badges'
export { bridge, findTile, sameTile, spotOf, tileExists, tileLabel, whereOf } from './bridge'
export type { Tab, TileHit, TileRef, TileSpot } from './bridge'
export { menuBind } from './menus'
export { closeCanvas, openCanvas } from './state'
export { applyPicks, currentPicks, picksAvailable, picksShown, picksWords } from './picks'
export type { DemoPick } from './picks'

// A demo value (a persona, a workflow phase). The first option is the default. Options are a list, or an object of
// groups ({ Data: ['Default', 'Loading'], Access: ['Read-only'] }). `of` ("Supplier card/Compact", a set's label and
// an option's label) makes it a component state: drawn on the canvas, never in the Demo pill or the URL.
export function useDemoState<T extends string>(name: string, input: readonly T[] | Record<string, readonly T[]>, config: { of?: string } = {}) {
  const { options, groups } = readOptions(input)
  const of = config.of?.trim() || undefined
  const key = of ? `${slugOf(name)}@${slugOf(of)}` : slugOf(name)
  const path = pageKeyOf()
  const id = idOf(path, key)
  const route = useRoute()
  const router = useRouter()
  const sb = inject(sandboxKey, null)

  // In a frame (a canvas tile): forced values only. Nothing reaches the live registry or the URL.
  if (sb) {
    sb.reg.states.push({ key, label: name, path, options: [...options], count: 1, groups, of })
    return computed<T>({
      get: () => (options.includes(sb.states[id] as T) ? (sb.states[id] as T) : options[0]),
      set: (v) => {
        sb.states[id] = v
      },
    })
  }

  if (of) {
    const own = ref<T>(options[0])
    return computed<T>({
      get: () => (options.includes(own.value) ? own.value : options[0]),
      set: (v) => {
        own.value = v
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
    else states[id] = { key, label: name, path, options: [...options], count: 1, groups }
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

// A component with no `<Variants>` of its own, once a teammate has made a variant for it: the same component, inside a
// set whose first option is the original. It takes the original's props, listeners and slots, and hands them on.
export function wrapComponent(Original: any, file: string) {
  const name = humanise(file.split('/').pop()!.replace(/\.vue$/, ''))
  return defineComponent({
    name: Original?.name ?? 'Variants',
    inheritAttrs: false,
    setup: (_, { attrs, slots }) => () =>
      h(Variants, { name, wrapper: true, file, forward: { attrs, slots } }, { original: () => h(Original, attrs, slots) }),
  })
}
