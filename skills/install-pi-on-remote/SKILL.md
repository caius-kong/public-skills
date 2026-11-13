---
name: install-pi-on-remote
description: "Deploy a remote macOS Mac as an agents server: configure dedicated passwordless SSH over LAN or Tailscale, run the repository bootstrap.sh to install Pi, install Herdr with its Pi integration and its agent skill, and verify both direct-SSH Pi and Herdr-managed remote Pi instances. Use whenever the user asks to install/reinstall Pi or Herdr on another Mac, set up remote SSH agents, or deploy an agents server. macOS only."
---

# install-pi-on-remote

Use this playbook only for macOS Macs, local or remote. Tailscale provides network reachability; macOS Remote Login provides the SSH service. The repository's `~/.pi/bootstrap.sh` owns Pi packages, provider configuration, and API-key setup; Herdr's official installer and CLI own Herdr and its Pi integration.

## Preflight

- `herdr`: `~/.agents/skills/herdr/SKILL.md`
  - If missing: `npx -y skills add herdrdev/herdr --skill herdr -g -y`（`-y` 必需，否则 CLI 会等确认并把非交互 SSH 运行卡住；已存在时跳过安装、只校验，见 §7）
  - 用途：Herdr 的 Pi 集成与它自己的 agent skill 都由它提供；本 skill 不复制。

## Intake: ask once, then run unattended

Ask everything below in **one** message, as a table with defaults pre-filled so the user can answer in one line. After the answer, echo it back as one block and run the whole job without further questions; the only later interruption is a stop condition in the procedure.

| Ask | Answer shape | Notes |
|---|---|---|
| target | `local` / `remote: <alias>` | ask host/user only when no alias matches |
| provider + credential source | `trendmicro` (already on target) / `deepseek,zai` default `zai` + keys-file path | omit = repository defaults, no credential written. Never ask for or accept a key value |
| hindsight | `none` / `https://<url>` + token source | token = already on target, or a mode-`600` file path the user places. A new server is out of scope (`docs/hindsight-pi-deployment.md`) |
| herdr | `off` (default) / `on` | `on` = install Herdr, its Pi integration and its agent skill (reuse an existing install, do not update it) and run its managed acceptance |
| skills | `off` (default) / `<owner>/<repo>,…` | recommended: `caius-kong/skills`, `mattpocock/skills`, `anthropics/skills`, `mvanhorn/last30days-skill` (URLs and install rules in 7b). Clone from HTTPS, follow each repo's own README; a repo that cannot be installed is reported as skipped, never fatal. Herdr's own `herdr` skill is not listed here; §8 installs it with Herdr |
| existing pi | `keep` (default) / `reinstall` / `uninstall+bootstrap` | ask only when the target already has Pi; the only destructive branch |

Do not ask for anything you can discover yourself. Resolve these before or while asking: SSH reachability (`ssh -o BatchMode=yes -o ConnectTimeout=5 <alias> true`), macOS version/architecture, installed Pi version and install method, `~/.pi` origin and dirty state, providers present in `auth.json`, Herdr presence and integration status, existing skill clones under `~/dev/<owner>/<repo>`, free disk.

## Modes and fast path

| Target | herdr | Sections to run |
|---|---|---|
| local | `off` | 5 → 7 → 9 |
| local | `on` | 5 → 7 → 8 → 9 |
| remote, SSH already works | `off` | 5 → 7 → 9 (skip 2–4) |
| remote, SSH needs setup | `off` | 2 → 3 → 4 → 5 → 7 → 9 |
| remote | `on` | all sections |

If the reachability check succeeds and the host key is already trusted, skip §2–§4 instead of re-deriving keys. In local mode every `ssh <alias> '...'` step becomes a direct command and §2–§4 are skipped. A non-`off` `skills` answer only appends step 7b; it never changes which of the other sections run.

## Procedure

