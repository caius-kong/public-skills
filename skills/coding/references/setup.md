# Sub-skill Setup Reference

When a sub-skill is not found, show the relevant install instructions below.
Repo README is authoritative — commands here may be outdated.

## mattpocock/skills

Skills: `grill-me`, `grill-with-docs`, `to-prd`, `diagnose`
Repo: https://github.com/mattpocock/skills

```bash
npx skills@latest add mattpocock/skills
# Then run once per project inside Claude Code:
/setup-matt-pocock-skills
```

## open-gsd/gsd-core

Skills: `gsd-progress`, `gsd-ui-phase`
Repo: https://github.com/open-gsd/gsd-core

```bash
npx @opengsd/gsd-core@latest
```

## anthropic-agent-skills

Skills: `frontend-design`, `webapp-testing`
Detection path: `~/.claude/plugins/marketplaces/anthropic-agent-skills/skills/<skill-name>/SKILL.md`

```bash
claude plugin install frontend-design@anthropic-agent-skills
claude plugin install webapp-testing@anthropic-agent-skills
```

## fix-jira

Install from the same source as `/coding` (user's custom skills repo).

## Codex delegation prerequisites (`--codex`)

Not a missing-skill case — checked before the first delegated step when `/coding --codex` runs on a GSD project. If any is unset, show the fix and wait.

- Codex CLI logged in: `which codex` resolves and `codex login` has run. Install: `npm install -g @openai/codex`.
- `gsd config-set workflow.cross_ai_command codex` — execute-phase's `--cross-ai` errors on an empty command.
- `gsd config-set workflow.plan_review_convergence true` — gate for `/gsd-plan-review-convergence`.
