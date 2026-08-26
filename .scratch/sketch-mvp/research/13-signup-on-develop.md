# How Frappe develop handles open signup, verification, roles, and landing

Ticket: `apps/sketch/.scratch/sketch-mvp/issues/13-signup-on-develop.md`
Frappe A: `/home/faris/benches/frappe-bench/apps/frappe`, branch `develop`, HEAD `6f6fd317d5`
(2026-07-22, 928 commits behind `upstream/develop`). This is the tree the ticket names.
Frappe B: `/home/faris/benches/sketch-bench/apps/frappe`, branch `develop`, HEAD `0219b2224e`
(2026-08-26). **This is the tree Sketch actually runs on.** B is newer than A.
Frappe C: same repo as A, branch `version-16`, HEAD `543d9cd90d`, for the version-16 diff.

Citations give the A line number first, then the B line number when it shifts. Everything below
was read in the checkouts, not from memory.

## Gist

- Two flags gate signup. Website Settings `disable_signup` (Check, **default 1**) and System
  Settings `max_signups_allowed_per_hour` (Int, default 300). Set `disable_signup = 0` to open it.
- Verification is a password-reset link, not a separate "verify email" token. The welcome mail
  carries `/update-password?key=<plaintext>`. Only the SHA-256 hash is stored. The link expires
  after System Settings `reset_password_link_expiry_duration` (Duration, default 1200 s = 20 min).
  Clicking it sets the password **and logs the user in**.
- With no outgoing Email Account, signup **still succeeds and returns HTTP 200**. The user sees a
  green success banner reading "Please ask your administrator to verify your sign-up", plus a
  desk-oriented alert toast. An Error Log row is written. Nothing tells the user the mail failed.
- A new signup gets `user_type = "Website User"` (hardcoded) and the single role in Portal
  Settings `default_role`. That is the supported hook point for `Sketch User`.
- `Sketch User` **must have `desk_access = 0`**. `Role.desk_access` defaults to 1, and
  `User.set_system_user()` flips `user_type` to `System User` on the next save if any held role
  has desk access. `add_roles()` calls `save()`, so the flip happens during signup.
- `website_route_rules` **cannot claim `/`**. Only `get_home_page()` decides what `/` renders.
  Use the `home_page` hook in Sketch's `hooks.py`, plus a `page_renderer` or route rules for
  deep links.
- There is **no hook that adds a field to core's signup payload**. Two workarounds, ranked in
  section 5. The clean one is `override_whitelisted_methods`.
- Versus `version-16`: signup, roles, user_type, and landing are unchanged. The only real deltas
  are auth-mail related (no mail to disabled users, redesigned templates) and the login form now
  posts to `/api/method/login` instead of `cmd=login`.

## 1. Flags that allow open signup

### Website Settings `disable_signup` (the only real gate)

- Field: `frappe/website/doctype/website_settings/website_settings.json:251-257`, Fieldtype
  `Check`, **`"default": "1"`**, label "Disable signups". Typed at `website_settings.py:36`.
- Read by `is_signup_disabled()`: A `frappe/website/utils.py:206-207`, B `:215-216`.
  One line: `return frappe.get_website_settings("disable_signup")`.
- Enforced server-side at the top of `sign_up`: A `frappe/core/doctype/user/user.py:1116-1117`,
  B `:1125-1126`. Throws `_("Sign Up is disabled")`, title `_("Not Allowed")`.
- Enforced client-side in the login page: `frappe/www/login.py:45` puts it in the context,
  `frappe/www/login.html:113,129,138,141,206` hides the Sign up link and replaces the signup
  form with a "Signups have been disabled" card.
- Also gates social-login signup: `frappe/integrations/doctype/social_login_key/social_login_key.py:255-260`.
- A fresh site keeps the default `1`. Only `frappe.utils.install.before_tests` sets it to `0`
  (`frappe/utils/install.py:149`), and that runs for tests only. **Sketch must set it explicitly.**

### System Settings `max_signups_allowed_per_hour` (the throttle)

- Field: `frappe/core/doctype/system_settings/system_settings.json`, Fieldtype `Int`,
  default `300`.
- Read at A `user.py:1126-1135`, B `:1135-1144`. Compares against
  `frappe.db.get_creation_count("User", 60)`. Over the cap, `sign_up` calls
  `frappe.respond_as_web_page(..., http_status_code=429)`. Note it does **not** return, so the
  code below still runs in the same request.
