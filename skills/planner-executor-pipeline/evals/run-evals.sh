#!/usr/bin/env bash
# planner-executor-pipeline evals — skill-creator protocol runner.
#
# Modelled on skills/skill-gate/evals/run-converted.sh.
#
# The skill under test IS the pipeline protocol:
#   WITH    = live skills/pi/planner-executor-pipeline/ (SKILL.md + references/)
#   WITHOUT = frozen pre-skill prompt-template snapshot (skill-creator's
#             "improving an existing skill" baseline)
#
# Isolation (both layers required):
#   - fs:  each arm gets its own scratch dir with its own copy of the skill
#   - agent: each arm runs as a FRESH process (`pi -p`, never a fork). A forked
#            arm would inherit this session's analysis and invalidate the
#            comparison (see skill-gate's References note).
#
# The evals are read-only analysis probes: no subagent is dispatched, so one
# fresh `pi -p` arm per configuration is a cheap, faithful probe of whether the
# protocol text steers the orchestrator's decisions.
#
# Usage:
#   bash run-evals.sh [eval-name ...]        # default: all four
#   EVAL_RUNS=2 bash run-evals.sh gate-authz-before-violation
set -euo pipefail

EVAL_DIR="$(cd "$(dirname "$0")" && pwd -P)"
SKILL_DIR="$(cd "$EVAL_DIR/.." && pwd -P)"
WS_ROOT="${EVAL_WS_ROOT:-$(cd "$SKILL_DIR/.." && pwd -P)/planner-executor-pipeline-workspace}"
ITER="${EVAL_ITERATION:-iteration-1}"
BASE="$WS_ROOT/$ITER"

# Resolve pi by absolute path: a pnpm self-update can leave a stale shim so
# bare `pi` stops resolving, which silently yields empty transcripts.
PI_BIN="$(command -v pi 2>/dev/null || true)"
for cand in "$HOME/Library/pnpm/bin/pi" "$HOME/.local/bin/pi" "/opt/homebrew/bin/pi"; do
  [ -n "$PI_BIN" ] && break
  [ -x "$cand" ] && PI_BIN="$cand"
done
[ -n "$PI_BIN" ] || { echo "FATAL: cannot locate pi" >&2; exit 2; }

PROVIDER="${EVAL_PROVIDER:-trendmicro}"
MODEL="${EVAL_MODEL:-deepseek-v4.1-flash}"
THINKING="${EVAL_THINKING:-low}"
RUNS="${EVAL_RUNS:-1}"

# Frozen baseline: the pre-skill prompt template, kept beside this runner so the
# eval set is self-contained (the /tmp original is gone).
FROZEN="$EVAL_DIR/frozen-baseline.md"

