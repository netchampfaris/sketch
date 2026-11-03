// Where the page's toasts sit. The Viewer shell draws its own chrome over this frame (the Demo pill and the toolbar's
// trigger in the corner and, over the canvas, its panel), so toasts stand above the corner, and while the canvas
// leaves room for the shell's panel (Canvas.vue publishes it in --sketch-panel-w) they stand left of it.
let placed = false
export function placeToasts() {
  if (placed) return
  placed = true
  const style = document.createElement('style')
  style.textContent =
    '[data-sonner-toaster]{--offset-bottom:72px!important;--mobile-offset-bottom:72px!important;--offset-right:max(24px,calc(var(--sketch-panel-w,0px) + 16px))!important;}'
  document.head.append(style)
}
