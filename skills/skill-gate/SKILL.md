---
name: "skill-gate"
description: "Extend skill-creator with Context Concise Principles and change-based verification. Use when creating or modifying a skill, including bundled scripts, configuration and resources; editing AGENTS.md or prompt templates; or reviewing whether a change was adequately tested."
---
## Purpose
Extend skill-creator with **Context Concise Principles** and verification proportionate to the change. A skill includes its instructions and bundled code, configuration and resources; consider their combined behavior, not only the edited filename.

## Procedure
Before editing, identify the affected behavior and define evidence that would reveal a regression. Combine the applicable checks below for mixed changes.

**SKILL.md edits (hard gate)**: Any `SKILL.md` edit must go through `skill-creator` — no exceptions, even inside another skill's workflow; knowing the spec isn't a bypass. Refusing a direct edit isn't the end of the gate: carry the rest of this Procedure through — run skill evals, read the with_skill/without_skill outputs yourself, apply **Context Concise Principles**' delete/reword/rewrite/generalize test (reject patch accretions that hurt maintainability, crowd out model judgment, or narrow task generality), and report accept/iterate — never stop at refusal, viewer launch, or offload to the user.

**Bundled code, configuration and resources**: Run relevant existing deterministic tests directly; add a focused test where changed behavior lacks coverage. For a bug fix, demonstrate that the regression test detects the original defect. Include affected callers and configuration defaults, validation and compatibility in the impact assessment. Use skill-creator to evaluate affected agent behavior when a change alters how the agent selects, invokes or interprets a tool, or changes task-level capability requirements. A deterministic implementation fix under an unchanged agent-facing contract can be accepted on relevant deterministic evidence; skill-creator comparisons are not required merely because the code supports a skill. Reuse evidence that genuinely tests the same behavior: a script referenced or executed by a skill eval is not, by itself, regression coverage.

**External skill dependencies (hard constraint)**: A skill that invokes another skill declares it under a `## Preflight` heading as an installed absolute path (`~/.agents/skills/<name>/SKILL.md`) with the command that installs it when missing. Never vendor a copy. Read that path rather than relying on injection. Gate the change on a check that resolves every declared path: a missing dependency must fail before the run, not mid-run.

**Other instruction files (AGENTS.md, prompt templates, instructional references)**: Gate the edit directly; within a skill, also use skill-creator when the affected capability requires it:
1. Behavior-changing edit → eval before commit: define and record the bar before running, compare single-variable two arms where feasible (WITH = revised file, WITHOUT = frozen baseline, same task), read both outputs yourself; fail → rollback + honest report.
2. Every edit, cosmetic included → apply **Context Concise Principles** to each sentence, report accept/iterate.

**Completion**: Execute the selected checks before accepting the change; report what ran, what it establishes, and any unverified behavior or missing prerequisites. Missing tests or execution access are gaps to resolve or report, not a passing result. Obtain authorization for live checks with external side effects. This is an agent workflow, not a CI or hook enforcement mechanism.

## Context Concise Principles
Apply these principles to text that instructs the agent, including references loaded on demand, rather than mechanically to business code. Edit to **minimum effective instruction** — four tests, applied when adding, keeping, or shortening:
- delete if redundant (LLM reliably reaches the right judgment without it, incl. edge cases)
- reword if verbose (same behavior reachable from fewer words)
- rewrite/omit if harmful (wrong instruction > no instruction)
- generalize if patch-style (LLM-facing instructions state principles in natural language; enumerated flags, shapes, or incident-specific mechanisms fail unless specificity is load-bearing — a deterministic check where exactness is the point, or evidence that the general form failed)

Unit of analysis is the **sentence**: apply all four tests to every sentence this edit adds or modifies — never to the net patch; a length-neutral or anecdote-for-anecdote swap gets no exemption. Rationale is not instruction: dates, historical numbers, and incident narratives are `why` — if removing the sentence leaves the model's judgment fully determined by the remaining operative text, it fails the delete test; the legitimate home for `why` is the commit message, design doc, or PRD. Reject dangling references — sentences citing a value or fact this same edit deletes.

## Default Constraints
Use English instruction.

## References
Resolve each `/command` in Tasks against its path below before executing.
- `skill-creator`: `~/.agents/skills/skill-creator/SKILL.md`
  - If missing: `npx skills add anthropics/skills`
  - Evals run in fresh context only: replace `run_eval.py`'s / `improve_description.py`'s `claude -p` call with a fresh subagent (`context: "fresh"`) or current agent's own CLI (`pi -p`, `codex e` etc.); never a forked arm.