1. **Resolve scope and target.** Read-only and plan-only requests make no changes. Herdr-only setup skips Pi uninstall/bootstrap and preserves Pi provider/auth state. Herdr is installed only when intake says `herdr = on`; a plain "install Pi" request never touches Herdr. If Pi already exists during a normal install request, report its state and ask before bootstrap or other Pi changes; only an explicit clean-reinstall request authorizes uninstall (already settled at intake). Resolve a supplied machine name against existing SSH aliases before asking for another address or username; request identity details only if the alias is missing or ambiguous. LAN addresses (RFC1918) require both Macs on the same network. For Tailscale, both Macs normally need the official macOS app installed, signed into the same permitted tailnet, and online. Tailscale provides network reachability; macOS Remote Login separately provides SSH. If either Mac is not ready, wait before attempting SSH. If a company/MDM Mac's app reports “System Extension setup failed” or “System Extension Blocked,” do not bypass policy. First confirm company approval for the CLI approach and the user's admin rights. If approved, check whether the Homebrew Tailscale CLI is already installed; if not, run `brew install tailscale`. Start its background service with `sudo brew services start tailscale`, sign in interactively with `tailscale up`, and verify `tailscale status` shows the device online. Never expose login credentials or sudo passwords. Without approval or admin rights, stop and ask IT or use LAN. Never probe a template/placeholder target; ask the user for the actual target before execution. If SSH is unreachable, state installation status is unknown and stop without changes.

2. **Prepare SSH access on the destination Mac.** If Remote Login is off, guide the user on that Mac: current macOS uses Apple menu → System Settings → General → Sharing → Remote Login; older macOS uses System Preferences → Sharing → Remote Login. Turn it on, choose “Only these users,” and add only the intended account. Ask the user to note the SSH command or account name shown there; confirm the target hostname/IP separately. Leave “Allow full disk access for remote users” off unless the task specifically requires it and the user approves.

   If the macOS firewall blocks the connection, do not disable the firewall. On current macOS, inspect System Settings → Network → Firewall → Options; on older macOS, inspect System Preferences → Security & Privacy → Firewall. Allow the Remote Login/SSH service (often shown as `sshd` or `sshd-auth`) only if it is blocked and policy permits. Labels vary; do not add unrelated services. If settings are managed or the SSH rule is unclear, ask the user or IT rather than changing policy. Do not change sleep/power settings as part of SSH setup; if always-on availability is requested, discuss sleep and power impact separately and get approval before changing it.

   Tailscale does not enable SSH. If Tailscale SSH is enabled instead of ordinary OpenSSH, stop and clarify the authentication policy; this playbook uses OpenSSH public-key authentication.

3. **Verify first contact and confirm the host.** On first connection, verify the SSH host-key fingerprint via a trusted channel before accepting it; never disable host-key checking. To confirm reachability and macOS, use an authorized one-time password login if needed:

   ```sh
   ssh -o ConnectTimeout=10 <user>@<target> 'echo OK; uname -s; sw_vers -productVersion'
   ```

   `BatchMode=yes` deliberately refuses password prompts, so use it only after a key has been installed. If password login is disabled or fails, do not weaken sshd settings; request an authorized key-provisioning route such as local access or an already-authorized account. Stop if Remote Login is off or the OS is not macOS.

