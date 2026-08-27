// Browser copy of frappe-ui/tailwind/preset.js.
// Two changes only:
//  - lucideIconsPlugin reads SVG files with node:fs, so it is replaced by
//    iconPackBrowser, which reads the same icons from a bundled JSON map
//  - no `content`; the runtime feeds classes through a virtual file
import themePlugin from 'FUI/tailwind/plugin.js'
import forms from '@tailwindcss/forms'
import typography from '@tailwindcss/typography'
import lucide from './shims/iconPackBrowser.js'

const integerSpacing = Object.fromEntries(
  Array.from({ length: 64 }, (_, i) => i + 1).map((n) => [n, `${n * 0.25}rem`]),
)

export default {
  darkMode: ['selector', '[data-theme="dark"]'],
  theme: { extend: { spacing: integerSpacing } },
  safelist: ['prose', 'prose-v3'],
  plugins: [forms, typography, themePlugin, lucide],
}
