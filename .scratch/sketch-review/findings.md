# Sketch review findings, 2026-08-29

Two agents reviewed the live site `sketch.netchamp.dev` with a fresh account
(`sketchtester`). One walked the onboarding funnel. One did a senior-designer
UI pass against the `frappe-ui` skill.

Neither agent could take screenshots. Every visual claim comes from computed
styles and `getBoundingClientRect` read in the live page.

Findings are grouped into eight tasks below. Task 9 (mobile) is out of scope.

---

## Task 1: the viewer shows its state

**1.1 An empty or broken prototype renders a blank white page. BLOCKER.**
The viewer paints nothing when the prototype has no files or fails to compile.
`runtime/viewer/boot.js:288` returns `report('empty')`. `report()` at
`boot.js:421-441` writes `window.__sketch` and posts a message. It never
touches the DOM. Verified live twice: a 0-file prototype was blank; a file with
a syntax error was also blank, with `window.__sketch.status === "compile-failed"`
and a good error object that nothing displays.
Why it hurts: the first URL an agent hands a new user is a freshly created
prototype, so the first thing the user sees is white. A broken build looks
identical to a working server.
Fix: paint the `report()` status in the viewer. A "waiting for your agent"
state for `empty`, and the compile errors for `compile-failed` / `link-failed`
/ `boot-failed`.

**1.2 There is no way back from a prototype to Sketch. Medium.**
"Open prototype" is a full page navigation into the viewer
(`frontend/src/components/PrototypeCard.vue` `openViewer()` sets
`window.location.href`). The viewer has no Sketch chrome, no link, no back
control. Confirmed at `/u/sketchtester/first-look`: the only control on the
page is the prototype's own button.
Fix: show a thin owner-only bar in the viewer with a link back to Sketch.

**1.3 Every prototype tab is titled "Prototype". Medium.**
`document.title` is the constant "Prototype" on every viewer page
(`sketch/public/runtimes/1.0.0-beta.55/viewer.html:6`, source
`runtime/viewer/viewer.html`). Several open prototypes are indistinguishable
in the tab strip and in browser history. Every shared link has the same title.
Fix: set `document.title` from `data.title` in `boot.js`, or stamp the title
into `<title>` in the renderer.

---

## Task 2: the app moves on its own

**2.1 The gallery never updates when an agent writes. High.**
A prototype created by the agent does not appear until the user reloads.
`frontend/src/pages/PrototypesScreen.vue` reloads `prototypes` on mount only.
`runtime/viewer/boot.js:130` disables the poller inside an iframe, so card
previews do not refresh either. Verified live: created "Agent hello" over MCP,
waited 8 seconds with the page open, count stayed at 2. After reload it showed 3.
Why it hurts: this is the moment the user is watching to learn whether the
connection worked, and the screen says nothing happened.
Fix: poll `list_prototypes` while the gallery is visible, using the same
revision idea the viewer already has.

**2.2 The connection state does not update without a reload. High.**
"No agent has connected yet." stays on screen after the agent connects.
`frontend/src/pages/SettingsScreen.vue:183` (`onMounted(() => agentToken.reload())`)
and `:257`. Verified live: an MCP `initialize` call stamped `last_used`; the
open page kept saying "No agent has connected yet." After a reload it said
"Last agent request: 1 minute ago."
Why it hurts: the one honest success signal in the funnel is hidden behind a
page reload the user does not know to do.
Fix: poll the connection state on `/settings`, and add a "Test connection" button.

**2.3 Regenerating the token leaves a stale "connected" signal. Medium.**
`sketch/sketch/doctype/sketch_token/sketch_token.py` `regenerate()` writes only
`token`, not `last_used`. `SettingsScreen.vue:246-258` reads `last_used`, so
Settings still says "Last agent request: N ago" while every agent is now broken.
Confirmed in code, not exercised.
Fix: clear `last_used` in `regenerate()`.

---

## Task 3: Settings page