- A second, unrelated throttle runs in `User.before_insert`:
  `throttle_user_creation()` at A/B `user.py:207-209`.

### Flags that do NOT gate signup

- System Settings `disable_user_pass_login` (Check, default 0) hides the password login form and
  the "Sign up" link next to it (`login.py:47`, `login.html:113,129`), but `sign_up` itself
  ignores it.
- System Settings `login_with_email_link` (Check, default 1) is a separate passwordless login,
  not signup.
- Portal Settings `default_role` decides the role, not whether signup is allowed (section 3).

## 2. Email verification after signup

### The code path

1. `frappe/templates/includes/login/login.js:40-57` posts
   `cmd=frappe.core.doctype.user.user.sign_up` with `email`, `full_name`, `redirect_to`.
2. `sign_up` (A `user.py:1114-1164`, B `:1123-1173`) builds the User with `enabled: 1`,
   `new_password: random_string(10)`, `user_type: "Website User"`, then `user.insert()`.
3. `User.after_insert` (A/B `user.py:211-214`) sends **no mail**. It only creates Notification
   Settings and clears two cache keys.
4. `User.on_update` (A/B `user.py:327-333`) calls `send_password_notification(self.__new_password)`.
5. `send_password_notification` (A/B `user.py:457-494`) runs only when `flags.in_insert` is set.
   It stores the random password, then checks the gate at `user.py:468-472`:
   `not self.flags.no_welcome_mail and cint(self.send_welcome_email) and not self.flags.email_sent`.
   `send_welcome_email` is a User field, default `"1"` (`user.json`). `sign_up` sets neither flag,
   so the gate passes.
6. `send_welcome_mail_to_user` (A `user.py:526-551`, B `:530-556`) mints the link with
   `self._reset_password()` and picks the subject.
7. `send_login_mail` (A `user.py:553-597`, B `:560-604`) calls `frappe.sendmail`.
   `user.py:555-556` returns early for a disabled user.
8. `now` is not passed for the welcome mail, so `delayed = self.flags.delay_emails` (falsy).
   `frappe/email/__init__.py:224-225` turns that into `now = True`. The queue row is sent from
   `frappe.db.after_commit` (`frappe/email/__init__.py:271-274`), inside the signup request.

Flags that suppress the mail: `flags.no_welcome_mail` (set by the setup wizard at
`frappe/desk/page/setup_wizard/setup_wizard.py:334` and by social login at
`frappe/utils/oauth.py:345`, so **social signups get no welcome mail**), the `send_welcome_email`
field, `flags.email_sent`, and `self.enabled`.

### The template

- Default: `template="new_user"` (A `user.py:545`, B `:549`), resolved by
  `frappe/utils/jinja.py:79-93` to `frappe/templates/emails/new_user.html`. No `.txt` twin.
- `with_container=True` wraps it in `frappe/templates/emails/standard.html` through
  `get_formatted_html` (`frappe/email/email_body.py:406-441`). CSS comes from the
  `email_css = ["email.bundle.css"]` hook (`frappe/hooks.py:53`).
- **B only:** the welcome and reset mails pass `wrapper="templates/emails/auth_email.html"`
  when no custom template is set (B `user.py:526,554`). `frappe/templates/emails/auth_email.html`
  is a new branded auth wrapper. B also passes `app_name=get_brand_name() or "Frappe"`
  (B `user.py:554`), and B's `new_user.html` reads "Welcome to {app_name}" with a "Complete
  registration" button. A's copy is the older "Complete your registration".
- Subject: the `welcome_email` hook can return **only a subject string** (A `user.py:531-533`).
  Otherwise `_("Welcome to {0}").format(site_name)`, else `_("Complete Registration")`.
- Full replacement: System Settings **`welcome_email_template`** (Link to `Email Template`,
  `system_settings.json:573-578`), read at A `user.py:541`, B `:545`. When set, `send_login_mail`
  passes `template=None` and `content=<rendered Email Template>`, and the Email Template's own
  `subject` **overrides** the computed subject (A `user.py:583`).
  A resolves it with `get_email_template(...)`; B resolves it with
  `frappe.get_doc("Email Template", ...).get_formatted_email(...)` (B `user.py:587-589`).
- Jinja context available to a custom template: `first_name`, `user`, `title`, `login_url`,
  `created_by`, `link`, `site_url` (A `user.py:565-573`), plus `app_name` on B.
- The sibling field `reset_password_template` covers the forgot-password mail only.
- The Notification doctype is not involved.

