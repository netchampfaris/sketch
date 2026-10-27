<script lang="ts">
// <Variants name="Leave card"><template #compact>…</template><template #detailed>…</template></Variants>
// Renders the chosen slot only, with no wrapper element. The first slot is the default.
// Variants a teammate added for this set (extras.ts) join the options after the owner's own and render in an error
// boundary, so a mistake in one never reaches the page.
import { Fragment, defineComponent, getCurrentInstance, h, inject, onBeforeUnmount, onErrorCaptured, ref, watch } from 'vue'
import type { PropType, VNodeChild } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { extraOf, failed, mergeOptions } from './extras'
import { choices, currentOf, fromQuery, hookRouter, humanise, mirrorSets, pageKeyOf, sandboxKey, setId, sets, slugOf, type VSet } from './state'

type Forward = { attrs: Record<string, unknown>; slots: Record<string, (...a: any[]) => VNodeChild> }

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
    if ((sb ? sb.reg.sets : sets).some((s) => s.path === path && s.key === key)) {
      // A wrapped component used twice is not a mistake in the page.
      if (!props.wrapper) console.warn(`[sketch variants] Two sets on this page are named "${props.name}". Names must be unique.`)
      key += '-2'
      label += ' 2'
    }

    // The component whose template wrote this tag: its type carries the SFC's own path (`__file`,
    // set by compileSFC), however deep in slots of other components the tag ends up.
    const file = props.file || String((inst.vnode.ctx?.type as { __file?: string } | undefined)?.__file ?? '')
    const own = () => Object.keys(slots).filter((k) => k !== 'default').map((value) => ({ value, label: humanise(value) }))
    const options = () => mergeOptions(own(), { name: props.name, wrapper: props.wrapper, file })
    // The slot's elements sit between the Fragment's start and end anchors.
    const elements = () => {
      const out: Element[] = []
      const end = inst.subTree?.anchor
      for (let n = inst.subTree?.el?.nextSibling; n && n !== end; n = n.nextSibling) if (n.nodeType === 1) out.push(n as Element)
      return out
    }
    const set: VSet = { key, label, name: props.name, file, path, options, elements }
    const id = setId(set)
    const draw = (cur: string | undefined) => {
      if (cur === undefined) return undefined
      if (slots[cur]) return slots[cur]!()
      return extraOf(cur) ? h(Boundary, { value: cur, forward: props.forward }) : undefined
    }

    // Keyed by the option: slot vnodes are compiled with static props that Vue assumes are unchanged, so
    // two options that render the same component would otherwise be patched in place, not swapped.
    if (sb) {
      sb.reg.sets.push(set)
      return () => {
        const v = sb.variants[id]
        const o = options()
        const cur = o.some((x) => x.value === v) ? v : o[0]?.value
        return h(Fragment, { key: cur }, draw(cur))
      }
    }

    hookRouter(router)
    // A link that names an option wins over what was picked earlier.
    const opt = fromQuery(route, 'v', key)
    if (opt && options().some((o) => o.value === opt)) choices[id] = opt
    sets.push(set)
    watch(() => currentOf(set), () => mirrorSets(router), { flush: 'post' })
    mirrorSets(router)
    onBeforeUnmount(() => sets.splice(sets.indexOf(set), 1))

    return () => {
      const cur = currentOf(set)!
      return h(Fragment, { key: cur }, draw(cur))
    }
  },
})
</script>
