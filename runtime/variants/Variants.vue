<script lang="ts">
// <Variants name="Leave card"><template #compact>…</template><template #detailed>…</template></Variants>
// Renders the chosen slot only, with no wrapper element. The first slot is the default.
import { Fragment, defineComponent, getCurrentInstance, h, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { mountPill } from './mount'
import { choices, currentOf, fromQuery, idOf, mirror, sets, slugOf, type VSet } from './state'

// `scan-first` and `scanFirst` both read "Scan first".
const humanise = (s: string) => {
  const t = s.replace(/([a-z])([A-Z])/g, '$1 $2').replace(/[-_]+/g, ' ').toLowerCase()
  return t.charAt(0).toUpperCase() + t.slice(1)
}

export default defineComponent({
  name: 'Variants',
  inheritAttrs: false,
  props: { name: { type: String, required: true } },
  setup(props, { slots }) {
    const inst = getCurrentInstance()!
    const route = useRoute()
    const router = useRouter()
    const path = route.path
    let key = slugOf(props.name)
    let label = props.name
    if (sets.some((s) => s.path === path && s.key === key)) {
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
    const set: VSet = { key, label, path, options, elements }

    // A link like #/inbox?v=leave-card.timeline opens on that option.
    const id = idOf(set)
    if (choices[id] === undefined) {
      const opt = fromQuery(route, 'v', key)
      if (opt && options().some((o) => o.value === opt)) choices[id] = opt
    }

    sets.push(set)
    mountPill(router)
    watch(() => currentOf(set), () => mirror(router, route), { flush: 'post' })
    mirror(router, route)
    onBeforeUnmount(() => sets.splice(sets.indexOf(set), 1))

    return () => h(Fragment, null, slots[currentOf(set)!]?.())
  },
})
</script>
