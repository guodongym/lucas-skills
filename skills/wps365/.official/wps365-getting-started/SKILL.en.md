---
name: wps365-getting-started
description: "WPS365 CLI onboarding entry point: install and verify wps365-cli, configure the API gateway for private deployments (api-base), bind an application in one step (config init) or create one via the developer console (provider bootstrap), authenticate with OAuth (auth setup/login, incl. --device headless login), verify with user me, and route to each business domain plus the api fallback. Use when a customer first onboards wps365-cli, needs to install/configure/authenticate from scratch, run their first command, switch between public cloud and private deployment, or is unsure which domain skill to use."
metadata:
  requires:
    bins: ["wps365-cli"]
---

# WPS365 CLI Getting Started

This skill is the **entry point** for onboarding wps365-cli: from install to running your first command, then routing to specific capabilities. For deep domain operations, switch to the matching domain skill (see "Capability map" below).

## Agent execution guide (read this first)

**Always probe state first, skip completed steps, avoid redundant operations:**

```bash
wps365-cli version              # no output -> install first (see Step 1)
wps365-cli update --check       # behind CDN latest -> then run wps365-cli update
wps365-cli config get api-base  # private + unset -> configure first (see Step 2); ignore on public cloud
wps365-cli auth status          # logged in -> use directly; not -> log in below
```

**After upgrading CLI or installing a new skills package (Agent required):** existing customers almost always still have stale `$(wps365-cli config path)/spec/` YAML. Replacing only the CLI binary is **not** enough — **refresh local specs before any business commands**.

```bash
# 1) Prefer: overwrite with this skills package's spec/ (matches bundled CLI/docs; CDN may lag)
SPEC_DIR="$(wps365-cli config path)/spec"
mkdir -p "$SPEC_DIR"
cp "<SKILLS_PKG>/spec/api.yaml" "<SKILLS_PKG>/spec/curated.yaml" "$SPEC_DIR/"
# <SKILLS_PKG> = extracted wps365-skills/ directory

# 2) If the package has no spec/, fall back to CDN
wps365-cli spec update -y

wps365-cli spec status
```

Typical symptoms: message send fails with `delegated is incompatible with operation security`, missing new commands, behavior differs from the skill docs — overwrite `spec/` first; do not keep flipping `--token-type`.

**First-time onboarding / re-init (public cloud, prefer `config init`):**

```bash
wps365-cli config init                 # browser create/bind app and auto-write credentials
# re-init or switch apps:
wps365-cli config init --new --force   # create a new app and overwrite local binding
# or: wps365-cli config init --force   # pick an existing app and overwrite

wps365-cli auth login --device --scopes "kso.user_base.read"   # device login, MUST pass required scopes
wps365-cli user me              # verify; success means onboarding is done
```

> **Agent must not say:** "CLI cannot create apps; the user must create one in the developer console and paste the secret." On public cloud, **`config init` / `config init --new`** creates or binds an app in the browser and writes credentials. Use `auth setup` only when AK/SK already exist. Missing `provider bootstrap` does **not** mean apps cannot be created (see Step 3).

> **Always log in with `--device`**: do not use `auth login` without `--device`, which runs the authorization-code flow, auto-opens the browser and listens on a local callback port. **`--device` MUST pass `--scopes`**: the device flow requests exactly the scopes you pass; **omitting scopes results in `granted []`** and later commands fail with `token missing required scopes`. `kso.user_base.read` is the minimum for `user me`; add domain scopes as needed (e.g. `kso.drive.readwrite,kso.file_search.readwrite`). Scopes can only request items the app has **enabled** in the developer console; a mistyped/not-enabled scope (e.g. `kso.user.readwrite`) triggers `invalid_scope`.

> **Device login must run to completion**: `auth login --device` claims the token by polling (not a browser callback). After starting it, show the link to the user and **keep the process alive** until it exits successfully; never check `auth status` once and kill it, otherwise the user's authorization has no one to claim it and the token never arrives.
>
> **QR:** `config init` and `auth login --device` both print an ASCII QR on stderr. To write an image: `wps365-cli auth qrcode --file qr.png "<verification URL>"`. Do **not** use global `-o/--output` as a file path (that flag is json|yaml|table); PNG path is `--file`. Path must be relative to the current directory (no `..`, no absolute paths).
>
> Private deployment / existing credentials / programmatic app creation: see the detailed steps below; troubleshooting is in the FAQ at the end.