SANDBOXES=()
# Remove per-run sandboxes on exit (they live outside the workspace on purpose).
cleanup_sandboxes() { for d in "${SANDBOXES[@]:-}"; do [ -n "$d" ] && rm -rf "$d"; done; }
trap cleanup_sandboxes EXIT
EVALS=("$@")
if [ ${#EVALS[@]} -eq 0 ]; then
  EVALS=(handoff-contract-shape gate-authz-before-violation bounded-wait-terminal frozen-test-fix-route)
fi

eval_id_of() { # $1 = eval name -> numeric id from evals.json
  python3 -c 'import json,sys
spec=json.load(open(sys.argv[1],encoding="utf-8"))
print(next((e["id"] for e in spec["evals"] if e["name"]==sys.argv[2]), ""))' \
    "$EVAL_DIR/evals.json" "$1"
}

for ev in "${EVALS[@]}"; do
  fx="$EVAL_DIR/$ev"
  eid="$(eval_id_of "$ev")"
  out="$BASE/eval-${eid}-$ev"
  rm -rf "$out"   # never let stale run dirs aggregate into this invocation
  [ -d "$fx" ] || { echo "SKIP $ev: no fixture at $fx" >&2; continue; }
  mkdir -p "$out"
  cp "$fx/prompt.txt" "$out/prompt.txt"

  # Arm payloads are staged OUTSIDE the eval dir tree, one root per arm, so a
  # run can never read its sibling arm's files. (Real incident: a WITHOUT arm
  # escaped its dir and read the sibling WITH/references/artifacts.md, importing
  # the very rule under test — the discrimination was invalid.)
  for arm in WITH WITHOUT; do
    root="$BASE/.arms/eval-${eid}-$ev/$arm"
    rm -rf "$root"; mkdir -p "$root/references"
    if [ "$arm" = "WITH" ]; then
      cp "$SKILL_DIR/SKILL.md" "$root/planner-executor-pipeline-SKILL.md"
      cp "$SKILL_DIR"/references/*.md "$root/references/"
    else
      cp "$FROZEN" "$root/planner-executor-pipeline-SKILL.md"
      : > "$root/references/.keep"   # deliberately empty: baseline has no refs
    fi
  done

  for arm in WITH WITHOUT; do
    for n in $(seq 1 "$RUNS"); do
      d="$out/$arm/run-$n"; mkdir -p "$d/outputs"
      FAILED=0
      # Isolation that actually holds: each run's cwd is a fresh mktemp dir under
      # a SEPARATE system temp root, so no sibling arm is reachable by any
      # relative path (../WITHOUT/… cannot resolve). An earlier attempt used
      # sibling dirs under $BASE/.sandbox and a baseline arm still read
      # ../WITH/references/artifacts.md — verified in real transcripts.
      sandbox="$(mktemp -d "${TMPDIR:-/tmp}/pe-eval-${arm}-XXXXXX")"
      SANDBOXES+=("$sandbox")
      mkdir -p "$sandbox/outputs"
      cp "$out/prompt.txt" "$sandbox/prompt.txt"
      cp "$BASE/.arms/eval-${eid}-$ev/$arm/planner-executor-pipeline-SKILL.md" "$sandbox/"
      mkdir -p "$sandbox/references"
      cp "$BASE/.arms/eval-${eid}-$ev/$arm"/references/*.md "$sandbox/references/" 2>/dev/null || true
      (
        cd "$sandbox"
        # hard isolation check: nothing may resolve upward into another arm's dirs
        for probe in ../../WITH ../../WITHOUT ../../NO_SKILL ../WITH ../WITHOUT ../NO_SKILL; do
          if [ -e "$probe" ]; then echo "FATAL: sandbox can reach $probe" >&2; exit 4; fi
        done
        perl -e 'alarm 900; exec @ARGV' "$PI_BIN" \
          --no-skills --no-context-files --no-extensions --no-session --offline \
          --provider "$PROVIDER" --model "$MODEL" --thinking "$THINKING" \
          --print "$(cat prompt.txt)" > transcript.raw 2> run.err < /dev/null || true
      )
      # one retry on an empty arm: this is provider/latency flakiness, not a
      # behavioural signal, and a single slow run must not abort the set.
      if [ ! -s "$d/transcript.raw" ]; then
        echo "  (retry: empty raw transcript for $ev/$arm/run-$n)" >&2
        (cd "$sandbox" && perl -e 'alarm 900; exec @ARGV' "$PI_BIN" \
          --no-skills --no-context-files --no-extensions --no-session --offline \
          --provider "$PROVIDER" --model "$MODEL" --thinking "$THINKING" \
          --print "$(cat prompt.txt)" > transcript.raw 2> run.err < /dev/null || true)
      fi
      cp "$sandbox/transcript.raw" "$d/transcript.raw" 2>/dev/null || true
      perl -pe 's/\e\][^\a\e]*(?:\a|\e\\)//g' "$d/transcript.raw" > "$d/transcript.md" \
        || cp "$d/transcript.raw" "$d/transcript.md"
      cp "$d/transcript.md" "$d/outputs/response.md"
      # isolation self-check: the transcript must not reference a sibling arm
      if grep -qE "sibling|WITH/references|WITHOUT/references|/WITH/|/WITHOUT/" "$d/transcript.md" 2>/dev/null; then
        echo "FATAL: $ev/$arm/run-$n mentions a sibling arm path — arms are not isolated" >&2
        FAILED=1
      fi
      bytes=$(wc -c < "$d/transcript.md" | tr -d ' ')
      printf "  %-30s %-8s run-%s  %s bytes\n" "$ev" "$arm" "$n" "$bytes"
      # fail closed on an empty arm: a missing run must never be silently graded
      if [ "$bytes" -lt 50 ] || [ -z "$(tr -d '[:space:]' < "$d/transcript.md")" ]; then
        echo "FATAL: $ev/$arm/run-$n produced no usable transcript ($bytes bytes) — see $d/run.err" >&2
        tail -3 "$d/run.err" >&2 || true
        FAILED=1
      fi
    done
    [ "${FAILED:-0}" = "1" ] && { echo "Aborting before grading (empty arm above)." >&2; exit 3; }
  done
done

echo
echo "Grading (programmatic evidence per agents/grader.md)..."
python3 "$EVAL_DIR/grade.py" "$BASE"

echo
echo "Aggregate:"
echo "  (cd ~/.agents/skills/skill-creator && python3 -m scripts.aggregate_benchmark $BASE --skill-name planner-executor-pipeline)"
echo "Grader must still read both transcripts personally — flags are a pre-filter."