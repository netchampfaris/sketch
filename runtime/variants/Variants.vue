<script lang="ts">
// <Variants name="Leave card"><template #compact>…</template><template #detailed>…</template></Variants>
// Renders the chosen slot only, with no wrapper element. The first slot is the default.
import { Fragment, defineComponent, getCurrentInstance, h, inject, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { choices, currentOf, fromQuery, hookRouter, humanise, mirrorSets, pageKeyOf, sandboxKey, setId, sets, slugOf, type VSet } from './state'

export default defineComponent({
  name: 'Variants',
  inheritAttrs: false,
  props: { name: { type: String, required: true } },
  setup(props, { slots }) {
    const inst = getCurrentInstance()!
    const route = useRoute()
    const router = useRouter()
    const sb = inject(sandboxKey, null)
    const path = pageKeyOf()
    let key = slugOf(props.name)
    let label = props.name
    if ((sb ? sb.reg.sets : sets).some((s) => s.path === path && s.key === key)) {
      console.warn(`[sketch variants] Two sets on this page are named "${props.name}". Names must be unique.`)
      key += '-2'
      label += ' 2'
    }

    const options = () => Object.keys(slots).filter((k) => k !== 'default').map((value) => ({ value, label: humanise(value) }))
    // The slot's elements sit between the Fragment's start and end anchors.
    const elements = () => {
      const out: Element[] = []
      const end = inst.subTree?.anchor
      for (let n = inst.subTree?.el?.nextSibling; n && n !== end; n = n.nextSibling) if (n.nodeType === 1) out.push(n as Element)
      return out
    }
    // The component whose template wrote this tag: its type carries the SFC's own path (`__file`,
    // set by compileSFC), however deep in slots of other components the tag ends up.
    const file = String((inst.vnode.ctx?.type as { __file?: string } | undefined)?.__file ?? '')
    const set: VSet = { key, label, name: props.name, file, path, options, elements }
    const id = setId(set)

    // Keyed by the option: slot vnodes are compiled with static props that Vue assumes are unchanged, so
    // two options that render the same component would otherwise be patched in place, not swapped.
    if (sb) {
      sb.reg.sets.push(set)
      return () => {
        const v = sb.variants[id]
        const o = options()
        const cur = o.some((x) => x.value === v) ? v : o[0]?.value
        return h(Fragment, { key: cur }, slots[cur!]?.())
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
      return h(Fragment, { key: cur }, slots[cur]?.())
    }
  },
})
</script>