---

## Step 1: Install and verify

Check whether it is already installed:

```bash
wps365-cli version
```

If you get "wps365-cli not found", install by platform:

```bash
# macOS / Linux / Windows (Git Bash)
curl -fsSL https://raw.githubusercontent.com/wps365-open/cli/main/install.sh | bash
```

```powershell
# Windows PowerShell
irm https://raw.githubusercontent.com/wps365-open/cli/main/install.ps1 | iex
```

> **Offline / intranet**: if this skill package ships a `bin/` directory (pre-bundled CLI archives for each platform), no download is needed — just extract the archive matching your machine:
> `aarch64-apple-darwin`=Apple Silicon Mac · `x86_64-apple-darwin`=Intel Mac · `*-unknown-linux-gnu`=Linux · `*-pc-windows-gnu`=Windows.
> Example: `tar -xzf bin/wps365-cli-*-aarch64-apple-darwin.tar.gz` (use the matching `.zip` on Windows), then move the extracted `wps365-cli` onto your `PATH` or call it by absolute path.

Still not found after install: the install dir is not on `PATH`. Add it to `~/.zshrc` (or `~/.bashrc`) and **restart the terminal/IDE**. If you cannot edit `PATH`, invoke via absolute path `/full/path/wps365-cli …`.

---

## Step 2: Confirm environment (public cloud / private)

- **Public cloud**: uses the official default endpoint, **no config needed**, go to Step 3.
- **Private deployment**: you **must** set the API gateway before any network call, otherwise requests hit the wrong host.

```bash
# Show the current API gateway
wps365-cli config get api-base

# Point to the private gateway (the key is api-base, NOT api-base-url)
wps365-cli config set api-base "https://<your-gateway-host>"
```

> You can also override temporarily with the `WPS365_API_BASE` environment variable (takes precedence over the config file), which is handy for CI or multi-environment switching:
> `export WPS365_API_BASE="https://<your-gateway-host>"`

On private deployments, if this CLI build has `provider bootstrap` (see Step 3 Option C), creating an app also needs the developer console URL. Never invent a host; always ask the user for the actual private endpoints. Without bootstrap: set `api-base`, then use **`config init`** (if supported on that deployment) or **`auth setup`** with existing credentials.

---

## Step 3: Bind an app + authenticate

WPS365 uses OAuth2. You first need an application (`client_id`/`client_secret`), then complete the user authorization login.

> **Default to Option A.** Only fall back to Option B when the user already has AK/SK, or `config init --help` is unavailable. Do **not** claim "CLI cannot create apps" just because `provider bootstrap` is missing.

### Option A: One-shot bind / re-init (recommended, public-cloud default)

Create or select an app in the browser and write credentials automatically (the CLI **can** create/bind apps):

```bash
wps365-cli config init                 # interactive: browser login -> select/create app -> write client_id/secret
wps365-cli config init --new           # create a new app directly
wps365-cli config init --app-id "<APP_ID>"   # bind an existing app
wps365-cli config init --new --force   # re-init: create new app and overwrite local binding
wps365-cli config init --force         # re-init: overwrite binding (pick an existing app)
```

Trust `wps365-cli config init --help` on this machine (expect `--new` / `--force` / `--app-id`).

### Option B: Existing credentials, configure manually

Use only when the user **already** has `client_id`/`client_secret` (or must skip browser bind) — **not** as the only path when "CLI cannot create apps":

```bash
wps365-cli auth setup           # interactive guided credential entry
# or non-interactive:
wps365-cli auth setup --client-id "AK..." --client-secret "sk-..." \
  --redirect-uri "http://localhost:18365/callback"
```

### Option C: `provider bootstrap` (optional; some builds only)

Probe first: `wps365-cli provider bootstrap --help`. If unknown command, **this CLI has no bootstrap** — use Option A / B; do **not** infer that apps cannot be created.

