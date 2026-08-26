# How Frappe develop handles open signup and email verification

Type: research
Status: claimed
Blocked by: 

## Question

Read /home/faris/benches/frappe-bench/apps/frappe (develop). Report: the Website Settings and System Settings flags that allow signup, how email verification works after signup, which role a new user gets and how to change it, and how to redirect a new user to the Sketch frontend instead of Desk. Note anything that differs from version-16.

## Comments

### 2026-08-26 — claim is stale, scope widened

This ticket was claimed during charting and produced nothing. There is no
file in `../research/`. Re-fire it.

Added scope from ticket 08: signup must also collect a **unique Username**,
validated against a reserved list. Report how the Frappe develop signup path
can be extended to ask for it, and whether `User.username` can be made a hard
requirement given `validate_username` blanks it on collision
(`frappe/core/doctype/user/user.py:766-781`).
