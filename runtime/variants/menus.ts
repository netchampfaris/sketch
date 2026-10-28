// One dropdown open at a time, across the page's toolbar, comment popover, comments panel, Demo pill and canvas.
// Every dropdown binds itself with `menuBind('its-own-key')`: opening one closes whichever other was open.
// Lives here because `sketch:variants` is the one module the annotate toolbar and the canvas both hold.
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