### What the user clicks

- Built in `User._reset_password` (A `user.py:493-509`, B `:493-509`):
  - `key = frappe.generate_hash()`, `hashed_key = sha256_hash(key)`.
  - `db_set("reset_password_key", hashed_key)`. **Only the hash is stored.**
  - `db_set("last_reset_password_key_generated_on", now_datetime())`.
  - `url = "/update-password?key=" + key`.
  - `link = get_url(url, allow_header_override=False)`. Header override is off to stop
    Host-header poisoning of the link.
- Route `/update-password` is `frappe/www/update_password.py` + `frappe/www/update-password.html`.
  The page reads the key from the query string and posts it to
  `frappe.core.doctype.user.user.update_password` (`update-password.html:161-165`).
- `update_password` (A `user.py:941-999`, B `:951-1009`), whitelisted `allow_guest=True,
  methods=["POST"]`:
  - `_get_user_for_update_password` (A `:1070-1093`, B `:1079-1102`) re-hashes the key and looks
    up the User by `reset_password_key`.
  - Unknown key: "The reset password link has either been used before or is invalid".
    Expired: "The reset password link has been expired". Both return **HTTP 410**.
  - Rejects reuse of the current password, sets the new one, clears
    `reset_password_key` and `redirect_url` (`reset_user_data`).
  - `frappe.local.login_manager.login_as(user)`. **The user is logged in by this call.**
  - Returns the landing URL. See section 4.
- Expiry: System Settings **`reset_password_link_expiry_duration`**, Fieldtype `Duration`,
  **default `1200`** seconds. Read at A `user.py:1080-1082`. `0` or empty disables expiry.
  The same 20-minute window applies to the welcome link, because it is the same key.
  **B only:** `password_reset_mail` passes `expiry_minutes` into the template so the mail
  states the window (B `user.py:518-527`). The welcome mail does not.

### If SMTP is not configured

- Lookup chain: `frappe.sendmail` -> `QueueBuilder.process` ->
  `QueueBuilder.get_outgoing_email_account` (A `frappe/email/doctype/email_queue/email_queue.py:761-768`,
  B `:764-771`, called with `_raise_error=True`) -> `EmailAccount.find_outgoing`
  (`frappe/email/doctype/email_account/email_account.py:506-534`).
- Order: sender email match, then `append_to` doctype match, then `find_default_outgoing()`
  (`email_account.py:536-541`): an Email Account with `enable_outgoing=1, default_outgoing=1`,
  else site-config `mail_server` via `find_from_config`, else a dummy account **only when emails
  are muted**.
- Nothing found: `email_account.py:530-534` throws
  `_("Please setup default outgoing Email Account from Tools > Email Account")` with
  `frappe.OutgoingEmailError` (`frappe/exceptions.py:59-60`, `http_status_code = 501`).
- This throw happens **synchronously inside the signup request**, at queue-build time.
- `sign_up` does **not** catch it. `User.send_password_notification` does, at A `user.py:481-487`,
  B `:487-494`: `frappe.clear_last_message()`, then a `msgprint(..., alert=True)`, then
  `self.log_error("Unable to send new password notification")`.
- Net effect: **signup succeeds silently.** `flags.email_sent` is never set, so `sign_up` returns
  `(2, "Please ask your administrator to verify your sign-up")` with HTTP 200. `login.js:351-360`
  treats only `message[0] == 0` as an error, so the browser shows a **green success banner**.
  The user also sees a stray alert toast written for desk admins
  (`frappe/public/js/frappe/request.js:501-510`).
- Side effect: `_reset_password()` already wrote `reset_password_key` before the mail failed.
  A valid but undelivered key sits on the record and expires in 20 minutes.
- Related switches: `frappe.are_emails_muted()` (`frappe/__init__.py:1363-1364`, `flags.mute_emails`
  or site config `mute_emails`) makes `find_default_outgoing` return a dummy account, so **no
  throw**, and the queue row stays "Not Sent". `frappe.in_test` without `frappe.flags.testing_email`
  skips the SMTP call. The `override_email_send` hook can replace the transport
  (`email_queue.py:246-247`). There is no `developer_mode` branch on this path.
- If SMTP is configured but the send fails later, the row is marked Error and retried by the
  scheduled `frappe.email.queue.flush` (`frappe/hooks.py:244`). Invisible to the user.

### Enabled state

