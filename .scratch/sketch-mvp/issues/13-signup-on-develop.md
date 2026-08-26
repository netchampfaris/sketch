# How Frappe develop handles open signup and email verification

Type: research
Status: resolved
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

## Answer

Resolved 2026-08-26. Agents read the code and wrote the findings; I reviewed
them. Full report with file:line citations:
`../research/13-signup-on-develop.md` (586 lines).

The agent read three trees and named each: Frappe `develop` `6f6fd317d5` (the
tree the ticket named), Frappe `develop` `0219b2224e` (**the tree
sketch-bench actually runs**), and `version-16` `543d9cd90d`.

### Signup is two flags

- Website Settings `disable_signup`, a Check that **defaults to 1**. Set it
  to 0. Read by `is_signup_disabled()`, enforced in `sign_up`.
- System Settings `max_signups_allowed_per_hour`, default 300.
- `disable_user_pass_login` only hides the form. It does not gate `sign_up`.

### Verification is a password-reset link

There is no separate verify-email token. The welcome mail carries
`/update-password?key=<plaintext>`; only the SHA-256 hash is stored. The link
expires after `reset_password_link_expiry_duration` (default 1200 s).
Clicking it sets the password and logs the user in.

**With no outgoing Email Account, signup still returns HTTP 200 and a green
success banner.** The send error is swallowed and only an Error Log records
it. So SMTP is not optional for Sketch: without it, every new user is stuck
with no way to see why. The spec names SMTP as a setup step (map note,
ticket 03 removed) and this confirms the cost of skipping it.

### Role: use Portal Settings, and set `desk_access = 0`

A new signup gets `user_type = "Website User"` (hardcoded) and the one role
in **Portal Settings `default_role`**. That is the supported hook point for
`Sketch User`.

**Trap.** `Role.desk_access` defaults to 1, and `add_roles()` calls `save()`,
so `set_system_user()` flips the new user to System User during signup. The
`Sketch User` role fixture must set `desk_access = 0`. This amends ticket 12,
which named the role but not this field.

### Serving the SPA at `/`

`website_route_rules` **cannot claim `/`** — the resolver skips the map while
the path is `index`. Only `get_home_page()` decides what `/` renders. Use the
`home_page` hook in Sketch's `hooks.py`, or `add_to_apps_screen` with
`route: "/"` so `get_default_path()` wins. `User.default_workspace` overrides
everything, so Sketch must leave it unset. `public/index.html` is never
served.

This is the concrete recipe for the charting decision "the SPA serves at the
site root `/`, not `/sketch`".

### Username at signup: no clean hook

Core's `sign_up(email, full_name, redirect_to)` has a fixed signature and the
core client sends exactly those three. No hook adds a field.

Use `override_whitelisted_methods` to point
`frappe.core.doctype.user.user.sign_up` at a Sketch method that also takes
`username`. It is honoured on every entry path the login page uses. The
override **must** carry type annotations
(`require_type_annotated_api_methods = True`) and must re-implement core's
guards: `is_signup_disabled()`, the hourly throttle, the existing-user
branches, and `flags.ignore_password_policy`.

Pair it with the `signup_form_template` hook for the input markup only. That
hook adds markup and nothing else: core's `login.js` submit handler still
sends three arguments, so the Sketch template must rebind the submit handler
after `frappe.ready`. Core's `login.js` is not a stable API and changed shape
between version-16 and develop. Treat the rebind as the fragile part.

### One more Username fact

Core auto-derives `username` from `first_name` when none is given. So every
core signup already has a username. Ticket 12's `User.validate` hook must not
read an auto-derived value as user intent.

### Versus version-16: nothing that matters

Signup, roles, `user_type`, and landing are identical. Desk is at `/desk` on
both. The real deltas are auth-mail behaviour, the login form moving from
`cmd=login` to `/api/method/login`, password-reuse blocking, and `get_roles`
removal. Riding `develop` costs nothing here.

Nothing was executed. No signup was run, no mail sent, no setting changed.
