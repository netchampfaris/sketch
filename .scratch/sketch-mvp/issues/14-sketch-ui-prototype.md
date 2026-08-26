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
- The Public toggle, showing the resulting `/<username>/<slug>` URL.
- Username on the settings page: shown, and the copy for why it cannot
  collide with the reserved list.

URL layout is decided: the SPA serves at the site root `/`, Prototypes at
`/<username>/<slug>`.
