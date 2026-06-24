# public-skills

Personal Claude Code skills by [caius-kong](https://github.com/caius-kong).

## Installation

```bash
# Install a single skill
git clone https://github.com/caius-kong/public-skills.git
cp -r public-skills/skills/<skill-name> ~/.claude/skills/
```

Or install all skills at once:

```bash
cp -r public-skills/skills/* ~/.claude/skills/
```

Then restart Claude Code to pick up the new skills.

<!-- skills-list-start -->
## Skills

- [coding](skills/coding/): Single entry point for the standard development workflow.
  - [fix-jira](skills/fix-jira/): Sub-skill of `coding` — Use when a JIRA bug ticket (URL or issue key) needs root-cause investigation and a fix.
  - [copilot-pr-review-loop](skills/copilot-pr-review-loop/): Sub-skill of `coding` — Use when a PR needs iterative Copilot review cycles — after pushing commits, when Copilot review needs triggering or re-triggering, or when fixing Copilot feedback before re-submitting for another review round.

<!-- skills-list-end -->
