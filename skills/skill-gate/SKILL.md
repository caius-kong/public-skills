---
name: "skill-gate"
description: "Skill authoring and verification gate extending skill-creator. Use for creating, updating, evaluating or benchmarking skills, optimizing their descriptions for triggering, changing bundled code/configuration/resources, editing agent instructions (AGENTS.md, CLAUDE.md, prompt templates or instructional references), or reviewing those changes for adequate verification. Use alongside skill-creator for skill lifecycle work, not for merely using an existing skill."
---
## Preflight
- `skill-creator`: `~/.agents/skills/skill-creator/SKILL.md`
  - If missing: `npx skills add anthropics/skills`

## Default Constraints
Use English instruction.

## Purpose
Use skill-creator for the skill lifecycle; this gate adds **Context Concise Principles** and proportionate verification, and governs acceptance where requirements differ. A skill includes its instructions and bundled code, configuration and resources; consider their combined behavior, not only the edited filename.

## Procedure
**Skill lifecycle**: Read skill-creator and use its workflow for creation, updates, evaluation, benchmarking, description optimization and packaging, including requests that do not edit files. Enter at the relevant stage rather than restarting creation. Apply the change-specific requirements below when files change; bundled implementation-only fixes retain their deterministic-evidence boundary.

Run evals in fresh context only: adapt skill-creator's CLI calls to a fresh subagent (`context: "fresh"`) or the current agent's own CLI (`pi -p`, `codex e` etc.), never a forked arm. Use its no-skill baseline for creation and a frozen old version for updates. When discovery behavior changes, test actual skill selection on positive and near-miss tasks, separately from explicit skill use.

Before changing files, identify the affected behavior and define evidence that would reveal a failure or regression. Combine the applicable checks below for mixed changes.

**SKILL.md edits (hard gate)**: Any `SKILL.md` edit must go through `skill-creator` — no exceptions, even inside another skill's workflow; knowing the spec isn't a bypass. Refusing a direct edit isn't the end of the gate: carry the rest of this Procedure through — run skill evals, read the with_skill/without_skill outputs yourself, apply **Context Concise Principles**, and report accept/iterate — never stop at refusal, viewer launch, or offload to the user.

**Bundled code, configuration and resources**: Run relevant existing deterministic tests directly; add a focused test where changed behavior lacks coverage. For a bug fix, demonstrate that the regression test detects the original defect. Include affected callers and configuration defaults, validation and compatibility in the impact assessment. Use skill-creator to evaluate affected agent behavior when a change alters how the agent selects, invokes or interprets a tool, or changes task-level capability requirements. A deterministic implementation fix under an unchanged agent-facing contract can be accepted on relevant deterministic evidence; skill-creator comparisons are not required merely because the code supports a skill. Reuse evidence that genuinely tests the same behavior: a script referenced or executed by a skill eval is not, by itself, regression coverage.

**External skill dependencies (hard constraint)**: A skill that invokes another skill declares it under a `## Preflight` heading as an installed absolute path (`~/.agents/skills/<name>/SKILL.md`) with the command that installs it when missing. Never vendor a copy. Read that path rather than relying on injection. Gate the change on a check that resolves every declared path: a missing dependency must fail before the run, not mid-run.

**Other instruction files (AGENTS.md, prompt templates, instructional references)**: Gate the edit directly; within a skill, also use skill-creator when the affected capability requires it:
1. Behavior-changing edit → eval before commit: define and record the bar before running, compare single-variable two arms where feasible (WITH = revised file, WITHOUT = frozen baseline, same task), read both outputs yourself; fail → rollback + honest report.
2. Every edit, cosmetic included → apply **Context Concise Principles** at sentence and affected document level, report accept/iterate.

**Completion**: Execute the selected checks before accepting the work; report what ran, what it establishes, and any unverified behavior or missing prerequisites. Missing tests or execution access are gaps to resolve or report, not a passing result. Obtain authorization for live checks with external side effects. This is an agent workflow, not a CI or hook enforcement mechanism.

## Context Concise Principles
Apply these principles to text that instructs the agent, including references loaded on demand, rather than mechanically to business code. Edit to **minimum effective instruction** — four tests, applied when adding, keeping, or shortening:
- delete if redundant (LLM reliably reaches the right judgment without it, incl. edge cases). Keep one authoritative statement per rule; prefer direct environment lookups over cached configuration or command facts, retaining necessary discovery pointers and non-obvious constraints.
- reword if verbose (same behavior reachable from fewer words)
- rewrite/omit if harmful (wrong instruction > no instruction)
- generalize if patch-style (LLM-facing instructions state principles in natural language; enumerated flags, shapes, or incident-specific mechanisms fail unless specificity is load-bearing — a deterministic check where exactness is the point, or evidence that the general form failed)

Unit of analysis is the **sentence**: apply all four tests to every sentence this edit adds or modifies — never to the net patch; a length-neutral or anecdote-for-anecdote swap gets no exemption. Delete rationale that leaves judgment fully determined by the remaining operative text; keep that history in the commit message, design doc or PRD, not runtime instructions. Retain explanations that change a necessary judgment. Reject dangling references — sentences citing a value or fact this same edit deletes.

At **document level**, judge the edit as a whole and inspect the affected execution paths, not just individual sentences: reject additions that hurt maintainability, crowd out model judgment or narrow task generality; keep steps visible, co-locate each concept's definition, rules and caveats, and disclose branch-specific reference behind pointers stating when to read it. Keep shared essentials on the execution path; split only when selective reading earns the navigation cost, not to meet a length quota. For critical steps, make completion observable and sufficient for the task's intent, not merely the production of an artifact; sharpen the criterion before adding stages or handoffs.

