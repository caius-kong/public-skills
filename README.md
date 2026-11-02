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
- **[skill-gate](./skills/skill-gate/)** — Extend skill-creator with Context Concise Principles and change-based verification.
<!-- skills-list-end -->

## License

MIT — see [LICENSE](./LICENSE).
