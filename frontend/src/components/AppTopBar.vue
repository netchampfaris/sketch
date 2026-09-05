<script setup lang="ts">
/**
 * The one bar above every screen (spec 11).
 *
 * Sketch has two screens and one action, so a 14rem sidebar was furniture.
 * The mark goes left, the gallery switcher goes in the centre, and Settings
 * and the account menu go right. Settings is a labelled button rather than a
 * menu row, because it is the one page a user has to find again: it holds the
 * agent token.
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
  TabButtons,
  useColorScheme,
  type ColorScheme,
  type DropdownOptions,
  type TabButton,
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

/**
 * The two galleries, as a segmented switcher in the bar (signed in only).
 *
 * They were one route each and no way between them: the gallery was the root
 * and the feed was a row inside the account menu, so a user had to open a menu
 * to read what anybody else had built, and nothing on the gallery said the
 * feed was there.
 *
 * `route`, not `onClick`. Each option renders a real `<RouterLink>`
 * (`TabButtons.vue`, `tabElement`), so the pair works with the Back button,
 * with a middle click and with a hover preview, and neither costs a page load.
 */
const galleries: TabButton[] = [
  { value: '/', label: 'My prototypes', route: '/' },
  { value: '/feed', label: 'Public prototypes', route: '/feed' },
]

/**
 * The route is the model, and the model is read-only.
 *
 * The links do the navigating, so the setter has nothing to do: writing here
 * would move the pill before the route it points at had resolved. On
 * /settings and /about the value matches no option, and TabButtons then draws
 * no pill, which is the truth: neither page is a gallery. It has to be a
 * string and not `undefined`, or the component falls back to holding its own
 * selection and the pill stops following the route.
 */
const gallery = computed<string>({
  get: () => (galleries.some((one) => one.value === route.path) ? route.path : ''),
  set: () => {},
})

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
      // the route to the token is visible without opening anything. About
      // stays here: it is read now and then, not returned to.
      //
      // The Public feed row left too. The bar's gallery switcher is that
      // route now, and a second door to /feed inside a menu would have been
      // the only nav row left in there.
      //
      // `route`, not `onClick`. About is a route of the SPA now
      // (`frontend/src/router.ts`), so Menu.vue pushes it and it costs no
      // page load. It used to be a server-rendered page, and this row used to
      // set `window.location`.
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
      class="mx-auto flex w-full max-w-[940px] items-center gap-2 px-3 sm:px-5"
    >
      <!--
        Three parts, and from 640px the outer two are `flex-1 basis-0`. They
        claim the same width whatever they hold, so the switcher between them
        sits on the centre of the bar and not on the centre of the space left
        over. `justify-between` cannot do that: it parks the switcher against
        the mark, and the bar shifts it again every time the right side changes
        width.

        Under 640px the mark leaves the bar, signed in. The switcher, Settings
        and the Avatar already fill a 375px line, and the mark is the one of
        the four that repeats itself: "My prototypes" goes to the same route.
        A Guest has no switcher, so a Guest keeps the mark at every width.
      -->
      <div
        class="min-w-0 items-center"
        :class="account ? 'hidden sm:flex sm:flex-1 sm:basis-0' : 'flex'"
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
          <!--
            The wordmark hides under 640px, for a Guest too. It repeats a name
            the tab title already gives, and it costs the width the About /
            Sign in pair needs on a phone.
          -->
          <span class="hidden text-base-medium text-ink-gray-8 sm:inline"
            >Sketch</span
          >
        </router-link>
      </div>

      <!--
        The gallery switcher, signed in only. A Guest has no gallery of their
        own, so there is nothing to switch between and the bar keeps the
        About / Sign in pair instead.

        `ghost` paints no track. The pair reads as two labels on the bar, and
        only the open one carries a surface. `subtle` boxed them in a grey
        rail, which put a second border across a bar that already has one.
        `sm` is 28px, so the switcher sits inside the 48px bar without setting
        its height. The pill follows the route, so it never moves on hover and
        the bar never changes height.
      -->
      <TabButtons
        v-if="account"
        v-model="gallery"
        :options="galleries"
        size="sm"
        variant="ghost"
      />

      <div class="flex flex-1 basis-0 items-center justify-end gap-2">
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
          class="hidden sm:inline-flex"
          icon-left="lucide-settings"
          label="Settings"
          route="/settings"
          theme="gray"
          variant="ghost"
        />

        <!--
          The same control, icon only, under 640px. The two gallery labels
          take the width the "Settings" label used to have, and one 32px
          target beside the Avatar is the mobile shape for a bar action
          anyway. `label` stays: on an icon-only Button it becomes the
          `aria-label` (`Button.vue:334`), so the control is still named to a
          screen reader.
        -->
        <Button
          v-if="account"
          class="sm:hidden"
          icon="lucide-settings"
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
