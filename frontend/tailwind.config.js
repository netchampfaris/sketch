import frappeUIPreset from 'frappe-ui/tailwind'

/** @type {import('tailwindcss').Config} */
export default {
  presets: [frappeUIPreset],
  content: [
    './index.html',
    './src/**/*.{vue,js,ts,jsx,tsx}',
    // Tailwind v3 ignores `content` declared in presets, so scan frappe-ui's
    // source for its components' utilities.
    './node_modules/frappe-ui/src/**/*.{vue,js,ts,jsx,tsx}',
  ],
}