**3.1 The Settings vertical tabs draw no selected state. High.**
Active and inactive triggers both compute `background-color: rgba(0,0,0,0)`
and `box-shadow: none`. The TabList holds 8 children and no indicator element.
Active vs inactive is only `ink-gray-8` against `ink-gray-5`.
`SettingsScreen.vue:311-320`.
Fix: give the active trigger `bg-surface-elevation-3 shadow-sm` (TOKENS: active
nav item), or use horizontal `Tabs`, which do render an indicator.

**3.2 The client snippet overflows sideways and hides the token. High.**
The Claude Code `pre` has `scrollWidth` 1241 against `clientWidth` 672 at
1280px, and 182 at 390px. The `Bearer <token>` tail sits off-screen.
`SettingsScreen.vue:348`.
Fix: `whitespace-pre-wrap break-all` on the `pre`.

**3.3 The config blocks print the token in clear text under a masked field. Medium.**
The Token field is masked until "Show" is pressed
(`SettingsScreen.vue:270-278`, masked `FormControl`), but the `<pre>` at
`:344-347` shows the whole token unmasked at all times. The masking gives false
confidence during a screen share or a screenshot.
Fix: mask the token inside the snippet too, and reveal both with the one "Show"
toggle.

**3.4 JSON blocks are whole config files with no merge guidance. Medium.**
The Cursor, Windsurf, OpenCode, VS Code and Claude Desktop blocks are complete
top-level JSON objects, and the help text says "Add this to the config file".
`SettingsScreen.vue:74-160`. A user who already has MCP servers will paste over
them and lose the others.
Fix: add one line per JSON block: "Merge the `sketch` entry into your existing
file. Do not replace it."

**3.5 A failed copy is silent. Medium.**
`copy()` has no `try`/`catch`, so a rejected clipboard write shows no toast.
`frontend/src/pages/SettingsScreen.vue:223-226`,
`frontend/src/components/PrototypeCard.vue:61-64`, `frontend/src/store.ts:71-84`.
The user believes the token is on the clipboard, pastes something else into the
config, and blames the token.
Fix: wrap `copyText` in `try`/`catch` and show an error toast with the text to
select by hand.

**3.6 The rail divider hangs 111px below the last tab. Medium.**
Last trigger bottom 930.6. TabList bottom 1042.2, because the panel's
min-height stretches the flex row. The `border-e` runs the full height.
`SettingsScreen.vue:313`.
Fix: `self-start` on the TabList, or move the border to a wrapper sized by the
tabs.

**3.7 `min-h-[22.6rem]` is an invented value and leaves 225px empty. Medium.**
361.6px reserve. The Claude Code panel's content ends at 817, the panel at 1042.
`SettingsScreen.vue:329`.
Fix: use a scale value, or let the panel size to content and accept the reflow.

**3.8 Settings content stops 44px short of the page header. Medium.**
The shell column is `max-w-[940px]` (`App.vue:43`); the settings body adds
`max-w-4xl` (896px) at `SettingsScreen.vue:237`. Section content ends at 1046
while the header border ends at 1110. Reproduced at 1024px (918 vs 962).
Fix: drop `max-w-4xl`. The shell already caps the column.

**3.9 Code blocks use the tight type scale. Medium.**
`pre` computes 12px font with a 13.8px line height. The OpenCode and Claude
Desktop snippets are 10 to 12 lines of JSON at 1.15 leading.
`SettingsScreen.vue:348`.
Fix: `text-p-xs`, or set an explicit `leading-5`.

**3.10 Client notes print raw markdown backticks. Medium.**
All 8 notes contain literal backticks, for example "`--scope user` is not
optional." `SettingsScreen.vue:61,70,88,102,120,139,147,161`.
Fix: split the note into text plus `<code>` spans, or strip the backticks.

**3.11 The claude.ai warning renders gray. Medium.**
The Alert carries `theme="amber"`, but its container computes
`bg-surface-gray-1` with `ink-gray-6` text. Only the 16px triangle icon is
`ink-amber-5`. This is frappe-ui's banner layout, so the theme buys almost
nothing. `SettingsScreen.vue:353-358`.
Fix: tint the surface with `bg-surface-amber-2 border-outline-amber-3
text-ink-amber-7` (TOKENS: tinted status block).