When `--help` works, you can create an app via console `wps_sid` (cookie) or login (incl. some private deployments):

```bash
wps365-cli provider bootstrap --dry-run --scenario drive,aidocs
wps365-cli provider bootstrap --scenario drive,aidocs \
  --api-base-url "https://<your-gateway-host>" \
  --console-base-url "https://<your-console-host>" \
  --devconsole-sid "<wps_sid value>"
wps365-cli provider bootstrap --scenario drive --console-login
```

> `--scenario` (`-b`) decides which scopes to request per scenario; `--devconsole-sid` can also be provided via the `WPS365_DEVCONSOLE_SID` environment variable.

### Complete the login authorization

Once credentials are ready, authorize the user. **Both the device code flow (`--device`) and the browser authorization-code flow MUST pass `--scopes` with the required permissions** — the device flow requests exactly the scopes you pass, so **omitting them results in `granted []`** and later commands fail with `token missing required scopes`:

```bash
# Device code flow (works headless or with a browser): pass the required scopes
wps365-cli auth login --device --scopes "kso.user_base.read,kso.drive.readwrite"
```

> **Device login must run to completion** (key points in the "Agent execution guide" at the top): the process polls to claim the token and must stay alive until it exits successfully; never terminate it early. If killed or `device_code` expires (`device code expired`), re-run it. Detailed troubleshooting is in the FAQ at the end.

> **Always log in with `--device`.** Do not use `auth login` without `--device` — it runs the **authorization-code flow**: it auto-opens the browser, builds a `response_type=code` link and listens on a local callback port (e.g. `localhost:18365/callback`), which easily fails or produces unexpected browser popups in agent/headless/port-restricted scenarios.
>
> Only when the device flow is truly unavailable, fall back to the authorization-code flow:
>
> ```bash
> wps365-cli auth login --scopes "kso.user_base.read,kso.calendar.read"
> ```

`--scopes` can only request items the app has **enabled** in the developer console; take exact scope names from each domain skill and the console config. `auth login` scopes are **cumulative** (union with existing grants); logging in again to add scopes is safe and never clears prior grants. On `invalid_scope: The requested scope '...' is not allowed`: that one scope is mistyped or not enabled — **remove/correct that single scope**, or enable it for the app in the developer console first, then request it. **Do not drop all scopes** (an empty set yields `granted []`).

---

## Step 4: Verify

```bash
wps365-cli auth status     # show identity, scopes, expiry
wps365-cli user me         # fetch current user; success means onboarding is complete
```

---

## Authentication essentials

| Identity mode | Flag | Use case | How to obtain |
|---------------|------|----------|---------------|
| delegated (user-authorized) | `--token-type delegated` | User-scoped APIs (my calendar/files, etc.) | `auth login --device --scopes "..."` |
| app (application identity) | `--token-type app` | Server-side / app-scoped APIs | Run the command directly, add `--token-type app` if needed |

Commands pick the identity automatically from the underlying OpenAPI `security`; `--token-type` overrides explicitly. When delegated is unavailable it falls back to app.

Common auth commands:

```bash
wps365-cli auth token            # print current access token (--app for app identity token)
wps365-cli auth refresh --delegated   # manual refresh (or --app)
wps365-cli auth logout           # log out (keeps credentials, can re-login directly)
wps365-cli auth clean --force    # full reset: clear all tokens/credentials/auto keys
```

**Handling 403 / missing scope (by identity):**

- **delegated**: after `auth status`, run `auth login --device --scopes "missing-scope"` to grant (scopes are cumulative), have the user complete authorization via the device link in the browser, then retry.
- **app**: permissions are bound to the app config in the developer console; an **admin must enable them in the console**, the CLI cannot bypass this.
- **Enterprise package privileges (`403000001` / `ErrPrivileges: interface_*`)**: not an OAuth scope issue. Ask the user to have their **enterprise admin** enable **Business Advanced (商业高级版)** or **Business Flagship (商业旗舰版)**. See `../wps365-shared/SKILL.md`. Example: `interface_company_doc` = cloud-docs open capability, requires Business Advanced or higher.

**Inject credentials in CI / headless (env vars):**

