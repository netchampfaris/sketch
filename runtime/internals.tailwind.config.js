// Layer 1: precompile the CSS for frappe-ui's own components, so a Prototype
// renders styled at first paint without waiting on the browser engine.
// Full preset here, lucide icon plugin included (it runs in node).
import preset from 'frappe-ui/tailwind'
import { content } from 'frappe-ui/tailwind'

export default {
  presets: [preset],
  content,
}
