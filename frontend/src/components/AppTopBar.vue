<script setup lang="ts">
/**
 * The one bar above every screen (spec 11).
 *
 * Sketch has two screens and one action, so a 14rem sidebar was furniture.
 * The mark goes left; Settings and the account menu go right. Settings is a
 * labelled button rather than a menu row, because it is the one page a user
 * has to find again: it holds the agent token.
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
import { useRoute } from 'vue-router'
import {
  Avatar,
  Button,
  Dropdown,
  useColorScheme,
  type ColorScheme,
  type DropdownOptions,
} from 'frappe-ui'
import { goToLogin, logout, session, sessionSettled, signedIn } from '../store'

const { colorScheme, setColorScheme } = useColorScheme()
const route = useRoute()

/**
 * The mark that `sketch/install.py` already puts on the pages before the SPA.
 * It lives in `sketch/public/images/`, which Frappe serves, so it is not a
 * bundled asset. A bound `:src` keeps Vite from trying to resolve the path at
 * build time.
 */
const logo = '/assets/sketch/images/sketch-logo.svg'

const fullName = computed(() => session.data?.full_name ?? '')
const username = computed(() => session.data?.username ?? '')

/**
 * Which side of the bar to draw, before the session read has answered.
 *
 * The route is the guess, and on every route but the public ones it is a
 * certainty: `sketch/www/sketch.py` refuses a Guest the bundle there, so
 * anybody reading /settings is signed in. On /feed and /about a Guest is the
 * common reader, so the bar opens signed out and swaps once if a session
 * lands. It never swaps twice, and it never changes height either way.
 */
const account = computed(() =>
  sessionSettled.value ? signedIn.value : !route.meta.public,
)

/** Where the mark leads. A Guest has no gallery, so it leads to the feed. */
const home = computed(() => (account.value ? '/' : '/feed'))

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
      // Settings left this menu and became a labelled button in the bar, so
      // the route to the token is visible without opening anything. The feed
      // and About stay here: both are read now and then, not returned to.
      //
      // `route`, not `onClick`. Both are routes of the SPA now
      // (`frontend/src/router.ts`), so Menu.vue pushes them and neither costs
      // a page load. They used to be server-rendered pages, and this row used
      // to set `window.location`.
      { label: 'Public feed', icon: 'lucide-layout-grid', route: '/feed' },
      { label: 'About', icon: 'lucide-info', route: '/about' },
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
        :to="home"
      >
        <img
          alt=""
          aria-hidden="true"
          class="size-6 shrink-0 dark:invert"
          :src="logo"
        />
        <span class="text-base-medium text-ink-gray-8">Sketch</span>
      </router-link>

      <div class="flex items-center gap-2">
        <!--
          Signed out, on /feed or /about. Two controls, both labelled: the
          page that explains Sketch, and the way in. Neither is solid, which
          is the standing rule, and the row is the same 32px tall as the
          signed-in one, so the bar does not move when the session lands.
        -->
        <template v-if="!account">
          <Button
            v-if="route.path !== '/about'"
            label="About"
            route="/about"
            theme="gray"
            variant="ghost"
          />
          <Button
            icon-left="lucide-log-in"
            label="Sign in"
            theme="gray"
            variant="subtle"
            @click="goToLogin"
          />
        </template>

        <!--
          Settings is a labelled control in the bar, not a row inside the
          account menu. The token lives on that page, and the only route to it
          used to be an unlabelled "S" avatar: a user reconnecting on a second
          machine had to open a menu to find out. Ghost keeps it quiet next to
          the page's own action, and the label matches the page title, which
          the menu row's "Agent connection" did not.
        -->
        <Button
          v-if="account"
          icon-left="lucide-settings"
          label="Settings"
          route="/settings"
          theme="gray"
          variant="ghost"
        />

        <Dropdown v-if="account" align="end" :options="menu">
          <template #default="{ open }">
            <!-- Only the surface changes on hover and on open, so the bar
                 never moves. The Avatar holds its size with no label and no
                 image.

                 The 32px target is 4px wider than the 24px `md` Avatar inside
                 it (frappe-ui Avatar.vue:109, `w-6 h-6`), so centring the
                 Avatar pushed it 4px inside the right rail that the page
                 header, the card menus and the dropdowns all share. `-mr-1`
                 hangs that 4px past the gutter and puts the Avatar back on
                 the rail. -->
            <button
              aria-label="Account"
              class="-mr-1 flex size-8 shrink-0 items-center justify-center rounded-full transition focus-visible:ring-0 focus-visible:focus-ring"
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
    </div>
  </header>
</template>