4. **Configure and verify per-machine passwordless SSH.** Use one dedicated Ed25519 key per Mac, never a GitHub/git key or another machine's key. Test a matching existing key first. For a new key, let `ssh-keygen` prompt for a passphrase; for unattended use, keep the encrypted key available through the user's SSH agent/Keychain. Never expose or store the passphrase in scripts.

   Ensure local `~/.ssh` is owned by the user and mode `700`; create it if absent and correct its permissions if needed. Confirm the chosen key path does not already contain a key; if it does, verify that it is the intended dedicated key or choose a new path. Never overwrite an existing key. Then create a new key locally:

   ```sh
   install -d -m 700 ~/.ssh
   ssh-keygen -t ed25519 -f ~/.ssh/id_<alias> -C "ssh:<alias>"
   ```

   After key creation, confirm the private key is mode `600` and the public key is `644` or more restrictive. After the user has authorized initial access and the host key is verified, back up remote `~/.ssh/authorized_keys` if present to a unique file in `~/.ssh`, verify the backup, and keep it mode `600`. For example:

   ```sh
   ssh <user>@<target> 'if [ -f ~/.ssh/authorized_keys ]; then umask 077; backup=$(mktemp "$HOME/.ssh/authorized_keys.backup.XXXXXX") && cp -p ~/.ssh/authorized_keys "$backup" && chmod 600 "$backup" && cmp -s ~/.ssh/authorized_keys "$backup" && printf "Verified backup: %s\n" "$backup"; else echo "No existing authorized_keys file"; fi'
   ```

   If the backup command fails, stop before changing `authorized_keys`. Use `ssh-copy-id -i ~/.ssh/id_<alias>.pub <user>@<target>` only if `ssh-copy-id` is installed and the user approves; it is not included with every macOS client. Otherwise append the public key without overwriting existing entries and avoid duplicates:

   ```sh
   ssh <user>@<target> 'umask 077; mkdir -p ~/.ssh; touch ~/.ssh/authorized_keys; chmod 700 ~/.ssh; chmod 600 ~/.ssh/authorized_keys; while IFS= read -r key; do [ -z "$key" ] || grep -qxF "$key" ~/.ssh/authorized_keys || printf "%s\n" "$key" >> ~/.ssh/authorized_keys; done' < ~/.ssh/id_<alias>.pub
   ```

   This fallback sends only the public key; confirm it targets the intended account and host. If password login is disabled or unavailable and no authorized key-provisioning route exists, stop and ask the user to use local access or another authorized method; do not weaken SSH server authentication. Verify the dedicated key alone before relying on it:

   ```sh
   ssh -o BatchMode=yes -o IdentitiesOnly=yes -i ~/.ssh/id_<alias> <user>@<target> 'echo OK; hostname; sw_vers -productVersion'
   ```

   Add a local SSH alias without disturbing existing config. Back up `~/.ssh/config`, preserve `Include` directives and other host blocks, put specific blocks above `Host *`, and confirm the proposed block before writing:

   ```sshconfig
   Host <alias>
     HostName <LAN-IP-or-Tailscale-IP-or-MagicDNS-name>
     User <user>
     IdentityFile ~/.ssh/id_<alias>
     IdentitiesOnly yes
     AddKeysToAgent yes
     UseKeychain yes
   ```

   Verify the alias itself with `ssh -o BatchMode=yes <alias> 'echo OK; hostname'`. If any prerequisite or command result differs from the expected flow, stop and report the exact blocker instead of guessing.

5. **Inspect state before changing Pi or Herdr.** Record the host, macOS version/architecture, login shell, current Pi/Herdr versions and install methods, `~/.pi` origin/status, provider/model names from settings, and whether auth/config/integration files exist. Never read or print credential values. For read-only diagnosis, compare non-interactive and interactive shell behavior, inspect the login shell's startup files for both modes, and stop without mutation.

   Confirm remote `git` and `curl` work. The canonical bootstrap repository for this playbook is `git@github.com:caius-kong/.pi.git`; use it unless the user specifies another authorized clone URL. If the repository is private, ensure the destination Mac itself can read it (for example, with a repository-scoped read-only deploy key installed on that Mac). This GitHub repository credential is separate from the key used by the initiating Mac to log into the destination. Keep `PI_REPO_URL` credential-free; never embed passwords/tokens in its URL or expose credentials in logs. Preserve repo changes and stop on bootstrap conflicts; do not reset user state without explicit approval.

