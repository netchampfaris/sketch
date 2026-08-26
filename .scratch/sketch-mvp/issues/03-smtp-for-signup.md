# Configure an SMTP provider for verification emails

Type: task
Status: claimed
Blocked by: 01

## Question

HITL. Faris picks a provider (Resend, Postmark, Mailgun, Gmail app password). Agent hands over the checklist, then creates the Email Account on sketch.localhost with the provided credentials stored only in site_config or the doc, never in the repo. Record: provider, sender address, test email result.

## Comments

### 2026-08-26 — handover checklist (agent)

Claimed. Blocked on Faris: pick a provider and hand back the values below.
Nothing else in this ticket needs a decision.

**Step 1. Pick one.**

| Provider | Sender domain needed | Free tier | Notes |
|---|---|---|---|
| Resend | yes, DNS records on `netchamp.dev` | 100/day, 3000/month | API-first, SMTP also offered |
| Postmark | yes | 100/month | Best deliverability record for transactional mail |
| Mailgun | yes | trial only, then paid | |
| Gmail app password | no, sends as your Gmail | n/a | Fastest to set up. Gmail rate limits and rewrites the From header. Fine for testing, weak for open signup |

Sketch has open signup at `sketch.netchamp.dev`, so verification mail goes to
strangers. A real domain sender beats the Gmail path.

**Step 2. Set up the sender.** For Resend, Postmark, or Mailgun: add the
sender domain (suggest `netchamp.dev` or a `mail.` subdomain) and publish the
SPF, DKIM, and DMARC records the dashboard gives you. Wait for the dashboard
to show the domain verified.

**Step 3. Hand back these seven values.**

1. Provider name
2. SMTP host
3. SMTP port
4. TLS mode: STARTTLS or implicit SSL
5. SMTP username
6. SMTP password or API key
7. Sender address, e.g. `sketch@netchamp.dev`

Take the host, port, and TLS mode from the provider dashboard. Do not
guess them.

**Step 4. Agent does the rest.** On receipt the agent will:

- Create an `Email Account` on `sketch.localhost` named `Sketch Outgoing`
  with `enable_outgoing`, `default_outgoing`,
  `always_use_account_email_id_as_sender`, and the TLS flag
  (`use_tls` for STARTTLS, `use_ssl_for_outgoing` for implicit SSL).
- Store the password in the doc's `Password` field, encrypted by Frappe.
  Nothing lands in the repo.
- Send a test email to `netchamp.faris@gmail.com` and paste the real result.
- Record provider, sender address, and test result in the `## Answer` block.

Not done yet: nothing beyond the checklist. The Email Account is not created
and no mail has been sent.
