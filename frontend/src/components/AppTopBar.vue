<script setup lang="ts">
/**
 * The one bar above every screen (spec 11).
 *
 * Sketch has two screens and one action, so a 14rem sidebar was furniture.
 * The mark goes left, the account menu goes right, and everything the sidebar
 * carried moves into that menu.
 *
 * The bar is a fixed h-12. Nothing in it depends on the session: the Avatar
 * keeps its size with no label and no image, and the name and the username
 * only appear inside the menu. So the bar reads the same signed out, loading
 * and loaded, and it does not move on hover, on focus or on open.
 *
 * The theme rows are here because `useColorScheme` writes
 * `localStorage["theme"]` and `data-theme` on <html>. The Viewer reads that
 * same key inside its iframe, so these three rows theme the Sketch UI and
 * every Prototype (spec 12). They replace the old ThemeControl.vue.
 */
import { computed } from 'vue'
import {
  Avatar,
  Dropdown,
  useColorScheme,
  type ColorScheme,
  type DropdownOptions,
} from 'frappe-ui'
import { logout, session } from '../store'

const { colorScheme, setColorScheme } = useColorScheme()

/**
 * The mark that `sketch/install.py` already puts on the pages before the SPA.
 * It lives in `sketch/public/images/`, which Frappe serves, so it is not a
 * bundled asset. A bound `:src` keeps Vite from trying to resolve the path at
 * build time.
 */
const logo = '/assets/sketch/images/sketch-logo.svg'

const fullName = computed(() => session.data?.full_name ?? '')
const username = computed(() => session.data?.username ?? '')

const schemes: { label: string; value: ColorScheme; icon: string }[] = [
  { label: 'Light', value: 'light', icon: 'lucide-sun' },
  { label: 'Dark', value: 'dark', icon: 'lucide-moon' },
  { label: 'System', value: 'system', icon: 'lucide-monitor' },
]

/**
 * One group, so the username labels the whole menu.
 *
 * The label is a non-breaking space until the session answers. Menu.vue skips
 * an empty group label (`v-if="group.group && !group.hideLabel"`), so an empty
 * string would drop the h-7 row and the menu would jump when the name lands.
 *
 * The group key is `options`. `{ group, items }` is a type error and renders
 * nothing (frappe-ui Menu/types.ts, `items?: never`).
 */
const menu = computed<DropdownOptions>(() => [
  {
    key: 'account',
    group: username.value ? '@' + username.value : ' ',
    options: [
      { label: 'Agent connection', icon: 'lucide-plug-zap', route: '/settings' },
      {
        label: 'Theme',
        icon: 'lucide-sun-moon',
        submenu: schemes.map((scheme) => ({
          label: scheme.label,
          icon: scheme.icon,
          selected: colorScheme.value === scheme.value,
          onClick: () => setColorScheme(scheme.value),
        })),
      },
      { label: 'Log out', icon: 'lucide-log-out', onClick: logout },
    ],
  },
])
</script>

<template>
  <!--
    Sticky, not fixed, and inside the page's scroll container. It has to share
    that container with the router view: the two centre their columns on the
    same width, so the mark stays in line with the page title once a scrollbar
    appears. z-20 clears PageHeader's own z-10.
  -->
  <header
    class="sticky top-0 z-20 flex h-12 items-center border-b border-outline-gray-1 bg-surface-base"
  >
    <!-- Same centred column and same gutters as the router view below, so the
         mark lines up with the page title. -->
    <div
      class="mx-auto flex w-full max-w-[940px] items-center justify-between gap-2 px-3 sm:px-5"
    >
      <router-link
        class="-mx-1 flex items-center gap-2 rounded-4 px-1 py-1 transition hover:bg-surface-gray-2 focus-visible:ring-0 focus-visible:focus-ring"
        to="/"
      >
        <img
          alt=""
          aria-hidden="true"
          class="size-6 shrink-0 dark:invert"
          :src="logo"
        />
        <span class="text-base-medium text-ink-gray-8">Sketch</span>
      </router-link>

      <Dropdown align="end" :options="menu">
        <template #default="{ open }">
          <!-- Only the surface changes on hover and on open, so the bar never
               moves. The Avatar holds its size with no label and no image. -->
          <button
            aria-label="Account"
            class="flex size-8 shrink-0 items-center justify-center rounded-full transition focus-visible:ring-0 focus-visible:focus-ring"
            :class="open ? 'bg-surface-gray-3' : 'hover:bg-surface-gray-2'"
            type="button"
          >
            <Avatar :image="session.data?.user_image" :label="fullName" size="md" />
          </button>
        </template>

        <!-- The check marks the live scheme. Only the theme rows set
             `selected`, and an unset row returns a comment node, which
             `hasRenderableContent` rejects. So the Theme row keeps its own
             submenu chevron. -->
        <template #item-suffix="{ selected }">
          <span
            v-if="selected"
            aria-hidden="true"
            class="lucide-check size-4 shrink-0 text-ink-gray-7"
          />
        </template>
      </Dropdown>
    </div>
  </header>
</template>