```bash
export WPS365_CLIENT_ID="<client-id>"
export WPS365_CLIENT_SECRET="<client-secret>"
# or inject an access token directly, skipping local storage and refresh:
export WPS365_ACCESS_TOKEN="<token>"
```

---

## Dual-track command model

**Curated commands** (preferred, semantic flags):

```bash
wps365-cli calendar event list primary
wps365-cli im messages send --to "u1" --to "u2" --text "hello"
```

**api fallback** (for endpoints not covered by curated commands, full API):

```bash
wps365-cli api get "/v7/users/current"
wps365-cli api post "/v7/messages/batch_create" --data '{ ... }'
```

`api` supports `get|post|put|patch|delete|head`; the path is a relative API path.

**Self-inspection help** (first choice when unsure of syntax):

```bash
wps365-cli --help                 # top-level domain list
wps365-cli <domain> --help        # subcommands of a domain
wps365-cli <domain> <cmd> --help  # flag details
```

---

## Capability map & domain skill routing

| Domain | Top-level command | Read for deep usage |
|--------|-------------------|---------------------|
| Basics/auth/env | `auth` `config` `spec` `provider` | `../wps365-shared/SKILL.md` |
| Cloud docs / team libraries | `drive` (includes `drive doclib`) | `../wps365-drive/SKILL.md` |
| Smart documents | `airpage` | `../wps365-airpage/SKILL.md` |
| Smart sheets | `airsheet` | `../wps365-airsheet/SKILL.md` |
| Instant messaging | `im` | `../wps365-im/SKILL.md` |
| Calendar/meeting | `calendar` `meeting` | `../wps365-calendar/SKILL.md` · `../wps365-calendar-insert/SKILL.md` · `../wps365-meeting/SKILL.md` |
| Mail | `mail` | `../wps365-mail-core/SKILL.md` |
| Multi-dimensional sheets | `dbsheet` | `../wps365-dbsheet-records/SKILL.md` · `../wps365-dbsheet-schema/SKILL.md` |
| Contacts/user | `user` | `../wps365-contacts/SKILL.md` · `../wps365-user/SKILL.md` |
| WorkBuddy / MCP | `mcp` | `../wps365-mcp/SKILL.md` (enterprise WPS 365; do not mix with the personal kdocs connector) |

Each domain skill lists that domain's scopes and command examples; take specific scopes from the domain skill and `--help`.

---

## Output, preview & troubleshooting

```bash
-o json|yaml|table|tsv|ndjson|csv   # output format (global -o/--output)
--dry-run                            # print the request without sending; preview first
--jq '<filter>'                      # built-in jq filtering
--quiet                              # only output data and errors
```

**Exit codes:** `0` success · `1` API error · `2` auth · `3` args · `4` spec · `5` internal error.

**Spec management:** definitions live under `$(wps365-cli config path)/spec/`. **After an existing customer upgrades the CLI or installs a new skills package, the Agent must refresh that directory first**, then run business commands:

```bash
# Prefer: overwrite with skills package spec/
cp "<SKILLS_PKG>/spec/api.yaml" "<SKILLS_PKG>/spec/curated.yaml" "$(wps365-cli config path)/spec/"
# If the package has no spec/:
wps365-cli spec update -y
wps365-cli spec status
```

---

## FAQ

**Q: I just upgraded the CLI / skills package, but new commands are missing, message send only allows app, or behavior doesn't match the docs?**

Local `spec/api.yaml` (and `curated.yaml`) are still old. The Agent should **prefer overwriting** `$(wps365-cli config path)/spec/` with the skills package's `spec/` files; if the package has none, run `wps365-cli spec update -y`. Then check with `wps365-cli spec status` and retry. Upgrading only the binary without refreshing specs will not fix security or new commands.

**Q: On re-init / switching apps, the Agent says "CLI cannot create apps; create one in the console first"?**

That is wrong. On public cloud use **`wps365-cli config init --new --force`** (or `config init --force`) to create/bind in the browser and overwrite local credentials, then `auth login --device --scopes "..."`. Use `auth setup` only when AK/SK already exist. If `provider bootstrap` is missing, fall back to `config init` — do not ask the user to paste secrets first.

