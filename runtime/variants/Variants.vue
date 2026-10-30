<script lang="ts">
// <Variants name="Leave card"><template #compact>…</template><template #detailed>…</template></Variants>
// Renders the chosen slot only, with no wrapper element. The default is the slot `default="…"` names, else the first.
// Options show in the order they first appeared (extras.ts mergeOptions), so making one the default never moves it.
// Variants a teammate added for this set (extras.ts) join the options after the owner's own and render in an error
// boundary, so a mistake in one never reaches the page.
import { Fragment, defineComponent, getCurrentInstance, h, inject, onBeforeUnmount, onErrorCaptured, ref, watch } from 'vue'
import type { PropType, VNodeChild } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { extraOf, failed, mergeOptions } from './extras'
import { choices, currentOf, defaultOf, fromQuery, hookRouter, humanise, mirrorSets, pageKeyOf, sandboxKey, setId, sets, slugOf, type VSet } from './state'

type Forward = { attrs: Record<string, unknown>; slots: Record<string, (...a: any[]) => VNodeChild> }

// How many copies of a wrapped component hold one set open. The set leaves the page with the last of them.
const holders = new Map<VSet, number>()
function release(set: VSet) {
  const left = (holders.get(set) ?? 1) - 1
  if (left > 0) return void holders.set(set, left)
  holders.delete(set)
  const at = sets.indexOf(set)
  if (at >= 0) sets.splice(at, 1)
}

// The inside of an extra: loads the module on first render. A throw here belongs to the extra's boundary.
const Inner = defineComponent({
  props: { value: { type: String, required: true }, forward: { type: Object as PropType<Forward | null>, default: null } },
  setup(props) {
    const extra = extraOf(props.value)
    if (!extra) throw new Error('This variant is gone.')
    const Comp = extra.load() as any
    return () => h(Comp, props.forward?.attrs ?? {}, props.forward?.slots ?? {})
  },
})

const Boundary = defineComponent({
  props: { value: { type: String, required: true }, forward: { type: Object as PropType<Forward | null>, default: null } },
  setup(props) {
    const broke = ref('')
    onErrorCaptured((err) => {
      broke.value = String((err as Error)?.message || err)
      const extra = extraOf(props.value)
      if (extra) failed.report(extra, err)
      return false
    })
    return () =>
      broke.value
        ? h('div', { class: 'p-4 text-p-sm text-ink-gray-5', 'data-variant-failed': props.value }, `This variant did not load. ${broke.value}`)
        : h(Inner, { value: props.value, forward: props.forward })
  },
})

export default defineComponent({
  name: 'Variants',
  inheritAttrs: false,
  props: {
    name: { type: String, required: true },
    // The slot shown when nothing is picked. Sketch writes it when the owner picks Make default.
    default: { type: String, default: '' },
    // A set Sketch wraps around a component that has no `<Variants>` of its own: `file` is that component, and
    // `forward` carries the props and slots a variant receives in its place.
    wrapper: { type: Boolean, default: false },
    file: { type: String, default: '' },
    forward: { type: Object as PropType<Forward | null>, default: null },
  },
  setup(props, { slots }) {
    const inst = getCurrentInstance()!
    const route = useRoute()
    const router = useRouter()
    const sb = inject(sandboxKey, null)
    const path = pageKeyOf()
    let key = slugOf(props.name)
    let label = props.name
    // The component whose template wrote this tag: its type carries the SFC's own path (`__file`,
    // set by compileSFC), however deep in slots of other components the tag ends up.
    const file = props.file || String((inst.vnode.ctx?.type as { __file?: string } | undefined)?.__file ?? '')
    // One tag drawn many times (a card in a v-for, a component used in every row) is one set: every copy follows the one
    // choice. Two tags of that name in different files are a mistake, and the second is told apart.
    const twin = (sb ? sb.reg.sets : sets).find((s) => s.path === path && s.key === key)
    const shared = !!twin && (props.wrapper || (!!file && twin.file === file))
    if (twin && !shared) {
      console.warn(`[sketch variants] Two sets on this page are named "${props.name}". Names must be unique.`)
      key += '-2'
      label += ' 2'
    }

    const own = () => Object.keys(slots).filter((k) => k !== 'default').map((value) => ({ value, label: humanise(value) }))
    const options = () => mergeOptions(own(), { name: props.name, wrapper: props.wrapper, file, default: props.default })
    // The slot's elements sit between the Fragment's start and end anchors.
    const elements = () => {
      const out: Element[] = []
      const end = inst.subTree?.anchor
      for (let n = inst.subTree?.el?.nextSibling; n && n !== end; n = n.nextSibling) if (n.nodeType === 1) out.push(n as Element)
      return out
    }
    const set: VSet = twin && shared ? twin : { key, label, name: props.name, file, path, options, elements }
    const id = setId(set)
    const draw = (cur: string | undefined) => {
      if (cur === undefined) return undefined
      if (slots[cur]) return slots[cur]!()
      return extraOf(cur) ? h(Boundary, { value: cur, forward: props.forward }) : undefined
    }

    // Keyed by the option: slot vnodes are compiled with static props that Vue assumes are unchanged, so
    // two options that render the same component would otherwise be patched in place, not swapped.
    if (sb) {
      if (!shared) sb.reg.sets.push(set)
      return () => {
        const v = sb.variants[id]
        const o = options()
        const cur = o.some((x) => x.value === v) ? v : defaultOf(o)
        return h(Fragment, { key: cur }, draw(cur))
      }
    }

    hookRouter(router)
    if (shared) {
      holders.set(set, (holders.get(set) ?? 1) + 1)
      onBeforeUnmount(() => release(set))
      return () => {
        const cur = currentOf(set)!
        return h(Fragment, { key: cur }, draw(cur))
      }
    }
    holders.set(set, 1)
    // A link that names an option wins over what was picked earlier.
    const opt = fromQuery(route, 'v', key)
    if (opt && options().some((o) => o.value === opt)) choices[id] = opt
    sets.push(set)
    watch(() => currentOf(set), () => mirrorSets(router), { flush: 'post' })
    mirrorSets(router)
    onBeforeUnmount(() => release(set))

    return () => {
      const cur = currentOf(set)!
      return h(Fragment, { key: cur }, draw(cur))
    }
  },
})
</script>
