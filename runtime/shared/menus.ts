// One dropdown open at a time: every dropdown binds itself with `menuBind('its-own-key')`, and opening one closes
// whichever other was open. The shell (its toolbar, comment box, panel and Demo pill) and the frame's canvas each hold
// their own, being two documents.
import { ref } from 'vue'

const current = ref<string | null>(null)

export function menuBind(key: string, onOpen?: () => void) {
	return {
		open: current.value === key,
		'onUpdate:open': (o: boolean) => {
			if (o) {
				current.value = key
				onOpen?.()
			} else if (current.value === key) current.value = null
		},
	}
}
