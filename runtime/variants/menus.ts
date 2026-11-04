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
