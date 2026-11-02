# skill-gate evals

Gate behavioral evals use skill-creator's paired execution, evidence-based grading
and review viewer. Compare the revised gate with a frozen old version on matched
inputs; a passing pair is a regression guard, not evidence of improvement.

## Runtime versus development assets

The runtime instructions are `../SKILL.md`, which delegates capability evaluation
to the installed skill-creator. It does not load or execute this `evals/` directory
during ordinary gate use. Prompts, fixture code and assertions here are reusable
behavioral regression assets for developing skill-gate, not new runtime helpers.
Raw transcripts, grades, timing and HTML viewers are acceptance artifacts kept in
the ignored sibling workspace, not shipped as runtime dependencies. Existing
historical receipts remain records, not prerequisites for using the gate.

## Whole-skill change coverage

| ID | Case | Evidence |
|---|---|---|
| 4 | script-regression | Actually observes the unsafe fallback test fail before fixing it, then passes the focused regression without unnecessary LLM comparisons. |
| 5 | config-regression | Runs the shipped-default test and reports failure despite an unrelated fixture eval PASS; no live sends. |
| 6 | capability-boundary | Distinguishes an adequately tested internal refactor from an output-contract change requiring caller checks and affected skill-creator capability evals. |
| 7 | specificity-contract | Prospective clarification: preserve an exact checker/exit gate under an explicit scoped contract, remove incidental history, and report unexecuted capability evals honestly. |

Freeze the complete pre-edit skill in the sibling ignored `skill-gate-workspace/`. For each case,
prepare identical isolated inputs and fresh old/revised executors; provide only
that arm's gate. Run both arms in the same wave. IDs 4/5 require tools and real
local test execution: a proposed command is not execution evidence. Read the
full tool transcripts and outputs, grade using skill-creator's `agents/grader.md`,
save its `grading.json`/`timing.json`/`eval_metadata.json`, aggregate with
`aggregate_benchmark.py`, and generate the official review viewer. Record unavailable
metrics and missing runs explicitly. Retain cases 1-3 as Concise Principles and
instruction-routing regression guards. Report single-sample results as smoke
evidence, not a stability or significance claim.

`run-converted.sh` and `grade.py` below support only historical IDs 1-3. They do
not execute or grade IDs 4-7, and the legacy regex pre-filter is not an authoritative
grader for free-form reasoning.

## Whole-skill revision receipts (2026-10-16)

Frozen original versus first candidate: 12 fresh runs, followed by another 12
matched runs after observed overreach was corrected. The first candidate demanded
an unnecessary capability eval for the deterministic implementation fix; that
failure is retained rather than overwritten. The refined candidate explicitly
permits relevant deterministic evidence under an unchanged agent-facing contract.

Parent evidence grading of the refined wave: **17/18 for each arm**, with IDs
1/3/4/5/6 all 3/3. The unchanged historical ID2 assertion requiring retention of
the exact Git check fails in both arms. Both question its scope and prerequisites,
but the fixture also permits a migration-directory-only interpretation. Available
evidence does not settle whether the assertion or the responses are wrong; this
is an unresolved regression assertion, not a demonstrated fixture defect. The
failed score is preserved, and acceptance of that behavior remains pending.
The new cases passed in both arms, so no measured skill-benefit claim is made.

A separately preregistered ID7 follow-up made the checker scope, plan inputs and
exit-status requirements explicit. One fresh matched pair scored 3/3 in each arm:
both retain the precise deterministic check and delete incidental history. This
supports that boundary under the supplied contract, not a revision of ID2's failed
score, proof of model benefit, or a stability claim. Artifacts and official viewer:
`../skill-gate-workspace/iteration-specificity-contract-20261016/` (relative to the
skill root). The eval review also records that cases 4/5 explicitly request testing
and case 6 can invoke the old hard gate; none establishes automatic discovery or
isolates all newly added routing behavior.

