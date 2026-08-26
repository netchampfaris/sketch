# Define the doctypes and permission model

Type: grilling
Status: open
Blocked by: 08 (resolved — unblocked)

## Question

Decide the doctypes: Sketch Prototype (owner, name, slug, pin, is_public), how files are stored (child table rows or one JSON field or File docs), Sketch Runtime (version, folder), and where the per-user Token lives (Frappe api_key/api_secret or a Sketch-owned doc). Decide the role for signed-up users and the permission rules so a user only sees their prototypes and public links bypass login.

## Comments

### 2026-08-26 — from ticket 08

Now unblocked. Constraints this ticket must satisfy:

- **Username.** Unique per user, picked at signup, prefixes every Prototype
  URL. Frappe's `User.username` is `Data`, `unique: 1`, but
  `validate_username` (`frappe/core/doctype/user/user.py:766-781`) does not
  enforce it: on collision it calls `msgprint` and sets `self.username = ""`.
  Decide whether Sketch overrides that hook, adds its own field, or validates
  on the signup path. It must be impossible to end up with no username.
- **Reserved username list.** URLs are root level, so a username sits beside
  `app`, `api`, `assets`, `files`, `private`, `login`, `method`, `mcp`,
  `sketch`, `me`, `settings`, `new`, `p`, `u`, and every Website Route on the
  site. Decide where the list lives and how a later Frappe route addition is
  prevented from shadowing an existing user.
- **Slug.** Derived from the Prototype name at creation, frozen, unique per
  user. `set_name` changes the display name only.
- **Public.** `is_public` makes the Prototype readable at
  `/<username>/<slug>` without login.
- No `delete_prototype` over MCP. Deletion is a Sketch UI act, so the
  permission rules must allow the owner to delete from the SPA.