**3.12 There is no help or docs link anywhere in the app. Medium.**
`grep` over `frontend/src` finds one external URL, and it is inside the
OpenCode snippet. A user stuck between "I have a token" and "my agent is
connected" has nowhere to go.
Fix: add a "Help" item to the account menu that links to a setup and
troubleshooting page.

**3.13 The VS Code note is wrong. Low.**
It says "this is the one block below that carries no token"; the block is the
one being read, not one below it. `SettingsScreen.vue:106`.
Fix: reword to "this block".

**3.14 A prose sentence sits in a monospace path slot. Low.**
VS Code's path is `.vscode/mcp.json, or the user configuration file`, rendered
in `font-mono`. `SettingsScreen.vue:110`, `SettingsScreen.vue:336`.

**3.15 Helper text mixes 13px and 12px inside one card. Low.**
Token card: FormControl description 13px, then "Last agent request" 12px.
Endpoint card: 12px only. Profile: 13px then 12px.
`SettingsScreen.vue:250,255,287,379`.

**3.16 Sibling card gaps differ. Low.**
Intro to first card 20px (`mt-5`). Card to card 16px (`mt-4`).
`SettingsScreen.vue:245,280`.

**3.17 Live reload is real but unadvertised. Low.**
The owner's viewer tab polls and reloads itself when the agent writes
(`runtime/viewer/boot.js:116-166`), and no screen mentions this. The user
closes and reopens the tab after each agent turn, which is the exact work the
feature removes.
Fix: add one line to the Settings page: "Keep a prototype open. It reloads
itself while your agent writes."

**3.18 Profile fields are `max-w-md` (448px) under 856px connection cards.**
The right edge is ragged down the page. Taste, but cheap to fix.

**3.19 Settings is hidden behind an unlabelled avatar once the user connects. Low.**
The "Connect your agent" button disappears from the empty state as soon as
`last_used` is set (`PrototypesScreen.vue:88-96`), and the only remaining route
to `/settings` is the "S" avatar menu (`AppTopBar.vue`). A user who reconnects
on a second machine has to guess where the token lives.
Fix: keep a small "Agent connection" link in the top bar.

**3.20 The only route to `/settings` is labelled "Agent connection". Medium.**
The menu row says "Agent connection" (`AppTopBar.vue:62`). The page it opens is
titled "Settings" (`SettingsScreen.vue:232`) and also holds Profile.
Fix: label the row "Settings", or retitle the page.

---

## Task 4: type scale and hierarchy

**4.1 Page titles are smaller than section headings. High.**
h1 "Your prototypes" and h1 "Settings" measure 16px/600. h2 "Agent connection"
measures 17px/600. h3 "Set up your client" measures 16px/600, identical to h1.
`PrototypesScreen.vue:37`, `SettingsScreen.vue:232,239,302,368`.
Fix: page title `text-2xl-semibold` (18px), section `text-lg-semibold`,
sub-section `text-base-semibold`. DESIGN.md > Hierarchy.

**4.2 The card grid jumps 72px when data lands. High.**
Skeleton card measures 325.8px tall. A loaded card measures 397.8px. Both 438px
wide. Verified by rendering the skeleton classes in an isolated 900px grid.
`PrototypesScreen.vue:59-63`.
Fix: reserve the loaded rows (`mt-2 h-9` + `h-7`) in the placeholder, or use
frappe-ui `Skeleton` blocks at the card's real height.

**4.3 The header reports "0 prototypes" while the skeletons are on screen. Medium.**
`count` reads `prototypes.data`, which is `[]` until the call finishes.
`PrototypesScreen.vue:38-39`, `frontend/src/store.ts:20-24`.
Fix: hide the count line during `firstLoad`, or show a `Skeleton`.

**4.4 The placeholder is a hand-rolled static gray box. Low.**
`bg-surface-gray-2` with no shimmer. frappe-ui ships `Skeleton`.
`PrototypesScreen.vue:61`.