Workspace: `../skill-gate-workspace/iteration-whole-skill-20261016-refined/`
(relative to the skill root), containing raw tool traces, per-run grades/timing,
`benchmark.json` and the official static `review.html`. Original candidate results
are retained in `iteration-whole-skill-20261016/`. One sample per arm; no variance
or reliability claim. Explicit gate use was tested, not automatic discovery or
CI/hook enforcement. Historical `results.json` remains untouched.

## Legacy format (converted to skill-creator's protocol, 2026-09-20)

The evals now use skill-creator's layout and tooling. The skill under test IS
the gate text:

- `gate-WITH`    = the live `skills/skill-gate/SKILL.md`
- `gate-WITHOUT` = a frozen pre-revision snapshot (skill-creator's
  "improving an existing skill" baseline)

Artifacts follow skill-creator's conventions: `eval-<id>-<name>/eval_metadata.json`,
`eval-<id>-<name>/<arm>/run-N/{transcript.md,grading.json}`, and a workspace-level
`benchmark.json` / `benchmark.md` produced by
`python -m scripts.aggregate_benchmark <iteration> --skill-name skill-gate`.

| File | Role |
|---|---|
| `evals.json` | all 7 eval specs; the legacy runner selects IDs 1-3 |
| `run-converted.sh` | the single runner (replaces 6 bespoke `run-*.sh`, 672 lines) |
| `grade.py` | programmatic **pre-filter** only — see the caveat below |
| `results.json` | the grader's authoritative per-eval verdicts for iteration-1 |
| `<name>/` | legacy IDs 1-3: diffs, baseline and `gate-WITHOUT.md`; IDs 4-7: prompts and task fixtures |

Run:

```bash
bash run-converted.sh                 # historical IDs 1-3 only, n=1
EVAL_RUNS=3 bash run-converted.sh     # n=3 for a variance-bearing run
```

## Isolation (both layers are mandatory)

1. **git/fs** — each arm gets its own `run-N` directory; nothing is shared.
2. **agent** — each arm is a FRESH process (`pi -p --no-skills --no-context-files
   --no-extensions --no-session`). **Never a forked arm**: a fork inherits this
   session's own analysis of the skill under test, which invalidates the baseline
   and biases the with-arm. This is not hypothetical — a real run was contaminated
   that way (see `SKILL.md` References).

## Grading caveat (measured, not assumed)

`grade.py` checks assertions programmatically and is a **pre-filter only**.
Measured divergence at iteration-1: on 2 of 5 evals it disagreed with a
fresh-context grader reading the same transcripts (rationale-swap: pre-filter
2/3 vs 1/3, grader 3/3 vs 2/3; language: pre-filter 1/3 vs 1/3, grader 3/3 vs
2/3). Because free-form prose varies ("## **ITERATE**" vs "Verdict: Iterate"),
a regex either misses true verdicts or passes on incidental word presence.
**The grader's reading is authoritative**; `benchmark.json` reflects the
pre-filter and is therefore conservative, not final.

## PASS criteria (rationale-swap)

- WITH arm: sentence-level flags for both the swapped anecdote and the
  dangling reference; overall verdict iterate. Bare ACCEPT = FAIL.
- WITHOUT arm: expected to let the edit through; the gap is the regression
  control.

## Observed results

