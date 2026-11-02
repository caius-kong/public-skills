#!/usr/bin/env python3
"""Grade planner-executor-pipeline eval runs into skill-creator's grading.json schema.

Per skill-creator's agents/grader.md, assertions that can be checked
programmatically SHOULD be scripted. This script is the EVIDENCE generator for
the discriminating assertions; a grader still reads both transcripts before
accepting a verdict — the mechanical result is a pre-filter, not the verdict.

Each assertion is a (positive, negative) pair where possible: a rule that fires
should show its marker AND not show the marker of the wrong outcome. That keeps
the check honest — a transcript that merely restates the prompt scores badly.
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path


def norm(t: str) -> str:
    return re.sub(r"\s+", " ", t)


def has(t: str, *pats: str) -> bool:
    return any(re.search(p, t, re.I | re.S) for p in pats)


# Negation markers. Markdown emphasis is stripped from the lookback window
# first (see _deemphasis), so "do **not** resend" reduces to "do not resend".
NEG_BEFORE = re.compile(
    r"(?:do(?:es)?\s+not|don't|did\s+not|never|no\b|without|not\s+triggered|"
    r"instead\s+of|rather\s+than|\u4e0d\u5f97|\u4e0d\u5e94|\u4e0d|\u672a|\u65e0\u9700|\u7981\u6b62|\u907f\u514d)"
    r"[^.;\u3002\uff1b]{0,40}$",
    re.I,
)


def _deemphasis(s: str) -> str:
    """Drop markdown emphasis so negation words are adjacent to their verb."""
    return re.sub(r"[*_`]", "", s)


def asserts_absence(t: str, *pats: str) -> bool:
    """True only if the text AFFIRMATIVELY performs the forbidden action.

    A naive `not has(word)` fails on negative assertions: a transcript that
    correctly writes "do not resend" or "the FIX_EXECUTE branch is not triggered"
    contains the word while committing no violation. Each match is checked for a
    governing negation immediately before it; matches inside quoted rule text
    ("...\u4e0d\u5f97\u53cd\u590d\u6d3e\u53d1\u7a7a\u4efb\u52a1\u3002"") are treated as reference, not action.
    """
    for pat in pats:
        for m in re.finditer(pat, t, re.I | re.S):
            pre = _deemphasis(t[max(0, m.start() - 90):m.start()])
            if NEG_BEFORE.search(pre):
                continue
            # quoted protocol text: the transcript quoting the rule it obeys.
            # An unclosed quote opened shortly before reads as reference, not act.
            if re.search(r"[\u300c\u201c\u300e\u300f\u300a\u300b\"'\u2018`][^\u300d\u201d\u300f\u300b\"'\u2019`]{0,160}$", pre):
                continue
            # hypothetical / explanatory framing, not a performed action
            if re.search(r"(would only be|would be|only be dispatched|if|若|则|否则|"
                         r"that would|顺带|这意味着|means)[^.;\u3002\uff1b]{0,60}$", pre, re.I):
                continue
            # quoted protocol text: an unclosed quote opened shortly before,
            # and the quoted passage reads as a rule (not the writer's own act)
            if re.search(r'[\u300c"\u201c\'`][^\u300d"\u201d\'`]{0,140}$', pre):
                continue
            return True
    return False



def check(eval_name: str, text: str) -> list[dict]:
    t = text

    if eval_name == "handoff-contract-shape":
        rejected = has(t, r"原样退回", r"return(ing)? (the handoff )?to PLAN", r"do(es)? not (proceed|accept)",
                       r"not satisfied", r"退回") \
                   and has(t, r"nodes", r"edges", r"shape", r"形状", r"映射", r"mapping")
        return [
            {
                "text": "Rejects or flags the node/edge-array `dag` as violating the required mapping shape, rather than accepting it",
                "passed": rejected,
                "evidence": "decision is a rejection AND the dag shape mismatch is named",
            },
            {
                "text": "States that a shape mismatch is returned to the stage as-is (原样退回), not normalised by the parent",
                "passed": has(t, r"原样退回", r"as-is", r"不得由父会话", r"forbidden normali", r"normaliz"),
                "evidence": "as-is return / no self-normalisation",
            },
            {
                # Positive reading of the correct disposition. A negation test on
                # "normalize" is untenable here: the correct answer *must* discuss
                # normalization to say it is banned ("do not normalize it",
                # "that would be 自行归一化"), so the word's presence is evidence
                # FOR the right behaviour, not against it.
                "text": "Returns the handoff to the stage for re-issuing rather than repairing it in place",
                "passed": has(t, r"(re-?dispatch|重新派发|重派|return[^.;。；]{0,30}(to )?(PLAN|stage))",
                              r"(missing-list|缺失清单|reject[^.;。；]{0,40}(重新|re-issue|resubmit))"),
                "evidence": "returns to the stage instead of self-repairing",
            },
            {
                # In this fixture the handoff is REJECTED, so "persist verbatim"
                # is the wrong thing to demand: the correct answer records the
                # rejected artifact without adopting it, while the wrong answer
                # (accept) does persist it. Demanding verbatim here would reward
                # acceptance. Assert the correct disposition instead.
                "text": "Records the rejected handoff without adopting its contents as the plan",
                "passed": has(t, r"(不|never|not|do(es)? not)[^.;。；]{0,40}(adopt|treat|persist)[^.;。；]{0,40}(contract|plan|truth|计划)",
                              r"reject[^.;。；]{0,80}(等同字段缺失|as field-missing|as-is|原样)",
                              r"(记录|record)[^.;。；]{0,60}(dispatch_failures|缺失|missing|reject)",
                              r"missing-list|缺失清单|re-dispatch"),
                "evidence": "rejected-but-recorded disposition",
            },
        ]

    if eval_name == "gate-authz-before-violation":
        return [
            {
                "text": "Checks `state.authorized_test_edits` BEFORE judging the test diff as a violation",
                "passed": has(t, r"authorized_test_edits", r"授权") and has(t, r"先查|first|before|再判|先.{0,10}授权"),
                "evidence": "looks for the authz-first ordering",
            },
            {
                "text": "Reaches PASS (authorised-and-recorded) rather than FIX_EXECUTE for the recorded test edit",
                "passed": has(t, r"\bPASS\b") and not has(t, r"(verdict|判定|裁决)\s*[:：]?\s*(is\s+)?FIX_EXECUTE"),
                "evidence": "verdict field",
            },
            {
                "text": "Records the authorised test modification in gate-evidence",
                "passed": has(t, r"gate-evidence", r"记录.{0,20}(已授权|授权)"),
                "evidence": "looks for the recording step",
            },
            {
                "text": "Does not treat an allocated/recorded test change as an unauthorised freeze break",
                "passed": not asserts_absence(t, r"(未授权|unauthoris|unauthoriz)[^.;。；]{0,40}(FIX_EXECUTE|violation)"),
                "evidence": "affirmative unauthorised-vs-FIX_EXECUTE reading, negation-aware",
            },
        ]

    if eval_name == "bounded-wait-terminal":
        return [
            {
                "text": "Treats an actually expired 24-hour interview request as a terminal outcome, not a tool-retry signal",
                "passed": has(t, r"(超时|timeout).{0,80}(合法|legitimate|预期|expected|终局|terminal|不是失败|not a failure|未决)",
                              r"(合法结束|legal end|预期结果|请求.{0,10}过期)"),
                "evidence": "actual request-expiry handling; prompt guarantees the full 24-hour request window elapsed",
            },
            {
                "text": "Does NOT retry or resend the expired request after the 24-hour wait",
                "passed": not asserts_absence(t, r"(重发|resend|retry|re-?ask|再次(发起|请求)|ask again)"),
                "evidence": "affirmative resend/retry, negation-aware",
            },
            {
                "text": "Does NOT emit progress/heartbeat messages while waiting",
                "passed": not asserts_absence(t, r"(progress_update|进度(类|消息)|heartbeat|空转)"),
                "evidence": "affirmative progress chatter, negation-aware",
            },
            {
                "text": "Records the unresolved decision in blocked_on_interview if the expired run returns normally",
                "passed": has(t, r"blocked_on_interview") and has(t, r"questions_count|未决|pending|unresolved"),
                "evidence": "normal expiry may return a blocked handoff; the run deadline or hard stop may instead produce no handoff",
            },
        ]

    if eval_name == "frozen-test-fix-route":
        wrong = re.search(r"Routing\s*[:：]?\s*`?FIX_EXECUTE"
                          r"|(verdict|判定|裁决)\s*[:：]?\s*`?FIX_EXECUTE", t, re.I)
        right = re.search(r"Routing\s*[:：]?\s*`?(REPLAN|HALTED)"
                          r"|(verdict|判定|裁决|去向)\s*[:：]?\s*`?(REPLAN|HALTED)", t, re.I)
        return [
            {
                "text": "Does NOT route an unauthorised test change to FIX_EXECUTE when the fix itself requires editing the test",
                "passed": not wrong and not asserts_absence(t, r"Routing\s*[:：]?\s*`?FIX_EXECUTE"),
                "evidence": f"affirmative FIX_EXECUTE route: {wrong.group(0)[:60] if wrong else 'none'}",
            },
            {
                "text": "Routes instead to REPLAN (contract defect) or HALTED (needs human ruling)",
                "passed": bool(right),
                "evidence": f"route: {right.group(0)[:60] if right else 'none'}",
            },
            {
                "text": "Explains that EXECUTE is forbidden from editing tests, hence FIX_EXECUTE has no legal action",
                "passed": has(t, r"(EXECUTE|执行).{0,80}(禁止|不得|不能|forbidden|无(权|法)).{0,30}(改|edit|modif).{0,15}(测试|test)",
                              r"FIX_EXECUTE.{0,120}(dead end|no legal|无合法|不得|不可|pointless)"),
                "evidence": "rationale for the reroute",
            },
            {
                "text": "Does not dispatch a repeated empty FIX_EXECUTE task",
                "passed": not asserts_absence(t, r"(反复派发|repeatedly dispatch|empty task|空任务)"),
                "evidence": "affirmative repeated-empty dispatch, negation-aware",
            },
        ]


    return []


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: grade.py <workspace-iteration-dir>", file=sys.stderr)
        return 2
    base = Path(sys.argv[1])
    eval_dirs = sorted(base.glob("eval-*"))
    if not eval_dirs:
        print(f"no eval-* dirs under {base}", file=sys.stderr)
        return 2

    total_all, passed_all = 0, 0
    for ed in eval_dirs:
        name = ed.name.split("-", 2)[2] if ed.name.count("-") >= 2 else ed.name
        for cfg in ("WITH", "WITHOUT"):
            for run in sorted((ed / cfg).glob("run-*")):
                tf = run / "transcript.md"
                if not tf.exists():
                    continue
                text = norm(tf.read_text(encoding="utf-8", errors="replace"))
                exps = check(name, text)
                if not exps:
                    continue
                npass = sum(1 for e in exps if e["passed"])
                summary = {
                    "passed": npass,
                    "failed": len(exps) - npass,
                    "total": len(exps),
                    "pass_rate": round(npass / len(exps), 3),
                }
                (run / "grading.json").write_text(
                    json.dumps({"expectations": exps, "summary": summary}, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                total_all += len(exps); passed_all += npass
                print(f"  {name:30s} {cfg:8s} {run.name}  {npass}/{len(exps)}")

    if total_all:
        print(f"\n  OVERALL {passed_all}/{total_all} = {passed_all/total_all:.0%}")
    print("\nNOTE: mechanical flags only. Read both transcripts before accepting any verdict.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())