#!/usr/bin/env python3
"""Check a PlanHandoff spec.intent against its contract.

Exit 0 = 成立, 1 = 证实不一致, 2 = 无法判定 (崩溃绝不读成 PASS).

Every check exists because a delivery drifted in that exact way; each one has a
reverse fixture in evals/regression/t2/intent-canary-*.json. Checks that would
only ever pass are not in this file.
"""
import json, re, sys, pathlib

IMPL = [(r"\b[\w/]+\.py\b", "文件路径"), (r"->", "类型签名"), (r"\w\s*\(", "函数签名/调用"),
        (r"\bimport\b", "导入语句"), (r"\b\w+(?:\.\w+){2,}\b", "点分模块路径"),
        (r"\b(?:argparse|pytest|numpy|click|typer)\b", "库名")]
THIRD_PERSON = re.compile(r"^(?:用户(?:希望|想要|需要)|客户(?:希望|想要|需要)|业务(?:方)?(?:希望|要求))")
VAGUE = ["足够", "尽量", "适当", "友好", "健壮", "快速", "高效", "合理", "良好", "完善", "优化", "一定"]
DEFERRED = ["以后", "后续", "待定", "TBD", "再说", "暂不"]
GATES = {f"GATE#{n}" for n in range(1, 8)} | {"review-only"}


def check_intent(intent, ac_ids, new_symbols=(), require_accepted=False, problem_statement=""):
    errs, warns = [], []
    if not isinstance(intent, dict):
        return ["intent 不是对象"], warns

    unknown = set(intent) - {"status", "problem", "outcome", "constraints", "not_doing"}
    if unknown:
        errs.append(f"C0 未定义字段 {sorted(unknown)}（字段表之外的一律拒绝，否则就是自由发挥）")

    # C7 status 两态
    status = intent.get("status")
    if status not in ("draft", "accepted"):
        errs.append(f"C7 status={status!r} 不是 draft/accepted")
    elif require_accepted and status != "accepted":
        errs.append(f"C7 归档里的 intent 必须 accepted，实为 {status!r}")

    texts = {}
    for field in ("problem", "outcome"):
        value = intent.get(field)
        if not isinstance(value, str) or not value.strip():
            errs.append(f"C0 {field} 必须是非空字符串")
        else:
            texts[field] = value.strip()

    # C8 禁止开放问题字段（未决问题只能走访谈）
    if "open_questions" in intent and intent["open_questions"]:
        errs.append("C8 不允许 open_questions：未决问题必须走访谈并在冻结前答掉")

    # C1 无实现标识 / C6 无漂亮话 / C2 不引用本次新增标识符
    for field, text in texts.items():
        for pat, name in IMPL:
            for hit in re.findall(pat, text):
                errs.append(f"C1 {field} 含实现标识（{name}）{hit!r}")
        for word in VAGUE:
            if word in text:
                errs.append(f"C6 {field} 含无法验证的措辞 {word!r}")
        for sym in new_symbols:
            leaf = sym.rsplit(".", 1)[-1]
            hit = [x for x in (sym, leaf) if x and re.search(rf"(?<![\w-]){re.escape(x)}(?![\w-])", text)]
            if hit:
                errs.append(f"C2 {field} 引用了本次新增的标识符 {hit[0]!r}（问题/结果描述的是改动前后的世界，不能靠新名字叙述）")

    # C4 outcome 是结果不是清单
    if "outcome" in texts and "problem" in texts:
        outcome = texts["outcome"]
        if outcome == texts["problem"]:
            errs.append("C4 outcome 与 problem 同句（结果是改完之后的样子，问题是改之前的样子）")
        if len(re.findall(r"[。！？!?]", outcome)) > 2 or len(outcome) > 240:
            errs.append("C4 outcome 超过 2 句/240 字：它不是验收清单的复述")
        if re.search(r"AC\d+", outcome):
            errs.append("C4 outcome 里出现了验收编号：那份判据在验收里，不在这里复述")

    # C3 每条约束都指得出强制者
    cons = intent.get("constraints")
    if not isinstance(cons, list) or not cons:
        errs.append("C0 constraints 必须是非空列表")
        cons = []
    for i, c in enumerate(cons, 1):
        if not isinstance(c, dict) or not isinstance(c.get("text"), str) or not c["text"].strip():
            errs.append(f"C0 constraints[{i}] 必须是 {{text, enforced_by}}")
            continue
        for pat, name in IMPL:
            for hit in re.findall(pat, c["text"]):
                errs.append(f"C1 constraints[{i}] 含实现标识（{name}）{hit!r}")
        for word in VAGUE:
            if word in c["text"]:
                errs.append(f"C6 constraints[{i}] 含无法验证的措辞 {word!r}")
        refs = c.get("enforced_by") or []
        refs = [refs] if isinstance(refs, str) else refs
        if not refs:
            errs.append(f"C3 constraints[{i}] 没有 enforced_by：无强制者的句子是承诺不是约束")
        for r in refs:
            if r in GATES:
                continue
            if r not in ac_ids:
                errs.append(f"C3 constraints[{i}] 引用了不存在的强制者 {r!r}")

    # C5 not_doing 是"明确不做"，不是"以后再说"
    nd = intent.get("not_doing", [])
    if not isinstance(nd, list):
        errs.append("C5 not_doing 必须是列表（可为空）")
        nd = []
    for i, item in enumerate(nd, 1):
        if not isinstance(item, str) or not item.strip():
            errs.append(f"C5 not_doing[{i}] 必须是非空字符串")
            continue
        if any(w in item for w in DEFERRED):
            errs.append(f"C5 not_doing[{i}] 是未决问题不是排除项：{item[:40]!r}")
        if any(item.strip() == (c.get("text") or "").strip() for c in cons if isinstance(c, dict)):
            errs.append(f"C5 not_doing[{i}] 与某条约束重复：同一句话不能既是要守的又是要排除的")

    # C9 problem 是 problem_statement 的首句（派生而非另写，否则两处各写一版）
    ps = (problem_statement or "").strip()
    if ps and "problem" in texts:
        first = re.split(r"[。！？!?]", ps)[0].strip()
        if first and not texts["problem"].startswith(first[:20]):
            errs.append("C9 problem 不是 problem_statement 的首句：它必须派生自那里，不能另写一版")

    # 语气：中立提示，不阻断（真实性只有人类能判）
    if "problem" in texts and THIRD_PERSON.match(texts["problem"]):
        warns.append(f"problem 以第三人称开头（{THIRD_PERSON.match(texts['problem']).group(0)}…）：用第一人称更像发起人原话")
    return errs, warns


