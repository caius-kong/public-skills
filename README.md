# public-skills

Agent skills by [caius-kong](https://github.com/caius-kong), published one at a
time from a private development repo. Each skill is self-contained — a
`SKILL.md` plus its references, scripts and evals — and lives here exactly once.

## Install

```bash
git clone https://github.com/caius-kong/public-skills.git
cd public-skills

./link-skills.sh claude     # ~/.claude/skills/
./link-skills.sh codex      # ~/.agents/skills/ (shared with Pi)
./link-skills.sh pi         # ~/.agents/skills/ (shared with Codex)
./link-skills.sh openclaw   # ~/clawd/skills/

./link-skills.sh all        # every agent above
```

Symlinks mean one source of truth: edit a skill here and every agent sees the
change. `link-skills.sh` never overwrites a real directory unless you pass
`--force`; an existing symlink is repointed.

Plain copies work too — `cp -r skills/<name> ~/.claude/skills/` — but you have
to re-copy after every update.

| Agent | Skills directory |
|-------|------------------|
| Claude Code | `~/.claude/skills/` |
| Codex | `~/.agents/skills/` (shared) |
| Pi | `~/.agents/skills/` (shared) |
| OpenClaw | `~/clawd/skills/` |

> **OpenClaw 2026.7.1+** blocks symlinks that resolve outside the workspace
> root. `./link-skills.sh openclaw` sets `skills.load.allowSymlinkTargets` in
> `~/.openclaw/openclaw.json` so the symlinks are accepted.

## Skills

<!-- skills-list-start -->
- **[install-pi-on-remote](./skills/install-pi-on-remote/SKILL.md)** — Deploy a remote macOS Mac as an agents server: configure dedicated passwordless SSH over LAN or Tailscale, run the repository bootstrap.sh to install Pi, install Herdr with its Pi integration and its agent skill, and verify both direct-SSH Pi and Herdr-managed remote Pi instances. Use whenever the user asks to install/reinstall Pi or Herdr on another Mac, set up remote SSH agents, or deploy an agents server. macOS only.
- **[planner-executor-pipeline](./skills/planner-executor-pipeline/SKILL.md)** — Plan→Test Author→Execute→Gate→Conformance staged pipeline for turning a goal into shipped, verified code. Use when the user wants a goal planned and implemented end-to-end with contract handoffs between stages, wants an auditable multi-stage agent workflow (PLAN / TEST_AUTHOR / EXECUTE / GATE / CONFORMANCE), or asks for /planner-executor-pipeline; also use when discussing or modifying this pipeline's protocol.
- **[skill-gate](./skills/skill-gate/SKILL.md)** — Skill authoring and verification gate extending skill-creator. Use for creating, updating, evaluating or benchmarking skills, optimizing their descriptions for triggering, changing bundled code/configuration/resources, editing agent instructions (AGENTS.md, CLAUDE.md, prompt templates or instructional references), or reviewing those changes for adequate verification. Use alongside skill-creator for skill lifecycle work, not for merely using an existing skill.
<!-- skills-list-end -->

## License

MIT — see [LICENSE](./LICENSE).
