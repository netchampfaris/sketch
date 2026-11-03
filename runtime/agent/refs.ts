// Elements picked this visit, by a name the shell can hand back (`e1`, `e2`…). Picking (pick.ts) and Tweak
// (tweakPick.ts) share them, so the shell can track an element either tool picked. Once an element is gone,
// its ref finds nothing and the selector the shell kept stands in.
const byRef = new Map<string, WeakRef<Element>>()
const refs = new WeakMap<Element, string>()
let next = 0

export function refOf(el: Element): string {
	let r = refs.get(el)
	if (!r) {
		r = `e${++next}`
		refs.set(el, r)
		byRef.set(r, new WeakRef(el))
	}
	return r
}

export const elOf = (ref: string | undefined): Element | null => {
	const el = ref ? byRef.get(ref)?.deref() : undefined
	return el?.isConnected ? el : null
}
