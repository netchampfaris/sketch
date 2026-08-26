# How Frappe develop handles open signup and email verification

Type: research
Status: open
Blocked by: 

## Question

Read /home/faris/benches/frappe-bench/apps/frappe (develop). Report: the Website Settings and System Settings flags that allow signup, how email verification works after signup, which role a new user gets and how to change it, and how to redirect a new user to the Sketch frontend instead of Desk. Note anything that differs from version-16.

## Comments

### 2026-08-26 — claim is stale, scope widened

This ticket was claimed during charting and produced nothing. There is no
file in `../research/`. Re-fire it.

Added scope from ticket 08: signup must also collect a **unique Username**.
Report how the Frappe develop signup path can be extended to ask for it.

### 2026-08-26 — from ticket 12, scope narrowed

Three parts of this ticket are already answered. Do not re-decide them;
report only how to implement them on the develop signup path.

- **Username field.** Frappe's `User.username`. A Sketch `doc_events` hook on
  `User.validate` runs after core's (`document.py:2079-2090`), sees the value
  core blanked, and throws. Scope the hook to Website Users.
- **No reserved list.** Dropped. The rule is 3-30 characters, `[a-z0-9-]`,
  starts with a letter, no doubled or trailing hyphen, lowercase-normalised.
- **Role.** New users get `Sketch User`, `user_type = Website User`.

Still open and wanted: the Website Settings and System Settings flags that
allow signup, how verification mail works on develop, how to assign the role
at signup, how to redirect to the SPA at `/` instead of Desk, and anything
that differs from version-16.
