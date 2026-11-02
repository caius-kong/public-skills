#!/usr/bin/env bash
# skill-gate evals — skill-creator protocol runner.
#
# Replaces the six bespoke run-*.sh scripts (672 lines, make_arm/run_arm/
# mech_check copied 3-6 times each). One runner, driven by evals/evals.json.
#
# The skill under test IS the gate text:
#   gate-WITH    = live skills/skill-gate/SKILL.md
#   gate-WITHOUT = frozen pre-revision snapshot (skill-creator's
#                  "improving an existing skill" baseline)
#
# Isolation (both layers required):
#   - git/fs: each arm gets its own scratch dir copied from the fixture
#             (no git repo involved — fixtures are plain files)
#   - agent:  each arm runs as a FRESH process (`pi -p`, never a fork).
#             See the References note in SKILL.md: a forked arm inherits this
#             session's analysis and invalidates the comparison.
#
# Usage:
#   bash run-converted.sh [eval-name ...]      # legacy instruction cases 1-3 only
#   EVAL_RUNS=2 bash run-converted.sh language # n>1 for variance
set -euo pipefail

EVAL_DIR="$(cd "$(dirname "$0")" && pwd -P)"
SKILL_DIR="$(cd "$EVAL_DIR/.." && pwd -P)"
WS_ROOT="${EVAL_WS_ROOT:-$(cd "$SKILL_DIR/.." && pwd -P)/skill-gate-workspace}"
ITER="${EVAL_ITERATION:-iteration-1}"
BASE="$WS_ROOT/$ITER"

PROVIDER="${EVAL_PROVIDER:-trendmicro}"
MODEL="${EVAL_MODEL:-glm-5.3-flash}"
THINKING="${EVAL_THINKING:-max}"
RUNS="${EVAL_RUNS:-1}"

EVALS=("$@")
if [ ${#EVALS[@]} -eq 0 ]; then
  EVALS=(rationale-swap generalize scope-expand)
fi

for ev in "${EVALS[@]}"; do
  case "$ev" in
    rationale-swap|generalize|scope-expand) ;;
    *) echo "Unsupported by this legacy runner: $ev; use skill-creator fresh paired runs (see evals/README.md)." >&2; exit 2 ;;
  esac
done

# Map eval name -> numeric id from evals.json so the directory name carries the
# real eval_id. aggregate_benchmark.py parses `int(name.split("-")[1])` and
# silently falls back to enumeration order when that fails — which mislabels
# every eval (observed: eval_id 0 was generalize, 1 was language).
eval_id_of() { # $1 = eval name -> numeric id from evals.json
  python3 -c 'import json,sys
spec=json.load(open(sys.argv[1],encoding="utf-8"))
print(next((e["id"] for e in spec["evals"] if e["name"]==sys.argv[2]), ""))' \
    "$EVAL_DIR/evals.json" "$1"
}

# Frozen baseline ships per fixture (<fixture>/gate-WITHOUT.md). There is no
# shared default: the two evals that used one were removed (references-fresh and
# language belonged to skill-creator / Default Constraints, not Context Concise).

mapdir() { # $1 = eval name -> fixture dir
  case "$1" in
    scope-expand) echo "$EVAL_DIR/scope" ;;
    *)            echo "$EVAL_DIR/$1" ;;
  esac
}

for ev in "${EVALS[@]}"; do
  fx="$(mapdir "$ev")"
  eid="$(eval_id_of "$ev")"
  out="$BASE/eval-${eid}-$ev"
  rm -rf "$out"   # never let stale run-N dirs from a previous invocation aggregate in
  [ -d "$fx" ] || { echo "SKIP $ev: no fixture at $fx" >&2; continue; }
  mkdir -p "$out"
  # fixture inputs live once at eval level (shared, read-only)
  for f in prompt.txt task.md; do
    [ -f "$fx/$f" ] && cp "$fx/$f" "$out/$f"
  done
  for f in "$fx"/*.diff; do [ -f "$f" ] && cp "$f" "$out/"; done

  # WITH = live gate
  mkdir -p "$out/gate-WITH"
  cp "$SKILL_DIR/SKILL.md" "$out/gate-WITH/skill-gate-SKILL.md"
  # WITHOUT = frozen baseline (per-fixture if present, else shared)
  mkdir -p "$out/gate-WITHOUT"
  if [ -f "$fx/gate-WITHOUT.md" ]; then
    cp "$fx/gate-WITHOUT.md" "$out/gate-WITHOUT/skill-gate-SKILL.md"
  else
    echo "SKIP $ev: no frozen baseline at $fx/gate-WITHOUT.md" >&2; rm -rf "$out"; continue
  fi

  for arm in gate-WITH gate-WITHOUT; do
    for n in $(seq 1 "$RUNS"); do
      d="$out/$arm/run-$n"; mkdir -p "$d/outputs"
      FAILED=0
      cp "$out/prompt.txt" "$d/prompt.txt"
      for f in "$out"/*.diff "$out"/task.md; do [ -f "$f" ] && cp "$f" "$d/"; done
      cp "$out/$arm/skill-gate-SKILL.md" "$d/skill-gate-SKILL.md"
      attempt=1
      while :; do
        (
          cd "$d"
          perl -e 'alarm 900; exec @ARGV' pi \
            --no-skills --no-context-files --no-extensions --no-session --offline \
            --provider "$PROVIDER" --model "$MODEL" --thinking "$THINKING" \
            --print "$(cat prompt.txt)" > transcript.raw 2> run.err < /dev/null || true
        )
        perl -pe 's/\e\][^\a\e]*(?:\a|\\)//g' "$d/transcript.raw" > "$d/transcript.md" \
          || cp "$d/transcript.raw" "$d/transcript.md"
        [ "$(tr -d '[:space:]' < "$d/transcript.md" | wc -c | tr -d ' ')" -ge 50 ] && break
        if [ "$attempt" -ge 3 ]; then
          echo "FATAL: $ev/$arm/run-$n still empty after $attempt attempts — see $d/run.err" >&2
          exit 3
        fi
        echo "    retry $attempt for $ev/$arm/run-$n (empty launch; backoff 10s)" >&2
        attempt=$((attempt+1)); sleep 10
      done
      cp "$d/transcript.md" "$d/outputs/response.md"
      bytes=$(wc -c < "$d/transcript.md" | tr -d ' ')
      printf "  %-16s %-12s run-%s  %s bytes\n" "$ev" "$arm" "$n" "$bytes"
      # fail closed on an empty/whitespace transcript: a missing arm must never
      # be silently graded (an empty response would otherwise score 0 and look
      # like a baseline result).
      if [ "$bytes" -lt 50 ] || [ -z "$(tr -d '[:space:]' < "$d/transcript.md")" ]; then
        echo "FATAL: $ev/$arm/run-$n produced no usable transcript ($bytes bytes) — see $d/run.err" >&2
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
echo "  python -m scripts.aggregate_benchmark $BASE --skill-name skill-gate   # from the skill-creator dir"
echo "Grader must still read both transcripts personally — flags are a pre-filter."
echo
echo "NOTE: aggregate_benchmark.py hardcodes metadata.runs_per_configuration=3"
echo "      (its line ~271) regardless of the real run count. With EVAL_RUNS=1"
echo "      that field is WRONG — read run_summary, and treat stddev as"
echo "      meaningless at n=1. Use EVAL_RUNS=3 for a variance-bearing run."