- The user is created **enabled** (`"enabled": 1`, A `user.py:1144`). There is no separate
  "email verified" field. The reset key is the only verification token.
- The account is live but not password-usable: the password is a server-side
  `random_string(10)` that nobody sees. Password login only works after the link is used.
- Login paths that skip the password (social login, `frappe.www.login.send_login_link`) work
  immediately, because `enabled = 1`. **This is the hole to be aware of.** An unverified address
  can be claimed if any social provider is enabled.

## 3. Role and user_type on signup

### What core does

- `sign_up` hardcodes `"user_type": "Website User"` in the insert dict (A `user.py:1146`).
- After insert, A `user.py:1153-1156`:
  ```python
  default_role = frappe.get_single_value("Portal Settings", "default_role")
  if default_role:
      user.add_roles(default_role)
  ```
- `Portal Settings` is a Single. Fields: `default_role` (Link to `Role`) and
  `default_portal_home` (Data), plus menu tables
  (`frappe/website/doctype/portal_settings/portal_settings.json`). `default_role` has **no
  default value**, so out of the box a signup gets **zero roles**.
- `add_roles` (A `user.py:712-716`, B `:722-726`) appends and then calls `self.save()`.

### The trap: `desk_access`

- `save()` re-runs `User.validate`, which calls `set_system_user()` at position 5 of the chain
  (A `user.py:231`).
- `set_system_user` (A/B `user.py:410-421`) ends with:
  ```python
  self.user_type = "System User" if self.has_desk_access() else "Website User"
  ```
- `has_desk_access` (A/B `user.py:438-447`) counts held roles where `Role.desk_access == 1`.
- **`Role.desk_access` is a Check with `"default": 1`** (`frappe/core/doctype/role/role.json:71-77`).
- So a `Sketch User` role created without `desk_access = 0` flips the fresh signup to
  `System User` during `add_roles`, and every later save keeps it there. Sketch's role fixture
  must set `desk_access: 0`.

### Supported hook points to set `Sketch User` / Website User

Ranked, all read in the code:

1. **Portal Settings `default_role = "Sketch User"`.** The only point core calls by design
   (A `user.py:1154`). Set it in Sketch's `after_install`, or ship it as a fixture. One role only.
2. **`doc_events` on `User.after_insert` or `User.validate`.** `Document.hook` composes app
   handlers after the core method (`frappe/model/document.py:2070-2095`). Use this to add extra
   roles or to assert `user_type`. This is the same mechanism ticket 12 chose for the Username
   check, so the two live side by side.
3. **`override_whitelisted_methods` on `sign_up`.** Full control of the insert dict. See
   section 5. This is the option that also solves the Username field.
4. **A `User Type` doctype record.** If `user_type` names a non-standard `User Type`,
   `set_system_user` takes the `set_roles_and_modules_based_on_user_type` branch
   (A `user.py:414-418`) and the role comes from the User Type. Heavier than needed here.
5. **Domain fixtures** write `Portal Settings.default_role` from a `default_portal_role` key
   (`frappe/core/doctype/domain/domain.py:99-103`). Not worth using.

Social login is a separate path with its own copy of the same logic:
`frappe/utils/oauth.py:347-348` also reads `Portal Settings.default_role`, and sets
`flags.no_welcome_mail` at `:345`.

## 4. Landing on the SPA at `/` instead of Desk

### Where the post-login target is decided

`LoginManager.set_user_info`, A `frappe/auth.py:195-223`, B `:196-224`:

```python
if self.info.user_type == "Website User":
    frappe.local.response["message"] = "No App"
    frappe.local.response["home_page"] = get_default_path() or "/" + get_home_page()
else:
    frappe.local.response["message"] = "Logged In"
    frappe.local.response["home_page"] = get_home_page() or "/desk"
...
if not resume and (redirect_to := frappe.cache.hget("redirect_after_login", self.user)):
    frappe.local.response["redirect_to"] = redirect_to
    frappe.cache.hdel("redirect_after_login", self.user)
```

Note the asymmetry: Website Users consult `get_default_path()` **first**, System Users do not.

Client side, `frappe/templates/includes/login/login.js:320-345`. For `"No App"` the order is
`data.redirect_to`, then `localStorage.last_visited` or the `redirect-to` arg, then
`data.home_page`.

Other entry points that pick a landing URL:
- Already-logged-in user hits `/login`: `frappe/www/login.py:26-38`.
  `get_default_path() or get_home_page()` for Website Users, `get_default_path() or "/desk"`
  for System Users. `sanitize_redirect` (`login.py:202-224`) rewrites off-host targets to `/desk`.