**4.5 Two "New prototype" buttons on one screen, in two different weights. Medium.**
Header button is `variant="subtle"` (137.8x28). Empty-state button is
`variant="outline"` (139.8x28). Same label, two weights, plus a third CTA
"Connect your agent". `PrototypesScreen.vue:41-47`, `PrototypesScreen.vue:100-105`.
Fix: keep the header action only, or drop the header action while the list is
empty. DESIGN.md: one primary action per screen.

**4.6 Wrapped body copy uses the single-line type scale. Medium.**
"Sketch has no editor..." renders 13px with a 14.95px line height and wraps to
2 lines. TOKENS: `text-*` is for labels, `text-p-*` for text that wraps.
`PrototypesScreen.vue:79,82`.
Fix: `text-p-sm`.

**4.7 The app's two empty states do not match. Medium.**
Prototypes: 48px circle, 24px icon, title `text-base text-ink-gray-7` (weight
420), description `text-sm` (`PrototypesScreen.vue:69-83`).
History: 40px circle, 20px icon, title `text-base font-medium text-ink-gray-8`
(weight 500), description `text-p-sm` (`PrototypeHistoryDialog.vue:92-102`).
Fix: pick one recipe. DESIGN.md > Empty state.

**4.8 Page default ink is one step too dark. Low.**
App wrapper sets `text-ink-gray-9`. TOKENS reserves gray-9 for unread titles
and KPI figures; gray-8 is the page default. Same class on the viewer body.
`frontend/src/App.vue:33`,
`sketch/public/runtimes/1.0.0-beta.55/viewer.html:33` (source
`runtime/viewer/viewer.html`).
Fix: `text-ink-gray-8`.

**4.9 Size and weight are written as two utilities. Low.**
`text-lg font-semibold` in 5 places. TOKENS says prefer the composite, which
carries tuned letter-spacing. `PrototypesScreen.vue:37`,
`SettingsScreen.vue:232,239,302,368`.
Fix: `text-lg-semibold` / `text-xl-semibold`.

**4.10 The account avatar breaks the right rail by 4px. Low.**
Avatar right edge 1086. Header button, page action button, card menu button and
dropdown all end at 1090. `AppTopBar.vue:114-118`.
Fix: `-mr-1` on the 32px hit target, or size the target to the avatar.

---

## Task 5: prototype card

**5.1 The private footer line fails contrast. High.**
"Private. Only you can open it." is `text-ink-gray-4` at 12px. Contrast on
`surface-base` is 2.85:1. AA needs 4.5:1. DESIGN.md reserves ink-gray-4 for ids
and decorative glyphs. `PrototypeCard.vue:164`.
Fix: `text-ink-gray-5`.

**5.2 "Open prototype" only exists on hover. High.**
The button is `opacity-0 group-hover:opacity-100`. There is no
`@media (hover: none)` fallback, and the preview carries a click shield with no
handler. On touch the only way in is the overflow menu.
`PrototypeCard.vue:113-121`, `PrototypePreview.vue:69`.
Fix: make the card title a router link, or show the button unconditionally
under `@media (hover: none)`.

**5.3 The footer text sits on three different left edges. Medium.**
Title, description and "Updated..." start at x=190. The private note starts at
194 (`px-1`). The public link label starts at 198 (ghost button `px-2`).
Flipping the switch moves the line 4px. `PrototypeCard.vue:150-164`.
Fix: strip the padding, or bleed the ghost button with `-mx-2` so its label
lands on 190.

**5.4 The public link path is as loud as the prototype name. Medium.**
Link label: 14px, `ink-gray-8`. Card title h2: 14px, `ink-gray-8`, weight 500.
Only weight separates them. `PrototypeCard.vue:159`.
Fix: `size="sm"` label at `text-sm text-ink-gray-5`, or replace with an
icon-only copy Button plus a tooltip.

**5.5 The state row mixes two type steps side by side. Medium.**
Left: "Updated 4 minutes ago" 12px `ink-gray-5`. Right: the Switch label 14px
`ink-gray-7`. `PrototypeCard.vue:141-148`.
Fix: drop the Switch label and let the footer line carry the state, or lift the
timestamp to `text-sm`.

