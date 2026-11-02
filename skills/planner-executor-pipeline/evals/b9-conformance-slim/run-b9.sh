#!/usr/bin/env bash
# b9 conformance-slim eval — validates deleting「低量」from the Conformance
# stage line in planner-executor-pipeline.md (audit finding #3: redundant
# with 仅 A 问, vague).
#
# Behavioral surface = parent-side assembly only. Arms differ ONLY in the
# Conformance line:
#   WITHOUT arm = git HEAD 4d31b4e (低量 present, frozen baseline)
#   WITH arm    = working tree  (低量 deleted, uncommitted; rollback=checkout)
#
# Bar (defined before run): eval-log.md "b9 … bar 先定".
#   ① WITH arms assemble operative-complete Conformance task prompts
#     (A question + tri-state verdict + artifact path refs)
#   ② no WITHOUT arm translates 低量 into concrete operative instruction
#     missing from WITH arms → else FAIL → checkout + honest report
#   ③ inert-mention-only deltas → PASS, recorded honestly
# Mechanical checks are a pre-filter; the grader reads all four responses
# personally.
#
# Env overrides: EVAL_RUN_ROOT, EVAL_PROVIDER (default trendmicro),
# EVAL_MODEL (default glm-5.3-flash), EVAL_THINKING (default high),
# EVAL_B7 (fixture source, default /tmp/pipeline-eval-b7).
set -euo pipefail

EVAL_DIR="$(cd "$(dirname "$0")" && pwd -P)"
PI_REPO="$HOME/.pi"
# NOTE (v1.0): the prompt template this script read was deleted when the
# pipeline migrated to a skill. Historical experiment artifact — point
# PROMPT_PATH at the skill's SKILL.md to re-run:
#   PROMPT_PATH="skills/pi/planner-executor-pipeline/SKILL.md" (relative to $PI_REPO)
PROMPT_PATH="${PROMPT_PATH:-agent/prompts/planner-executor-pipeline.md}"
STAMP="$(date +%Y%m%d-%H%M%S)"
RUN_ROOT="${EVAL_RUN_ROOT:-/tmp/pipeline-eval-b9}"
RUN_DIR="$RUN_ROOT/$STAMP"
PROVIDER="${EVAL_PROVIDER:-trendmicro}"
MODEL="${EVAL_MODEL:-glm-5.3-flash}"
THINKING="${EVAL_THINKING:-high}"
B7="${EVAL_B7:-/tmp/pipeline-eval-b7}"

# Prereq 1: working tree must differ from HEAD by the 低量 deletion ONLY.
# (diff exits 1 when files differ — capture output first, don't test its status)
diff_out="$(diff <(git -C "$PI_REPO" show "HEAD:$PROMPT_PATH") \
                <(cat "$PI_REPO/$PROMPT_PATH") || true)"
echo "$diff_out" | grep -q '低量' || {
  echo "FATAL: working tree vs HEAD diff is not the 低量 deletion — fix first." >&2
  exit 2
}
# Prereq 2: fixture source must exist with handoffs.
[ -d "$B7/handoffs" ] || { echo "FATAL: $B7/handoffs missing." >&2; exit 2; }

mkdir -p "$RUN_DIR"
git -C "$PI_REPO" show "HEAD:$PROMPT_PATH" > "$RUN_DIR/base-prompt.txt"
cp "$PI_REPO/$PROMPT_PATH" "$RUN_DIR/rev-prompt.txt"

