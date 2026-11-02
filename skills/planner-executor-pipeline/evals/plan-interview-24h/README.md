# PLAN interview continuity and timeout: parent validation packet

This packet defines the small PLAN follow-up. It adds no request counters, state schema, interview journal, resume framework, or real-day soak test.

## Frozen baseline and staged PLAN

Pre-edit copies of the pipeline skill, all references, and the live user PLAN agent are frozen outside the worktree at `/tmp/simple-plan-interview-baseline/`; hashes are recorded in `/tmp/simple-plan-interview-eval/arm-manifest.sha256`. The staged revised PLAN is `/tmp/simple-plan-interview-eval/revised-plan.md`. Its interview-only baseline counterpart is `/tmp/simple-plan-interview-eval/baseline-plan.md`; the wrapper-only delta from the live baseline is `/tmp/simple-plan-interview-eval/baseline-harness-only.diff`.

Do not install either staged agent automatically. User-agent integration is parent-owned and separate.

## Fresh native behavioral evals

Use the same native PLAN runtime, tools, model, timeout extension, task prompt, cwd, evidence pack, and user answer sequence in both arms. For the PLAN-agent eval, load the staged baseline-plan and revised-plan definitions respectively. The baseline wrapper points `skills`/`skillPath` to the frozen baseline and loads the same timeout extension as the revised wrapper; its only changes from the frozen PLAN file are this matched skill/harness wiring plus a pre-plan read pointer to the frozen bundle. Do not load revised pipeline rules in the baseline arm. If this isolation cannot be maintained in a native agent run, stop and switch to the explicitly labeled fallback below.

For the planning-skill eval, use the same external PLAN instruction and tool harness in both arms, loading only the baseline skill/reference bundle or only the revised skill/reference bundle. Treat the whole matched protocol bundle as the variable; this does not identify a single-sentence cause.

Run neutral prompts in `normal-clarification.txt` and `new-ambiguity.txt` in fresh contexts. The parent supplies the same realistic explanation request, partial response, short pause, and later ruling to each arm; those answers are not preloaded in the task prompt. Record prompts, answer sequence, loaded paths, model/runtime identity, and both transcripts. Read both outputs and evaluate same-run continuity, focused unresolved-only follow-up, verbatim replies, no invented decisions, quiet wait, and ordinary PlanHandoff shape. Do not claim a result until the parent runs and reviews the paired arms.

If native staging cannot isolate each arm, run the same read-only delegate on an explicit decision fixture and give it exactly one plan file and one pipeline bundle per fresh arm. Label this a prompt-behavior eval, not live-agent end-to-end behavior.

## Native request-window probe

Run `native-probe/run.sh`. It tests the installed native supervisor-channel implementation with an ephemeral source copy and resolver for Pi's installed `typebox` package. It creates an actual request through `registerNativeSupervisorClient`, asserts persisted `expiresAt - createdAt === 86400000`, answers it, checks a child without the extension retains the native 600000 ms default, and confirms the foreground/parent guard fails before mutation. This is accelerated deterministic evidence, not a real 24-hour soak or proof of parent orchestration.

For a separate native production-path check, directly launch PLAN with `async:true`, `options.context:"fresh"`, and `options.timeoutMs:86400000`; explicitly load the staged agent's `subagentOnlyExtensions` path and keep ambient extension behavior intact. Inspect that run's supervisor request JSON and record the two timestamps and difference. Check parent/non-PLAN defaults separately. Do not wait a real day or claim hard-kill handoff.

The supported pipeline dispatch is direct async PLAN only. Foreground or shared-composite/workflow PLAN is unsupported because it cannot isolate the environment override. The extension itself detects a detached child runner, not agent identity inside a composite; a caller violating the dispatch contract could affect sibling steps in the same runner. This is an explicit residual limitation, not hidden by a new runtime guard.
