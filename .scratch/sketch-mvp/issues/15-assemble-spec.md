# Assemble the MVP spec

Type: task
Status: open
Blocked by: 17 (01, 02, 04, 05, 06, 08, 09, 10, 11, 12, 13, 14, 16 resolved; 03 removed; 07 closed out of scope)

## Question

Write `apps/sketch/.scratch/sketch-mvp/spec.md` from every resolved ticket. It must let /implement build the MVP without new decisions. Include: doctypes, MCP tools, Runtime layout, check step, Sketch screens, signup flow, deployment on this box. No Fixture API: ticket 07 closed it, and all fixture data is inline in `ref`s. Close the map.

## Comments

### 2026-08-27 — from ticket 11

The spec must carry these, none of which are in the tickets they contradict:

- The skill is `sketch/skill/frappe-ui.md` in **app source**, not in the
  Runtime folder. Ticket 12's comment on ticket 11 says otherwise and is
  superseded.
- `get_skill()` takes **no arguments**. Ticket 08's tool table says
  `get_skill(prototype)` and is superseded.
- **Dark mode is in the MVP.** The Viewer resolves a `theme` URL parameter,
  then `localStorage['theme']`, then `prefers-color-scheme`, and sets
  `data-theme` on its own `<html>`. `check` forces light.
- The Runtime resolves **eight** specifiers, not four. Ticket 04's list is
  superseded, and so are its measured sizes.
- The **Sketch UI creates Prototypes**, with a recipe picker. Ticket 08
  recorded creation as an agent-only act. Ticket 08 and ticket 14 both carry
  amendments; the recipe set itself is still undecided.