6. **For an explicitly requested clean Pi reinstall, back up before uninstalling.** Record the Pi version/install method. For a managed install, inspect the marker, resolved launcher/runtime root, and official uninstaller behavior; proceed only if the root is strictly inside `~/.pi/agent/install/` and the complete deletion set is limited to that runtime and Pi launcher. Choose only the installer's **Uninstall Pi** action after verifying this scope. If the full target set is uncertain, stop before uninstalling. For legacy npm installs, confirm ownership with `npm ls -g --prefix <existing-prefix> --depth=0 @earendil-works/pi-coding-agent`, verify the matching prefix, and remove only that package; if the package target/effects are unclear, stop.

   Check available disk space first. Before uninstalling, create a unique mode-`700` backup directory outside `~/.pi` and every removal root. Copy the full `~/.pi` tree excluding only the verified Pi runtime root and launcher, preserving ownership, modes, extended attributes, and symlinks; create separate mode-`600` copies of `settings.json` and `auth.json` when present. Record absent files, source/backup hashes, and symlink targets. Identify symlinks whose resolved referents are inside a removal root; preserve those referents independently or stop. Require hash matches, expected ownership, restrictive backup modes, and the backup location outside `~/.pi` before uninstall. Record a baseline inventory of every preserved path, type, symlink target, owner, permission, and regular-file hash. After uninstall, require that Pi is absent and compare the entire preserved tree and critical files with preflight. If Pi remains installed, the removal effects differ from the verified target, or any preserved state mismatches, stop before bootstrap. Inspect differences and restore only preflight paths confirmed missing or damaged; if the destination contains new or ambiguous data, preserve it and stop rather than overwrite. After restoration, repeat the complete integrity/inventory checks. Bootstrap may follow only after uninstall and preservation checks pass and remains within the original authorization.
