---
name: "skill-gate"
description: "Guarded SKILL.md editing procedure. Use when editing any SKILL.md (create/patch/update/delete), or when asked why a skill edit skipped evals."
---
## When to Use
Any SKILL.md edit — creating, patching, updating, or deleting a skill. Also when auditing whether a past skill edit followed the gate, and when a skill edit's change report is being produced.

## Procedure
**SKILL.md edit gate (hard)**: Any `SKILL.md` edit must go through `skill-creator` — no exceptions, even inside another skill's workflow; knowing the spec isn't a bypass. Refusing a direct edit isn't the end of the gate: carry the rest of this Procedure through — run skill evals, read the with_skill/without_skill outputs yourself, apply **Context Concise Principles**' delete/reword/rewrite/generalize test (reject patch accretions that hurt maintainability, crowd out model judgment, or narrow task generality), and report accept/iterate — never stop at refusal, viewer launch, or offload to the user.

## Context Concise Principles
`SKILL.md` load into agent context. Edit to **minimum effective instruction** — four tests, applied when adding, keeping, or shortening:
- delete if redundant (LLM reliably reaches the right judgment without it, incl. edge cases)
- reword if verbose (same behavior reachable from fewer words)
- rewrite/omit if harmful (wrong instruction > no instruction)
- generalize if patch-style (LLM-facing instructions state principles in natural language; enumerated flags, shapes, or incident-specific mechanisms fail unless specificity is load-bearing — a deterministic check where exactness is the point, or evidence that the general form failed)

Unit of analysis is the **sentence**: apply all four tests to every sentence this edit adds or modifies — never to the net patch; a length-neutral or anecdote-for-anecdote swap gets no exemption. Rationale is not instruction: dates, historical numbers, and incident narratives are `why` — if removing the sentence leaves the model's judgment fully determined by the remaining operative text, it fails the delete test; the legitimate home for `why` is the commit message, design doc, or PRD. Reject dangling references — sentences citing a value or fact this same edit deletes.

## References
Resolve each `/command` in Tasks against its path below before executing.
- `skill-creator`: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/skill-creator/skills/skill-creator/SKILL.md