**5.6 One boolean is drawn three times. Medium.**
Public/Private appears as a Badge next to the title, as the Switch label, and
as the footer sentence. `PrototypeCard.vue:130,145,159-164`.
Fix: keep the Switch plus the link row. Drop the Badge.

**5.7 Toggling Public rewrites "Updated" and reorders the gallery. Medium.**
`set_public` calls `doc.save()` (`sketch/api.py:331-336`), and the card reads
`pretty_date(modified)` (`sketch/api.py:161`). Toggling public reset the card
to "Updated 1 second ago". Verified live. The updated time no longer means "the
agent changed this", and cards move under the pointer.
Fix: sort and display on a content revision stamp, not on `modified`.

**5.8 Card subtitle leads with build jargon. Low.**
The line under each name reads "3 files - frappe-ui 1.0.0-beta.55"
(`sketch/api.py:_row`, the `description` field). The pinned library version is
the most prominent fact about a prototype, and a new user cannot act on it.
Fix: show the file count only, and move the pin into the History dialog.

**5.9 Destructive menu item is half red. Low.**
The Delete row's icon is `ink-red-7`. Its label computes `ink-gray-7`.
`PrototypeCard.vue:106`.

**5.10 `shadow-md` on the overlay button. Low.**
TOKENS assigns shadow-md to slider thumbs. A button floating over a preview is
`shadow-lg`. `PrototypeCard.vue:115`.

**5.11 The "Open prototype" button is 406px wide (`inset-x-4`).**
It reads as a bar rather than a button. Taste.

---

## Task 6: first prototype content

**6.1 The blank recipe tells the user to edit a file, but there is no editor. Medium.**
A new blank prototype says "Edit src/pages/Home.vue to start." and shows a dead
"Add a page" button with no click handler.
`sketch/recipes/blank/src/pages/Home.vue`. Seen at `/u/sketchtester/first-look`.
It contradicts the empty state on `/`, which correctly says Sketch has no editor.
Fix: change the copy to "Ask your agent to build this page" and remove the dead
button.

**6.2 The blank recipe ignores the name the user typed. Medium.**
The page heading is hardcoded to "Untitled"
(`sketch/recipes/blank/src/pages/Home.vue`). The prototype was named "First
look" and the viewer showed "Untitled".
Fix: substitute the prototype title into recipe files at create time.

**6.3 "Recipe" is unexplained, and the create dialog is titled after the wrong field. Low.**
Covered in task 7.

---

## Task 7: dialogs

**7.1 New prototype dialog: the title names the second field and uses Title Case. Medium.**
"Select a Recipe". The first and only required field is Name. Every other header
in the app is sentence case. `NewPrototypeDialog.vue:88`.
Fix: "New prototype". Add one line: "A recipe is a starting file tree your
agent can change."

**7.2 New prototype dialog: focus opens on the Close button. Medium.**
`document.activeElement` after open is `button[aria-label="Close"]`. The
required Name field never gets focus. `NewPrototypeDialog.vue:91-98`.
Fix: `autofocus` on the Name FormControl.

**7.3 New prototype dialog: two field labels, two styles. Medium.**
FormControl "Name" label: 14px, `ink-gray-5`. Hand-written "Recipe" label:
13px, `ink-gray-6`. `NewPrototypeDialog.vue:100`.
Fix: match the FormControl label, or wrap the recipe list in a
`FormControl`-style label slot.

**7.4 New prototype dialog: label-to-control gaps differ. Low.**
Name label to input: 6px. Recipe label to list: 8px (`mt-2`).
`NewPrototypeDialog.vue:100-101`.

**7.5 History dialog: rows have a hover surface but do nothing. Medium.**
`hover:bg-surface-gray-1` on a `<li>` with no click handler and no role.
`PrototypeHistoryDialog.vue:108`.
Fix: drop the hover surface, or make the row toggle the prompt.