7. **Run bootstrap non-interactively when Pi setup is requested.** On a fresh host, clone the canonical `git@github.com:caius-kong/.pi.git` repository (or the user's explicitly authorized alternative) into a new empty temporary directory; if that path exists, choose another without deleting it. Invoke its `bootstrap.sh` (over SSH for a remote target, directly in local mode) with `PI_REPO_URL` set to the same credential-free URL. For an existing `~/.pi` clone, verify its origin is the canonical repository or the user's explicitly authorized alternative before using `~/.pi/bootstrap.sh`; if it is unrelated, stop rather than repointing or replacing it. Use the destination's actual shell and SSH startup path; use `zsh -ic` only when the target uses zsh and it is needed to locate Node/Pi.

   The authoritative flag list is the parameter table in the repository README; do not restate it. Compose one command from the intake — providers (or none), keys file (or none), Hindsight URL and token file (or none):

   ```sh
   # remote
   ssh <alias> 'PI_REPO_URL=<verified-credential-free-repo-url> ~/.pi/bootstrap.sh \
     [--default-provider <p>] [--keys-file <destination-keys-file>] \
     [--hindsight-api-url <url>] [--hindsight-token-file <destination-token-file>]'

   # local
   PI_REPO_URL=<verified-credential-free-repo-url> ~/.pi/bootstrap.sh <same flags>
   ```

   Land credentials without exposing them: write the keys file and the Hindsight token on the destination yourself (`ssh <alias> 'umask 077; cat > ~/.pi-bootstrap-keys' < <local-mode-600-file>`, same for the token), pass only the paths, and delete both files after bootstrap. Never put a key or token in arguments, never echo file contents, and never accept a secret in chat.

   With no provider flag, bootstrap keeps the repository defaults and writes no credential; that is a valid finished state — report it as such instead of inventing a provider. With providers, a missing default-provider credential must fail before any settings change, and optional providers may be skipped (record which).

   A fresh host still needs the temporary clone of the canonical repository described in step 1; run that clone's `bootstrap.sh` with the same flags and the credential-free `PI_REPO_URL`.

   When the request also asks for Hindsight memory, add `--hindsight-api-url <https-url>`. That flag is the only Hindsight opt-in — there is no prompt and no `--memory` switch — and it implies the official coding-agent installer runs, `~/.hindsight/coding-agent.json` is written (`0600`, parent `0700`) and the extension is registered in `agent/settings.json`. Supply the tenant token with `--hindsight-token-file <mode-600 file>` or `HINDSIGHT_API_TOKEN`; take it from the initiating Mac's existing `~/.hindsight/coding-agent.json` only when that file already targets the same endpoint, otherwise ask the operator who provisioned the server. Never put the token in argv, never print it, and delete any temporary token file from the destination Mac afterwards. The URL must be HTTPS, or loopback HTTP when the destination is the Hindsight server itself. Bootstrap installs and configures a client only; server deployment and old-data migration belong to `docs/hindsight-pi-deployment.md`.

   Preserve existing `~/.pi/agent/auth.json` and its permissions; never overwrite existing provider entries. Record which requested providers were configured and which were skipped. If bootstrap stops on a dirty `agent/settings.json`, back it up and inspect before resolving; never discard user settings blindly. Before bootstrap, record per-provider hashes for existing auth entries without displaying their contents. After bootstrap, compare the preserved `~/.pi` state with the preflight inventory again; allow only documented changes to default provider/model/subagent settings, package-install state, the newly installed Pi runtime, and auth entries for requested/configured providers. If auth.json existed, verify all prior entries are unchanged and permissions remain restrictive; if absent, allow its creation only for configured providers with mode `600`. Unexpected changes to unrelated auth entries, settings, extensions, sessions, or files require stopping and investigation before Herdr installation or acceptance tests.

7b. **Install the requested skill repositories (only when intake lists them; skip entirely for `off`).** Skills are not part of this checkout: `agent/skills/` may hold symlinks into a separate skills repo (some relative, e.g. `../../.agents/skills/<name>`, some absolute), and on a fresh host they dangle until that repo is installed there. Leave them alone; the relative ones start resolving once the matching name appears in `~/.agents/skills/`.

   Recommended repositories:

   - `https://github.com/caius-kong/skills.git`
   - `https://github.com/mattpocock/skills.git`
   - `https://github.com/anthropics/skills.git`
   - `https://github.com/mvanhorn/last30days-skill.git`

   For each repo from intake: clone or refresh it over HTTPS (`GIT_TERMINAL_PROMPT=0`, public — the destination needs no GitHub credential) into `~/dev/<owner>/<repo>`, then **read that repo's `README.md` and follow its documented install instructions.** This playbook deliberately carries no per-repo procedure: these repos install through different surfaces (agent plugin installs, marketplaces, `npx skills`, plugin managers, manual copies) and they change over time, so the README is the source of truth and the agent adapts to it. When a README documents only other harnesses, use the harness-agnostic path Pi understands: a directory containing `SKILL.md` works when symlinked into `~/.agents/skills/<name>` (absolute source path, `mkdir -p` the destination first).

   Regardless of what a README says, hold these lines: never pass a force flag, never delete or replace an existing skill directory or a symlink owned by another repo (skip the name and report the collision — the user owns which repo wins), write nothing outside the agent skill dirs and `~/dev`, and never use a credential, a token, or another machine's key. A repo that will not clone, or whose README gives no workable path for this harness, is reported as **skipped: <reason>** and the run continues — an optional skill repo is never fatal.

8. **On the destination Mac, install Herdr and its Pi integration only when intake says `herdr = on` or the user separately asked for Herdr.** Skip this section entirely for a plain Pi install. Run these commands on the remote host over SSH (locally, without the `ssh` wrapper). Reuse a package manager already managing Herdr; otherwise use the official stable macOS installer:

   ```sh
   set -o pipefail
   curl -fsSL https://herdr.dev/install.sh | sh
   ```

   Treat either pipeline failure or a subsequent missing/unusable `herdr --version` as an installer failure and diagnose the exact cause before fallback. For a recoverable installer failure, consult Herdr's official install guide at `https://herdr.dev/docs/install/` and latest manifest at `https://herdr.dev/latest.json`; confirm current manifest fields, select the asset for the target architecture, verify its published SHA-256 with `shasum -a 256`, and install the verified binary as `~/.local/bin/herdr`. Use only a checksum published by Herdr's current official instructions or manifest; stop the fallback if none is available. If docs/schema differ, follow current official instructions rather than guessing. Never disable TLS checks or accept a checksum mismatch.

   Herdr documents the Pi integration file at `~/.pi/agent/extensions/herdr-agent-state.ts`; `herdr integration status` is authoritative and the file is corroborating evidence. See `https://herdr.dev/docs/integrations/`. Preserve existing Herdr configuration and do not update an existing installation unless requested. If `herdr` is missing from non-interactive PATH, first check whether the installed executable exists at the package manager or official install location. If it exists, inspect the actual login-shell startup files, edit only the applicable file while preserving content/system PATH priority, then verify `herdr --version` before any integration command. If no executable exists, treat installation as failed and diagnose/retry installation; do not edit shell startup files.

   Check status before modifying integration state:

   ```sh
   herdr --version
   herdr integration status
   ```

   If `herdr integration status` reports the Pi integration as current, skip installation only if the documented integration file is also present. If status reports it not installed and the file is absent, install it and verify status afterward. Stop and report the integration incomplete if status fails, returns an unrecognized state, or disagrees with file presence/ownership:

   ```sh
   herdr integration install pi
   herdr integration status
   test -s ~/.pi/agent/extensions/herdr-agent-state.ts
   ```

   If the file exists but status does not show it as Herdr-managed/current, preserve a backup and stop rather than overwrite ambiguous user-owned content. An outdated integration is an update; ask before replacing it unless the user explicitly requested an update. If post-install status or the documented file check fails, report the integration as incomplete and stop; do not treat Pi runtime installation as Herdr integration success.

   Then install Herdr's own agent skill, which teaches the harness how to drive Herdr (CLI discovery, pane and agent lifecycle, handoff, remote machine forwarding). Pi discovers `~/.agents/skills/`, which is where the `skills` CLI puts a global install, so no Pi-specific link is needed:

   ```sh
   test -e ~/.agents/skills/herdr || npx -y skills add herdrdev/herdr --skill herdr -g -y
   test -s ~/.agents/skills/herdr/SKILL.md
   ```

   `-y` is required: without it the CLI prompts for confirmation and agent targets and stalls a non-interactive SSH run. Per-agent failures such as “Eve does not support global skill installation” are not fatal; only a missing or unreadable `SKILL.md` at the canonical path is. If `~/.agents/skills/herdr` already exists, skip the install and verify it instead — the command replaces the copy, so re-running counts as an update and needs an explicit request. Never add a force flag and never delete another skill directory to make room.

9. **Verify requested installation and runtime paths.** For Pi setup, first identify and repair only the destination shell's applicable startup file if `pi` is missing from non-interactive PATH; verify `pi --version` before auth/readiness and smoke tests. Run `pi auth check` only for providers bootstrap confirmed as configured. It reports local credential readiness, not live network/model health; a real `pi -p` call tests only the selected default provider.

   From the initiating Mac, open a remote interactive Pi instance through SSH with a TTY (local mode: run `pi` directly):

   ```sh
   ssh -tt <alias> 'pi'
   ```

   In that remote Pi TUI, submit a harmless prompt and verify the completed response in the terminal before exiting Pi normally. The response must be distinguishable from the echoed prompt; for automation, ask for a fixed result that does not appear verbatim in the prompt. Require the remote Pi process to exit and the SSH session to return successfully. This is the direct SSH-launched Pi acceptance path and is separate from the Herdr-managed path.

   When Hindsight was requested, verify that path separately from provider connectivity: `~/.hindsight/coding-agent.json` must name the requested endpoint with a token present and mode `0600`, an authenticated `GET /v1/default/banks` from the destination must succeed with that token, and a `pi -p` run that asks Pi to call `hindsight_diagnose` must report the same endpoint with `api_token_matches_config=true`. Never print the token value.

   For a full Pi+Herdr/agents-server setup, or when the user explicitly requests Herdr-managed runtime acceptance, use the initiating Mac's Herdr CLI for the remote Pi path. Otherwise skip this check and report it as not run. The initiating Mac must have a compatible Herdr CLI, and Pi and its Herdr integration must already be available on the remote host. If the remote machine is not already saved, inspect all remote Herdr sessions and their active workspaces/panes first (for example, `ssh <alias> 'herdr session list --json'`, followed by `herdr --session <name> workspace list` and `herdr --session <name> pane list` for each listed session). Add it in an interactive terminal with `herdr machine add <alias> --label <unique-label> --remote-session default`. This prepares the remote Herdr server and saves a local machine profile. `machine add` may ask to stop a running remote server, which stops its pane processes; do not approve that prompt unless the user explicitly authorizes the interruption after reviewing affected work. If not authorized, stop and report the Herdr-managed runtime check as blocked rather than stopping remote processes. Use an existing remote project directory whose absolute path is confirmed; if none is known, ask the user rather than guessing. Create a dedicated test workspace on the remote host through that profile, capture the returned root pane ID, then start and prompt a Pi agent:

   ```sh
   herdr --machine <label> workspace create --cwd <remote-project-path> --label agent-smoke --no-focus
   herdr --machine <label> agent start remote-pi --kind pi --pane <root-pane-id>
   herdr --machine <label> agent prompt remote-pi "Reply exactly: HERDR_PI_REMOTE_OK. Do not use tools." --wait --until idle --until done --timeout 120000
   herdr --machine <label> agent read remote-pi --source recent-unwrapped --lines 40
   ```

   Use the actual root pane ID from the workspace-create JSON response; do not guess IDs. Accept only when the local Herdr CLI reports a successful start, the remote Pi's visible response contains `HERDR_PI_REMOTE_OK`, and the agent settles to `idle` or `done`. If the prompt times out or stalls, inspect the agent before retrying; do not send a duplicate prompt blindly. Report direct SSH Pi and Herdr-managed remote Pi results independently. Do not close unrelated remote sessions or workspaces.

   When Herdr was installed, its `herdr` skill belongs in the same discovery check. That proves loading only: the skill itself refuses to act unless `HERDR_ENV=1`, so a Pi instance outside a Herdr pane will correctly decline to drive Herdr sessions.

   When skill repositories were requested, verify discovery from Pi's own output, not from the model's self-report: every installed skill must expose a readable `SKILL.md` at its linked path, and `pi -p 'Reply OK' --mode json` must mention a sample of the installed names in its loaded-resource listing. Some skills set `disable-model-invocation: true`, so the model may not offer them by name — that is policy, not an install failure; asking the model "do you have skill X" proves nothing. Report installed names, skipped duplicates, skipped repos with the README-based reason, and dangles separately; do not delete a dangling link to “fix” it — it is the checkout's intentional pointer into a skills repo.

   For Herdr setup, also verify `herdr --version`, `herdr integration status`, and `test -s ~/.pi/agent/extensions/herdr-agent-state.ts` on the remote host. Integration status must be current and the file present; these checks alone do not prove the Herdr-managed Pi launch path.

   When repairing PATH, identify the login shell and startup files it reads in non-interactive SSH; compare with interactive PATH and edit only the applicable file while preserving content and system PATH priority. Never assume zsh or hard-code a startup filename.

## Report

For each host, report connection route and macOS version; observed `pi --version` and, when requested, `herdr --version`; Pi default provider and requested/configured/skipped provider lists; local credential-readiness results for each configured provider; Hindsight endpoint plus the authenticated bank-list and `hindsight_diagnose` results when Hindsight was requested; Herdr integration status and the `herdr` skill state when installed; requested skill repos with their installed/skipped outcome and the README path used; and separate pass/fail/not-run results for the direct SSH Pi runtime and Herdr-managed remote Pi runtime checks. Report the real default-provider `pi -p` result only when Pi setup was requested and authorized; otherwise state it was not run. Local auth readiness does not prove live connectivity for non-default providers. Separate verified facts from blocked, skipped, unknown, and not-run items.
