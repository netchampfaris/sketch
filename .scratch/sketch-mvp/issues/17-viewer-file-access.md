# How the Viewer and the checker read a private Prototype's files

Type: grilling
Status: open
Blocked by: 12 (resolved — unblocked)

## Question

The Viewer fetches a Prototype's source tree in the browser. Ticket 04 fetched
a `files.json` from disk; ticket 10 kept that. The MVP needs the real thing.

Decide:

- The endpoint the Viewer fetches to get `{ path: source }` for one Prototype,
  and how it is authorised for the owner, for a public link, and for neither.
- How the ticket 10 checker, a headless Chromium with no session, opens a
  **private** Prototype. Options: a short-lived signed URL minted per check, a
  cookie planted in the browser context, or the checker running as the owner
  through the same Sketch Token.
- Whether the Viewer's own HTML is served by a Frappe route per Prototype
  (`/u/<username>/<slug>`) or is one static page that reads the Prototype from
  the URL.
- Where the files live on disk under the site, and what the API does when a
  file has been deleted mid-check.

Ticket 12 decided the doctypes, the role, and that public links serve with
`ignore_permissions` after checking `is_public`. This ticket decides the wire.
