import frappeUIPreset from 'frappe-ui/tailwind'

/** @type {import('tailwindcss').Config} */
export default {
  presets: [frappeUIPreset],
  content: [
    './index.html',
    './viewer.html',
    './src/**/*.{vue,js,ts,jsx,tsx}',
    // The Viewer shell's UI (frontend/src/viewer).
    '../runtime/shell/**/*.{vue,ts}',
    // Tailwind v3 ignores `content` declared in presets, so scan frappe-ui's
    // source for its components' utilities.
    './node_modules/frappe-ui/src/**/*.{vue,js,ts,jsx,tsx}',
  ],
}
