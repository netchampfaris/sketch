# Prototype the three Sketch screens

Type: prototype
Status: resolved
Blocked by: 12

## Question

HITL. Using the frappe-ui skill, build a throwaway prototype of the prototypes list, the fullscreen viewer route (no chrome), and the settings page with Token and connect snippet. Name the existing frappe-ui components used. Faris reacts; the answer records the agreed layout and copy.

## Comments

### 2026-08-26 — from ticket 08

Screens this ticket must now cover, beyond the original three:

- Renaming and **deleting** a Prototype. Neither is an MCP tool; the UI is
  the only place either happens.
- The Public toggle, showing the resulting `/u/<username>/<slug>` URL.
- Username on the settings page: shown, with the format rule as help text
  (3-30 characters, `[a-z0-9-]`, starts with a letter, lowercase).

URL layout is decided: the SPA serves at the site root `/`, Prototypes at
`/u/<username>/<slug>`.

### 2026-08-26 — from ticket 12

- Prototype URLs moved to `/u/<username>/<slug>`. The site root is not safe
  to hand to usernames; see the ticket 08 amendment.
- **There is no reserved username list.** It is dropped. A format rule
  replaces it, so the settings copy explains the format, not a blocklist.
- The SPA at `/` is now a recorded decision, not a scaffold default. The
  scaffold still serves `/sketch`; moving it is implementation work.
- Settings shows one Token, always readable, with a Regenerate button. It is
  not a token list: one user, one token.

## Answer

Resolved 2026-08-27 with Faris. Faris chose **B — Studio**.

### Agreed layout

- Desktop uses a persistent 14 rem sidebar. It holds the Sketch identity,
  Prototypes and Settings navigation, a small agent-connection status, and the
  signed-in User at the bottom.
- The Prototypes screen header says **Your studio**, shows the Prototype count,
  and has one solid **New prototype** action.
- Prototypes use a responsive visual gallery. Each item has a rendered-preview
  area, name, short description, updated time, Public/Private switch, and an
  overflow menu. Rename and Delete live in that menu because they are UI-only
  actions. Delete uses a destructive confirmation.
- When Public is on, the item shows a Public badge and the copyable
  `/u/<username>/<slug>` URL. Turning Public off hides the URL.
- Settings keeps the same app sidebar and header. Its body has a narrow local
  navigation column and a content column with **Profile** followed by
  **Agent connection**.
- Profile shows Username with this help text: **3–30 characters. Use lowercase
  letters, numbers, and hyphens. Start with a letter.**
- Agent connection shows one readable Token with **Copy token** and
  **Regenerate** actions, followed by the `https://sketch.netchamp.dev/mcp`
  endpoint and a **Copy config** action.
- The Viewer is the Prototype document at `/u/<username>/<slug>`. It fills the
  viewport and has no Sketch sidebar, header, account controls, or other Sketch
  chrome. Everything visible there belongs to the Prototype.

### frappe-ui components

Use `Button`, `Dropdown`, `Switch`, `FormControl`, `Avatar`, `Badge`, the
imperative `dialog` and `toast` APIs, and the modern `List`, `ListRow`, and
`ListCell` family from `frappe-ui/list`. Use semantic surface, ink, and outline
tokens throughout.

### Prototype asset

The complete A/B/C prototype is preserved on branch
`forge/proto/14-sketch-ui` at commit `4d9536d`. Run it with `yarn dev` from
`apps/sketch/frontend`; the review route is
`/sketch/prototype/sketch-ui/list?variant=B`. The prototype is a primary source,
not implementation code; `/implement` must rewrite the chosen direction.

### 2026-08-27 — amendment: recipe picker and theme control

From ticket 11. Two screens this ticket's answer does not cover.

**A "Select a Recipe" picker when a Prototype is created.** Faris asked for it.
It means the Sketch UI creates Prototypes, which the resolved layout above does
not show: creation was an agent act. Ticket 08 owns the `create_prototype`
change; this ticket owns the screen. The agent has no recipe tool, so the
picker is the only place a recipe is chosen.

**A theme control.** Dark mode is in the MVP. Sketch owns the theme, and a
Prototype is forbidden from touching it. The Sketch UI needs a `light | dark |
system` control, and frappe-ui ships `ThemeSwitcher` and `useColorScheme` for
it. It writes `localStorage['theme']`, which the Viewer reads. Decide where the
control sits: the sidebar footer next to the User, or the settings screen.
