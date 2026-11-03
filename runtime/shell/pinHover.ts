// The element outlined while the pointer is on a pin: the pin's tracked id (frame.ts `rects`), and the
// dragged box of a box note, which is redrawn in place of its container.
import { shallowRef } from 'vue'
import type { BoxInfo } from '../shared/protocol'

export const pinHover = shallowRef<{ id: string; box?: BoxInfo } | null>(null)
export const clearHover = () => (pinHover.value = null)