- After the verification link: A `user.py:996-999`, B `:1005-1009`.
  `get_default_path() or "/desk"` for System Users, else
  `redirect_url or get_default_path() or get_home_page()`.
- OAuth / email-link login: `redirect_post_login` at `frappe/utils/oauth.py:365-373`.

### `get_home_page()` resolution order

A `frappe/website/utils.py:98-143`, B `:99-152`. In order, first hit wins:

0. `frappe.local.flags.home_page` (request-local override), skipped in tests.
1. `Role.home_page` for any role the user holds (A `:107-110`). Data field on the Role doctype.
2. Portal Settings `default_portal_home` (A `:114`).
3. Hooks, via `get_home_page_via_hooks` (A `:146-171`, B `:155-180`), in this order:
   a. `get_website_user_home_page` (dotted path, called with `frappe.session.user`)
   b. `website_user_home_page` (plain string, only if (a) is absent)
   c. `role_home_page` (dict `{role: path}`, first matching role wins)
   d. `home_page` (plain string)
4. Website Settings `home_page` (Data field, A `:122`).
5. Fallback `"login"` for Guest, `"me"` otherwise. `"me"` becomes `"desk"` for a System User
   (A `:128-129`) and `"portal"` for a portal user (A `:130-131`).
6. **`User.default_workspace` overrides everything above** (A `:133-136`). If set, the return is
   `/desk/<slug>` from `get_url_to_workspace`. Leave it empty.

The return value has **no leading slash** except in the `default_workspace` branch. That is why
`auth.py:205` writes `"/" + get_home_page()`.

Caching: `frappe.cache.hget("home_page", frappe.session.user, ...)` (A `:143`), bypassed when
`frappe._dev_server`. `"home_page"` is in `user_cache_keys` (`frappe/cache_manager.py:56`), so
`frappe.clear_cache(user=...)` flushes it. Role edits flush it
(`frappe/core/doctype/role/role.py:53-58`). Hook changes need `bench clear-cache`.

### `get_default_path()` beats `get_home_page()` for Website Users

`frappe/apps.py:92-110`:

```python
apps = get_apps()
_apps = [app for app in apps if app.get("name") != "frappe"]
if len(_apps) == 0: return None
system_default_app = frappe.get_system_settings("default_app")
user_default_app = frappe.get_cached_value("User", frappe.session.user, "default_app")
...
if len(_apps) == 1: return _apps[0].get("route") or "/desk"
elif is_desk_apps(_apps): return "/desk"
return "/apps"
```

- `get_apps()` (`frappe/apps.py:36-73`) lists only apps that declare the `add_to_apps_screen`
  hook and pass their own `has_permission` callable.
- So **if Sketch declares `add_to_apps_screen` with `"route": "/"`, `get_default_path()` returns
  `/` for both user types and wins at `auth.py:205`.** That is the shortest lever.
- If Sketch declares no `add_to_apps_screen`, `get_default_path()` returns `None` for a
  frappe-only site and `get_home_page()` decides.
