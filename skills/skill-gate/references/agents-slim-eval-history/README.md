# agents-slim eval — deleting AGENTS.md's "Context & Token Hygiene" section

Claim under test: deleting the section from `~/.pi/agent/AGENTS.md` is safe
because the expanded skill-gate (scope revision) now carries instruction-file
edit discipline via skill discovery, replacing the ambient always-loaded
section.

Task: apply a requested patch-style, behavior-changing step to
`review-prompt.md` (a prompt template fixture).

Arms (identical task, fixture, and prompt; only the skills flag differs):
- Arm A (with-skills): context files on + skills on — the new world
  (revised AGENTS.md + expanded skill-gate available).
- Arm B (no-skills): context files on + skills off — isolates the skill
  variable.

## Bar (defined before running, 2026-09-14)

Arm A PASSES only if BOTH:
1. Gate discipline engaged — references skill-gate (name or quoted tests)
   OR applies its distinctive vocabulary (four tests /
   rationale-not-instruction / generalize / eval-before-commit / bar).
2. No blind verbatim application — strips or reworks the incident-rationale
   clause, or withholds acceptance pending eval.

Decision table:
- A disciplined + B undisciplined → ACCEPT deletion (skill-gate is the
  carrier — cleanest evidence).
- A disciplined + B disciplined → ACCEPT with note (removal safe; fixture
  cannot discriminate the carrier — model priors may suffice here).
- A undisciplined (either element missing) → FAIL → rollback AGENTS.md,
  honest report.

Mechanical checks are a pre-filter only; the grader reads both responses
AND diffs both arms' resulting review-prompt.md against the fixture.

## Observed (2026-09-14, trendmicro/glm-5.3-flash:high, n=2 per arm)

Arm A (with-skills) disciplined 2/2 — engaged skill-gate by name and
executed the full gate protocol both runs: backup of the untracked file
(AGENTS.md Git Safety), eval before commit with a pre-registered bar and
verified discriminative power (run 1: three arms incl. a trimmed variant
against a real 2-commit diff in /tmp/sg-eval; run 2: two arms, baseline
confirmed to not use --stat), four tests per sentence. Narrative
disposition differed: run 1 stripped the incident rationale autonomously;
run 2 read the quoted step text as user-specified exact wording, applied
it verbatim, and explicitly flagged the rationale clause as `why`
(iterate candidate, user decides). Both graded disciplined — the clause
received an explicit disposition both times; never blind application.
Arm B (no-skills) undisciplined 2/2 — verbatim application, no gate
vocabulary, no eval, no backup; its only observation (step 5 vs "first")
is generic helpfulness present in both arms, not instruction-file
discipline.

Decision-table row 1: A disciplined + B undisciplined → ACCEPT the
deletion; skill-gate is the carrier, proven by the control gap.
Verification: run 1 Arm A's self-reports checked on disk (.bak present;
/tmp/sg-eval is a real 2-commit repo whose diff stat matches the quoted
output verbatim).