def main(argv):
    if len(argv) < 2:
        print("用法: intent-check.py <plan-handoff.json> [--intent-file intent.json] [--require-accepted]"); return 2
    plan_path = pathlib.Path(argv[1])
    try:
        plan = json.loads(plan_path.read_text())
    except Exception as e:
        print(f"CANNOT JUDGE: 读不到 plan-handoff: {e}"); return 2
    if "--intent-file" in argv:
        intent = json.loads(pathlib.Path(argv[argv.index("--intent-file") + 1]).read_text())
    else:
        intent = (plan.get("spec") or {}).get("intent")
        if intent is None:
            print("CANNOT JUDGE: plan-handoff 里没有 spec.intent"); return 2
    # Same rule as gate.py: take the leading identifier, whatever separator follows.
    # Splitting on a colon here made "AC1 <text>" (no colon) parse to the whole
    # string, so every other reference looked unknown -- a false FAIL on a
    # perfectly valid handoff.
    ac_ids = {m.group(1) for t in plan.get("tickets", []) for a in t.get("acceptance", [])
              if (m := re.match(r"^\s*(AC\d+)", a))}
    # Only the declared list. Deriving symbols from the ticket's file paths made
    # README.md into a forbidden word on a delivery whose whole point was a
    # README example -- a false FAIL, which teaches the reader to ignore FAILs.
    if "new_symbols" not in plan:
        print("FAIL:\n  - C0 new_symbols 缺失（C2 无法执行：不声明新增名字就无法判断 intent 是否在描述设计）")
        return 1
    symbols = set(plan["new_symbols"])
    errs, warns = check_intent(intent, ac_ids, symbols, "--require-accepted" in argv,
                               (plan.get("spec") or {}).get("problem_statement", ""))
    for w in warns:
        print(f"WARN: {w}")
    if errs:
        print("FAIL:\n  - " + "\n  - ".join(errs)); return 1
    print(f"PASS: intent 合法（{len(intent.get('constraints') or [])} 条约束全部指得出强制者）"); return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except Exception as e:
        print(f"CANNOT JUDGE: 检查器自身异常 {e}"); sys.exit(2)