**Q: config init keeps showing "Waiting for binding"?**

Make sure every step on the browser side is completed, especially the final authorization confirmation. If you only create/bind the app without authorizing, the CLI stays pending until the session expires.

**Q: What is the difference between config init and auth setup?**

| Aspect | config init | auth setup |
|--------|-------------|------------|
| Use case | First-time use, quick start | Existing credentials, manual management |
| How it works | Browser-guided, auto-fetches AK/SK | Interactive input or environment variable injection |
| Storage location | Same (config.json + secure storage) | Same |

**Q: I completed authorization in the browser for `auth login --device`, why is the token never obtained?**

The device flow is not a browser callback; the token can only be claimed by the **still-running login process polling** the server (about every 5 seconds), which exits successfully once it claims it. If that `auth login --device` process was terminated or the `device_code` expired (`device code expired`), the approval granted in the browser has no one to claim it and the token will never arrive locally. Fix: confirm no `auth login` process is alive (`ps aux | grep "auth login"`), then **re-run** `wps365-cli auth login --device`, complete the "authorize" step in the browser with the new link, and **keep the process running until it exits on its own**, then verify with `wps365-cli auth status`. Agents must treat this command as a task that runs to completion and never kill it prematurely.

**Q: A command fails with token missing required scopes: need one of [...], granted []?**

You logged in without (or with empty) `--scopes`, so no permissions were granted. The device flow requests exactly the scopes you pass, so you must pass them explicitly; e.g. `user me` needs at least `kso.user_base.read`:

```bash
wps365-cli auth login --device --scopes "kso.user_base.read,kso.drive.readwrite,kso.file_search.readwrite"
```

Scopes are cumulative, so you can log in again to add missing ones. Retry the original command after granting.

**Q: Login fails with invalid_scope: The requested scope '...' is not allowed?**

One specific scope is mistyped or not enabled for the app in the developer console (e.g. `kso.user_base.read` written wrongly as `kso.user.readwrite`). Fix: **remove/correct that single scope** in `--scopes`, or enable it for the app in the developer console first, then request it. **Do not drop all scopes** — an empty set yields `granted []` and later commands fail for missing scopes.

**Q: Why didn't my permission request take effect?**

After requesting a permission you must complete the full flow "create version → request release → enterprise admin approval" for it to take effect. If you only request the permission without submitting the version for review, the permission stays in "pending submission" status.

**Q: A call returns `403000001` / `ErrPrivileges: interface_company_doc` (or other `interface_*` / `saas_*`)?**

This is a missing **enterprise package privilege**, not a login scope gap. The privilege gateway checks business capability points (e.g. `interface_company_doc` = cloud-docs open APIs, needs **Business Advanced or higher**). The Agent should tell the user to ask their **enterprise admin** to enable **Business Advanced (商业高级版)** or **Business Flagship (商业旗舰版)** — do not keep retrying `auth login`. Other known privilege codes: see `../wps365-shared/SKILL.md`.

**Q: Contacts API returns empty data or a permission error?**

Some APIs (especially contacts-related endpoints) require, in addition to the "capability permission", a configured "available scope" and "data permission". Check them under Permission Management on the app detail page.

**Q: What if CLIENT_SECRET is leaked?**

Immediately click "Reset" in the "App Credentials" section of the developer console to generate a new secret; the old one is invalidated instantly. Then re-run `wps365-cli config init` or `wps365-cli auth setup` to configure the new credentials.

---

## Safety rules

- Never print `client_secret` / `access_token` / `refresh_token` in plain text.
- Before `create` / `update` / `delete` and bulk write operations, confirm intent with the user; preview with `--dry-run` when unsure.
- Report the count and scope of affected items before bulk writes/deletes.
- In private deployments, never invent a host; use the actual gateway/console endpoints provided by the user.
- **Do not dump the entire company directory**: never run `wps365-cli dept list <root_id>`, `wps365-cli dept member list <root_id> --recursive --all`, or recursively call `api get /v7/depts/.../children` / `.../members` to export all departments and people. To find someone use `user search`; to get a user's departments use `user dept list <USER_ID>`.