- System Settings `default_app` (Select) and User `default_app` (Select, "Redirect to the
  selected app after login") also feed this function.

### Serving the SPA at `/`

`frappe/website/path_resolver.py:183-198`:

```python
def resolve_path(path):
    if not path:
        path = "index"
    ...
    if path == "index":
        path = get_home_page()
    frappe.local.path = path
    if path != "index":
        path = resolve_from_map(path)
    return path
```

- **`website_route_rules` cannot claim `/`.** `resolve_from_map` is skipped while the path is
  still `"index"`. A `{"from_route": "/"}` rule never fires.
- `index.html` in `public/` is never served. `StaticPage` scans only each app's `www/` folder and
  refuses `html`, `css`, `js`, `json`, `md`, `txt`, `xml`
  (`frappe/website/page_renderers/static_page.py:12-23,37-55`).
- Website Settings `home_page` is validated on save. `validate_home_page`
  (`website_settings.py:76-85`) runs `PathResolver(...).is_valid_path()` and **silently blanks**
  anything it cannot resolve.

Recipe, all parts verified in code:

1. Set `home_page = "sketch"` in Sketch's `hooks.py` (matched at `frappe/website/utils.py:163-166`)
   and ship `sketch/www/sketch.html` + `sketch/www/sketch.py` with `no_cache = 1`.
   `/` then renders the SPA shell with no redirect. The URL stays `/`.
   Alternative: declare `add_to_apps_screen` with `"route": "/"` and let `get_default_path()` win.
2. Deep links (`/u/<username>/<slug>`) need their own `website_route_rules` entries, or a
   `page_renderer` hook. Only `/` goes through the home-page branch. Sketch already plans a
   `page_renderer` for `/mcp` (ticket 09), so a second renderer is consistent.
3. Keep every `Sketch User` role at `desk_access = 0` so `user.py:421` classifies the user as a
   Website User.
4. Leave `User.default_workspace` empty. It overrides everything (`website/utils.py:133-136`).
5. Leave `Role.home_page` and Portal Settings `default_portal_home` empty. They beat the hooks.
6. Signup already carries a redirect. `sign_up` writes `redirect_after_login` into the cache
   (A `user.py:1158-1159`) from the `redirect_to` argument. `update_password` reads it
   (A `user.py:985-989`) and `set_user_info` reads it (A `auth.py:216-218`). So passing
   `redirect_to=/` at signup lands the user on the SPA right after they click the mail link.

### What forces a user back to Desk

- `auth.py:210` and `login.py:34`, both `"/desk"` for System Users.
- `website/utils.py:128-129`, the `"me"` fallback becomes `"desk"` for System Users.
- `website/utils.py:133-136`, `User.default_workspace` always yields `/desk/...`.
- `frappe/apps.py:106-109`, `get_default_path()` returns `/desk` when the only app routes are
  Desk-shaped (`DESK_APP_PATTERN = ^/desk(/.*)?$`, `apps.py:19`).

`user_type = "Website User"` stops all of them:
- `auth.py:201-205` never produces `/desk`.
- `frappe/www/desk.py:26-27` throws `frappe.PermissionError` if a Website User opens `/desk`.
- `path_resolver.py:33-35` hardcodes `desk` and `desk/*` to the desk TemplatePage before any
  route resolution, so `/desk` cannot be re-pointed.

## 5. Collecting a unique Username at signup

**There is no clean extension point.** Core's `sign_up` has a fixed signature
`sign_up(email: str, full_name: str, redirect_to: str)` (A `user.py:1115`, B `:1124`) and the
core client sends exactly those three arguments (`login.js:43-46`). No hook adds a field to it.

Three workarounds, best first.

### Option A: `override_whitelisted_methods` (recommended)

- The hook exists on develop: `frappe/hooks.py:397` declares the dict,
  `frappe.override_whitelisted_method` resolves it at `frappe/__init__.py:1474-1477`.
- It is applied on every entry path the login page uses:
  `frappe/handler.py:68` for `cmd=` form posts, `frappe/api/v2.py:54` and
  `frappe/api/discovery.py:70` for `/api/method/...`.
- Sketch's `hooks.py`:
  ```python
  override_whitelisted_methods = {
      "frappe.core.doctype.user.user.sign_up": "sketch.api.sign_up",
  }
  ```
- The override receives whatever the client posts, so
  `sign_up(email: str, full_name: str, username: str, redirect_to: str)` works.
- **Type annotations are mandatory.** `require_type_annotated_api_methods = True`
  (A `frappe/hooks.py:159`, B `:192`), enforced at `frappe/utils/typing_validations.py:44`.
- The override must re-implement the guards core provides: `is_signup_disabled()`, the
  `max_signups_allowed_per_hour` check, the existing-user branches, and
  `flags.ignore_password_policy`. Copy them from `user.py:1116-1164`.
- Set `username` in the insert dict. Ticket 12's `doc_events` hook on `User.validate` then runs
  after core's `validate_username` and throws if core blanked the value.

### Option B: `signup_form_template` hook plus a rebound submit handler

- The hook is real and read at `frappe/www/login.py:52-61`:
  ```python
  signup_form_template = frappe.get_hooks("signup_form_template")
  if signup_form_template and len(signup_form_template):
      path = signup_form_template[-1]
      if not guess_is_path(path):
          path = frappe.get_attr(signup_form_template[-1])()
  else:
      path = "frappe/templates/signup.html"
  context["signup_form_template"] = frappe.get_template(path).render()
  ```
- The value is either a template path or a dotted path to a callable that returns one.
- The default is `frappe/templates/signup.html`, which holds only `#signup_fullname` and
  `#signup_email`. A Sketch template can add `#signup_username`.
- **The form field alone is not enough.** The submit handler lives in core
  `frappe/templates/includes/login/login.js:40-57` and only sends `email`, `full_name`,
  `redirect_to`. The Sketch template must ship its own script that unbinds and rebinds
  `.form-signup` submit after `login.bind_events()` runs on `frappe.ready`.
- This is fragile. Core's `login.js` is not a stable API and changed shape between version-16 and
  develop (see section 6). Use Option B only for the input markup, and pair it with Option A for
  the server side.

### Option C: own the whole page

- Skip `/login#signup`. Ship `sketch/www/signup.html` + `signup.py` and one
  `@frappe.whitelist(allow_guest=True, methods=["POST"])` method.
- Most work, least coupling to core. Still must re-implement the guards from `user.py:1116-1164`
  and add `@rate_limit`.

### Username mechanics already settled (ticket 12), confirmed here

- `User.username` is a real field with `"unique": 1`
  (`frappe/core/doctype/user/user.json`). The other unique fields are `mobile_no` and `api_key`.
- `validate_username` (A `user.py:756-771`, B `:766-781`):
  ```python
  if not self.username and self.is_new() and self.first_name:
      self.username = frappe.scrub(self.first_name)
  ...
  if self.username_exists():
      if self.user_type == "System User":
          frappe.msgprint(...); self.suggest_username()
      self.username = ""
  ```
- Two consequences for Sketch:
  - Core **auto-derives** a username from `first_name` when none is given. `sign_up` sets
    `first_name` from `full_name`, so every core signup already gets a scrubbed username.
    A Sketch hook must not treat a derived value as user intent.
  - For a Website User, a collision is blanked **silently**, with no message. That silence is
    exactly what ticket 12's `doc_events` hook turns into a throw.
- `validate_username` runs at position 24 of `User.validate` (A `user.py:239`), after
  `set_system_user` (`:231`). So `user_type` is already resolved when the collision branch reads it.

## 6. Differences from version-16

Diffed `version-16` (`543d9cd90d`) against `develop` (`6f6fd317d5`) in the same repo. They are
genuinely divergent, not a fast-forward: version-16 is 2872 commits ahead of the merge-base
`fcbe4d62d6`, develop 5835.

| Area | Difference |
|---|---|
| Open signup | **None.** `sign_up()` is byte-identical. `is_signup_disabled()`, `disable_signup`, `max_signups_allowed_per_hour` all unchanged. |
| Email verification | **Yes.** See below. |
| Default role / user_type | **None functionally.** |
| Landing / redirect | **None.** |
| Extra field at signup | **None.** Both forms collect Full Name and Email only. |

### Real differences that matter to Sketch

1. **Auth mail is never sent to a disabled user.** A `user.py:554-556` adds
   `if not self.enabled: return` at the top of `send_login_mail`. version-16 sent it regardless.
   Commit `b13af27ece`.
2. **The login form no longer posts `cmd=login`.** `frappe/auth.py:131` on develop matches only
   `frappe.local.request.path == "/api/method/login"`. version-16 also accepted
   `form_dict.get("cmd") == "login"`. `login.js` posts to `/api/method/login`. Any copied
   version-16 login template will silently stop authenticating on develop.
3. **`/api/method/frappe.www.login.send_login_link` now requires an enabled user**
   (`frappe/www/login.py:172-173`). version-16 checked existence only, so a disabled user could
   still get a one-time login link.
4. **Password reuse is blocked on reset** (A `user.py:970-976`).
5. `frappe/templates/signup.html` was restyled to espresso (`es-button`, `es-alert`, visible
   labels, a new `templates/includes/login/macros.html` with an `alert_banner` macro). Field ids
   `#signup_fullname` and `#signup_email` are unchanged. Signup responses now render inline
   banners instead of `frappe.msgprint`.
6. `login.js` icon ids changed from `#es-line-preview` / `#es-line-hide` to `#icon-eye` /
   `#icon-eye-off`, because the espresso icon bundles were dropped from `hooks.py`.
7. `frappe.core.doctype.user.user.get_roles(arg=None)` was **removed** on develop. A new
   `change_password(user, new_password, logout_all_sessions=1)` was added (A `user.py:1197`).
   The desk User form no longer offers inline password change (`new_password`,
   `logout_all_sessions`, and the section break are `"hidden": 1`).
8. User doctype gained a `workspaces` child table and lost `banner_image`. Gravatar was removed
   from the framework (`d76c0aa702`).
9. `require_type_annotated_api_methods = True` and `use_json_request_body = True` are
   develop-only hooks. Both affect a custom `sign_up` override.

### Explicitly identical on both branches

- `sign_up`, `after_insert`, `set_system_user`, `has_desk_access`, `validate_username`,
  `add_roles`, `reset_password`.
- `is_signup_disabled` and the whole of `frappe/website/utils.py`, including `get_home_page`.
- `frappe/www/complete_signup.{py,html}` (an OAuth-only page, not used by the normal signup).
- All 27 files in `frappe/templates/emails/` on the local `develop`.
- Website Settings `disable_signup` / `home_page` / `show_footer_on_login` definitions.
- System Settings `welcome_email_template`, `reset_password_template`,
  `max_signups_allowed_per_hour`, `reset_password_link_expiry_duration`,
  `disable_user_pass_login`, `login_with_email_link`.
- Portal Settings `default_role` logic.
- **Desk is at `/desk` on both.** `frappe/www/desk.py` exists on both; there is no
  `frappe/www/app.py` on either. Both `hooks.py` files carry the same
  `website_redirects` mapping `/app/(.*)` -> `/desk/\1`, `/apps` -> `/desk`, `/app` -> `/desk`,
  and the same `website_route_rules` entry `/desk/<path:app_path>` -> `desk`
  (A `hooks.py:55-65`, C `hooks.py:62-72`). Do **not** write `/app` in Sketch code.

### Where Frappe A lags Frappe B (the tree Sketch runs)

Frappe A is 928 commits behind `upstream/develop`. Everything in that gap that touches this
ticket is the transactional-email redesign, and it is already present in Frappe B:

- New file `frappe/templates/emails/auth_email.html`, a branded auth wrapper.
- `send_login_mail` gains a `wrapper=` parameter (B `user.py:560`). Welcome and reset mails pass
  `wrapper="templates/emails/auth_email.html"` when no custom template is set.
- `send_welcome_mail_to_user` passes `app_name=get_brand_name() or "Frappe"` (B `user.py:554`).
- `password_reset_mail` passes `expiry_minutes` derived from `reset_password_link_expiry_duration`
  (B `user.py:518-527`).
- Custom templates resolve through `frappe.get_doc("Email Template", ...).get_formatted_email(...)`
  instead of `get_email_template(...)` (B `user.py:587-589`).
- `new_user.html`, `password_reset.html`, `login_with_email_link.html`,
  `administrator_logged_in.html` rewritten. New `two_factor_setup.html`.
- `get_home_page` batches the Role lookup with `frappe.db.get_values("Role", all_roles,
  "home_page", pluck=True)` and uses `load_user_default_workspace()` (B `website/utils.py:105-145`).
  **Same resulting landing page**, fewer queries.
- `frappe/apps.py` `get_apps` / `get_route` switch from `get_installed_apps()` to
  `get_active_apps()`, which excludes apps in the `disabled_apps` global.

**No upstream commit changes `sign_up()`, `is_signup_disabled()`, the hardcoded
`Website User` type, or the Portal Settings default role.** Every answer above holds on both
develop checkouts.

## Verification

Read on 2026-08-26. Agents read the code; the branch and commit of each tree were confirmed with
`git rev-parse` and `git log -1` before reading.

- Frappe A: `git rev-parse --abbrev-ref HEAD` -> `develop`; `git log -1` ->
  `6f6fd317d562239534ac00f213326344a8487f91` "build: target ES2020 by default (#41155)".
  `git status -sb` -> `develop...upstream/develop [behind 928]`.
- Frappe B: `develop`, `0219b2224e4c936608cf3c4b0d264512f30b2d46`
  "Merge pull request #41887 from Shllokkk/guard-duplicate-drop-index".
- Frappe C: `version-16`, `543d9cd90d`.
- The version-16 comparison used `git diff version-16..develop -- <path>` and
  `git diff develop..upstream/develop -- <path>` on Frappe A, plus
  `git ls-tree --name-only <branch> frappe/www/` to confirm `desk.py` on both and no `app.py`
  on either.
- A and B were compared file by file with `diff -u` on the eight files that matter.
  `frappe/templates/signup.html` and `frappe/templates/includes/login/login.js` are byte-identical
  between A and B.

Not verified: nothing was executed. No signup was run, no mail was sent, no setting was changed on
any site. All behaviour above is read from source. Sketch's `Sketch User` role, its
`add_to_apps_screen` route, and the `override_whitelisted_methods` override do not exist yet.
