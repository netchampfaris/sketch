<script setup lang="ts">
/**
 * The display preference: light, dark or system.
 *
 * `useColorScheme` writes `localStorage["theme"]` and sets `data-theme` on
 * <html>. The Viewer reads that same key inside the iframe, so this one
 * control themes the Sketch UI and every Prototype (spec 12).
 *
 * frappe-ui marks `ThemeSwitcher` deprecated in favour of `Select` with
 * `useColorScheme`. `Select` is also the only one of the two that fits a
 * 14rem sidebar footer.
 */
import { Select, useColorScheme, type ColorScheme } from 'frappe-ui'

const { colorScheme, setColorScheme } = useColorScheme()

const options = [
  { label: 'Light', value: 'light', icon: 'lucide-sun' },
  { label: 'Dark', value: 'dark', icon: 'lucide-moon' },
  { label: 'System', value: 'system', icon: 'lucide-monitor' },
]
</script>

<template>
  <Select
    aria-label="Theme"
    class="w-full"
    :model-value="colorScheme"
    :options="options"
    side="top"
    size="sm"
    variant="ghost"
    @update:model-value="(value) => setColorScheme(value as ColorScheme)"
  />
</template>
