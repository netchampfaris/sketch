// The Demo pill's side of the shell: the rows the frame reports (its `model` message, runtime/variants/model.ts), and
// where the pill sits among the shell's other bottom-edge chrome. The frame's word is only ever drawn as text; a pick
// goes back to it as `state:set`, which it checks against its own sets and states.
import { reactive } from 'vue'
import type { ModelSet, ModelState } from '../shared/protocol'
import { onFrame, onGone, post } from './frame'

export const demo = reactive({
	sets: [] as ModelSet[],
	states: [] as ModelState[],
	canOpen: false,
	// ---- The shell's own
	// On a phone, how far from the bottom the open toolbar's top edge (plus a gap) is, and where it ends sideways: the
	// pill rides above it only when the two would meet (Toolbar.vue sets these).
	toolbarLift: 0,
	toolbarRight: 0,
	// The pill stack's height plus the bar it rides on, 0 with no pill: the toolbar's trigger and the toasts stand above it.
	stackH: 0,
})

onFrame('model', (d) => Object.assign(demo, d))
// A reloaded frame says it all again; until then the pill has nothing to show.
onGone(() => Object.assign(demo, { sets: [], states: [], canOpen: false }))

export const choose = (id: string, value: string) => post('state:set', { id, value })
export const measure = () => post('model:measure', {})