make_arm() { # $1 = arm name, $2 = prompt source file
  local dir="$RUN_DIR/$1"
  rm -rf "$dir"; mkdir -p "$dir"
  cp -R "$B7" "$dir/repo"
  # fixture state: Gate green, Conformance pending (no verdict yet)
  python3 - "$dir/repo/handoffs/pipeline-state.json" <<'PY'
import json,sys
p=sys.argv[1]; s=json.load(open(p)); s["stage"]="CONFORMANCE"
json.dump(s,open(p,"w"),ensure_ascii=False,indent=2)
PY
  rm -f "$dir/repo/handoffs/verdict.json"
  {
    cat <<'HEAD'
你是 planner-executor-pipeline 管线的父会话 orchestrator。下面是你本次会话加载的管线 prompt 完整原文，你的所有行为以它为准：

<<<PIPELINE_PROMPT
HEAD
    cat "$2"
    cat <<'TAIL'

PIPELINE_PROMPT

当前状态：目标仓库在本目录下 repo/（路径见下），git 干净，HEAD 为 Execute 提交；确定性 Gate 已执行且全部核查通过（证据 handoffs/gate-evidence.json）；handoffs/pipeline-state.json 的 stage 为 CONFORMANCE。仓库绝对路径：
TAIL
    echo "$dir/repo"
    cat <<'TAIL'

你的任务：按管线 prompt 的 Conformance 阶段要点与交接协议，写出你即将派发给 Conformance worker 的完整 task prompt 原文。只输出该 task prompt 的文本本身；不要实际派发任何 subagent，不要执行其他阶段，不要创建或修改任何文件。
TAIL
  } > "$dir/prompt.txt"
}

run_arm() { # $1 = arm dir
  (
    cd "$1"
    perl -e 'alarm 900; exec @ARGV' pi \
      --no-session --offline --no-extensions --no-skills \
      --provider "$PROVIDER" --model "$MODEL" --thinking "$THINKING" \
      --print "$(cat prompt.txt)" \
      > response.raw 2> run.err < /dev/null || true
  )
  perl -pe 's/\e\][^\a\e]*(?:\a|\e\\)//g' "$1/response.raw" > "$1/response.md" \
    || cp "$1/response.raw" "$1/response.md"
}

# Pre-filter ①: WITH arms must assemble operative-complete prompts
# (A-question keywords + tri-state verdict contract).
mech_with() { # $1 = arm dir
  local f="$1/response.md"
  if [ ! -s "$f" ]; then echo "ASSEMBLY=EMPTY"; return; fi
  if grep -qE '硬编码|空壳' "$f" && grep -q 'REPLAN' "$f" \
     && grep -q 'FIX_EXECUTE' "$f"; then
    echo "ASSEMBLY=OK"
  else
    echo "ASSEMBLY=INCOMPLETE"
  fi
}
# Pre-filter ②: does a WITHOUT arm translate 低量 into operative clauses?
# (report-only; grader judges operative vs inert personally)
mech_without() { # $1 = arm dir
  local f="$1/response.md" hits=""
  [ -s "$f" ] || { echo "EFFORT-CLAUSE=EMPTY"; return; }
  for kw in 低量 少量 简洁 简短 精炼 budget effort 控制在 不要展开; do
    grep -q "$kw" "$f" && hits="$hits $kw"
  done
  echo "EFFORT-CLAUSE:${hits:-none}"
}

echo "== b9 conformance-slim eval $STAMP (provider=$PROVIDER model=$MODEL thinking=$THINKING) =="

for i in 1 2; do
  make_arm "without-$i" "$RUN_DIR/base-prompt.txt"
  echo "-- running Arm WITHOUT-$i (frozen baseline, 低量 present) --"
  run_arm "$RUN_DIR/without-$i"
done
for i in 1 2; do
  make_arm "with-$i" "$RUN_DIR/rev-prompt.txt"
  echo "-- running Arm WITH-$i (revised, 低量 deleted) --"
  run_arm "$RUN_DIR/with-$i"
done

echo
for i in 1 2; do
  echo "Arm WITHOUT-$i mech: $(mech_without "$RUN_DIR/without-$i") | assembly: $(mech_with "$RUN_DIR/without-$i")"
done
for i in 1 2; do
  echo "Arm WITH-$i    mech: $(mech_with "$RUN_DIR/with-$i")"
done

echo
echo "Artifacts: $RUN_DIR"
echo "Grader: read all four response.md personally per eval-log b9 bar."