**7.6 History dialog: the prompt column ends on three different x positions. Low.**
Timestamps are `shrink-0` with no width, so prompt right edges land at 817, 839
and 842. DESIGN.md principle 5 asks for a fixed-width trailing column.
`PrototypeHistoryDialog.vue:113-119`.
Fix: `w-20 text-right` on the timestamp span.

**7.7 History dialog: `rounded-4` and `border-b` on the same element. Low.**
The divider runs straight across a rounded corner.
`PrototypeHistoryDialog.vue:108`.
Fix: `divide-y divide-outline-gray-1` on the `<ul>`.

**7.8 History dialog: two disclosure buttons, one convention. Low.**
"3 files" carries a chevron. "Show full prompt" carries none.
`PrototypeHistoryDialog.vue:148-163`.

---

## Task 8: the signed-out surface

**8.1 No page explains what Sketch is before sign-in. High.**
Every public URL either redirects to `/login` or 404s. `sketch/www/sketch.py`
`_require_login` sends `/` to `/login?redirect-to=%2F` (301). Checked `/`,
`/index`, `/sketch`, `/about`, `/home`, `/docs`, `/help`: none serve product
copy. A first-time visitor is asked to hand over a GitHub account before
learning what the product does.
Fix: serve a short marketing page at `/` for Guests, with the sign-in button on it.

**8.2 `/login` is the stock Frappe page with no product context. High.**
The page reads "Sign In. Welcome! Please sign in to continue." over one "Login
with GitHub" button, and never says that the button also creates the account.
Branding is applied (`sketch/install.py:set_branding`, logo and favicon both
200), but the copy is core's. There is no Sketch template override.
`disable_signup = true` in the same page's script, so "Signups have been
disabled" text sits in the DOM.
Fix: override the login page. One line about Sketch. Button label "Continue
with GitHub".

**8.3 Login page copy nits. Low.**
"Sign In" is Title Case; every other header in Sketch is sentence case.
"Login with GitHub" uses "Login" as a verb, while the app menu says "Log out".

**8.4 The login page and the app use different type and colour systems. Low.**
Login computes `InterVariable` with plain `rgb()` values (h4 is
`rgb(15,15,15)`). The app computes `InterVar` with frappe-ui `color(srgb ...)`
tokens (ink-gray-8 is `rgb(23,23,23)`).
Fix: a Sketch login template built on frappe-ui tokens.

---

## Out of scope

- Task 9, mobile. At 390px the Settings client picker keeps its `w-40` desktop
  rail (`SettingsScreen.vue:313,329`). Deliberately deferred.
- The username is auto-derived, never offered, and frozen
  (`sketch/oauth_hooks.py:set_username_for_social_signup`,
  `SettingsScreen.vue:394-404`). CONTEXT.md names this as a design decision.
- The no-solid-button rule (commit `54f7fdc`) stays. Fix hierarchy with
  placement and weight, never by adding a solid button.
- `/mcp` responses set `sid=Guest`, `full_name=Guest` and `user_id=Guest`
  cookies. Harmless for a CLI client, noise for a browser-based one.

## Verified good, do not regress

- No hardcoded hex or rgb anywhere in `frontend/src`. Only two arbitrary
  values, both `max-w-[940px]`, plus `min-h-[22.6rem]` in Settings.
- Keyboard focus rings work. Tabbing shows a 2px `:focus-visible` outline.
- Card height does not change when the Public switch flips: 397.75 before,
  397.8 after.
- The card grid, top bar and page header share one 190px left edge and one
  1090px right edge.
- Disabled states work: "Copy public link" is `aria-disabled`, `ink-gray-4`,
  `cursor: not-allowed` on a private card. "Create prototype" is disabled until
  Name is filled.
- Dark mode flips cleanly. Meta text stays at 4.18:1 in both themes.
- The List in the recipe picker hides the divider next to the active row.
- The `/mcp` error JSON names the mistake, the exact header to send, and a
  `settings_url`. Keep it.
- Each client tab carries the one real gotcha for that client. Keep them.
- Private prototypes answer 404, not 403, to a signed-out visitor.
- The History dialog empty state explains who writes versions.
