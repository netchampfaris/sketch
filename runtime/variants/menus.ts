// The canvas's own dropdowns: one open at a time. Every dropdown binds itself with `menuBind('its-own-key')`: opening
// one closes whichever other was open. The shell keeps its own (runtime/shell/variants.ts menuBind).
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

// Sketch's own menus open in a body-level host of ours, so the frame agent's picking tells them from the page's menus
// and never picks them. No z-index of its own: a menu keeps the library's.
let host: HTMLElement | null = null
export function menuHost() {
  if (!host?.isConnected) {
    host = document.createElement('div')
    host.setAttribute('data-sketch-ui', 'menus')
    document.body.append(host)
  }
  return host
}