- 2026-09-08, two runs (trendmicro/glm-5.3-flash:high, identical neutral
  prompt, only gate text differs): WITH arm 2/2 — enumerated S1/S2/S3,
  deleted the swapped anecdote as rationale (citing no-swap-exemption and
  why's sanctioned home), rejected the dangling reference by name,
  ITERATE. WITHOUT arm: run 1 kept the swapped anecdote as a load-bearing
  why (the historical failure mode); run 2 caught it only via generic
  tests. The old text's gap is stochastic — it leaves the analysis unit to
  model judgment — which is the defect class this revision pins down.
- Both arms in both runs also flagged the fixture's 30m budget vs 43m
  cited run contradiction (an unplanned but valid second defect in the
  anecdote sentence).

## Arm discipline

Fresh timestamped workspace per arm per run (no fixture reuse, no residue);
arms never read each other's outputs; only the gate text differs between
arms.

## scope-expand (2026-09-14 revision: gate covers all instruction files)

Revision: skill-gate expands from SKILL.md-only to all instruction files
loaded into agent context (AGENTS.md, prompt templates, profiles), with
strict internal branch separation — SKILL.md keeps the hard skill-creator
routing verbatim; other files get a direct gate (behavior-changing edit →
eval before commit; every edit → four tests). Motivation: AGENTS.md /
prompt templates / skills are the same instruction layer; separate gates
would duplicate the judgment text and drift (proven: AGENTS.md's
three-tests copy vs skill-gate's four).

Fixture `scope/`: two diffs — `skill-edit.diff` (cache-warmer SKILL.md,
patch-style) and `agents-edit.diff` (AGENTS.md, patch-style + behavior
change). Runner `run-scope-expand.sh`. FLAGS: bit1 = skill-creator
routing for the SKILL.md diff (crown-jewel regression guard), bit2 =
eval-before-commit discipline for the AGENTS.md diff, bit3 = patch-style
disposition for its sentence. PASS: WITH = ITERATE FLAGS=7.

Observed (2026-09-14, trendmicro/glm-5.3-flash:high, n=2): WITH 2/2
ITERATE FLAGS=7 — branch separation explicit both runs ("SKILL.md edit
(hard gate branch)" / "AGENTS.md edit (direct-gate branch)", "no
skill-creator routing for AGENTS.md"); eval-first discipline carried
with concrete pre-registered bars; run 2 additionally required the
`--workers 8` flag be kept only if the eval shows the general form
fails. WITHOUT 2/2 ITERATE FLAGS=1 — SKILL.md branch full quality both
runs; AGENTS.md ruled out of scope both runs ("GATE DOES NOT APPLY",
refusing analogical extension). The bit-2 gap is deterministic (the old
gate has no such branch), a cleaner discriminatrix than generalize's.

Operational notes: zai direct route 429 (insufficient balance) — route
switched to trendmicro (exclusion expired 2026-09-11); BSD grep max
repetition 255 ({0,300} → {0,240}); tool timeout must exceed the
runner's internal 2×900s worst case (run 2's WITH arm completed
manually in the same stamp dir after a 600s tool kill).

## iteration-1 results (2026-09-20, n=1)

Graded by **fresh-context reviewer subagents** (one per eval, read-only), which
read both transcripts and quoted evidence. `grade.py` numbers are the pre-filter
and differ on 2 evals (see caveat above).

| eval | WITH | WITHOUT | discriminating bit(s) | non-discriminating |
|---|---|---|---|---|
| rationale-swap | **3/3** | 2/3 | flags the anecdote swap as no-exemption rationale | verdict ITERATE; dangling-reference rejection (both pass) |
| generalize | **3/3** | 2/3 | applies the four-test framework and reaches the GENERALIZE disposition | verdict ITERATE; keeps the deterministic check |
| scope-expand | **3/3** | 1/3 | eval-before-commit for AGENTS.md; applies the tests to non-SKILL instruction files | SKILL.md hard gate (both pass) |

Every eval has a real, single-bit gap. Non-discriminating assertions are listed
honestly rather than dropped — they are regression guards, not discriminator.

### Known limits

- **n=1** per configuration: this is a discrimination smoke check, not a
  variance or significance claim. Use `EVAL_RUNS=3` before citing statistics.
- `aggregate_benchmark.py` **hardcodes** `metadata.runs_per_configuration: 3`
  (its line ~271) regardless of the actual count. At n=1 that field is WRONG;
  read `run_summary` instead and treat `stddev` as meaningless.
- `time_seconds` / `tokens` are 0 (the fresh-process runner does not report
  them); they are not timing evidence.
- `agents-slim/` is **not** converted: its variable is AGENTS.md, not a gate
  rule (arms are with-skills/no-skills). Kept as history in `references/`.
