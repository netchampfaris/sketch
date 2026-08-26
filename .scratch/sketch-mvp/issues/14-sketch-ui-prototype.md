# Prototype the three Sketch screens

Type: prototype
Status: open
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
