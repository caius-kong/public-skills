---
description: 实验臂 A 工件（Round 4）：机制验证胜出但骨架被用户否决——非生产候选，仅作实验记录；execute-handoff 行已补。
argument-hint: "[custom_prompt]"
---

# 架构（纯 prompt 模式）

父会话 = 唯一 orchestrator：维护状态文件、按模板生成阶段 task prompt（原样启动子 agent，不改写边界条款）、执行确定性 Gate、处理用户确认点（PlanHandoff 冻结 y/n、Merge y/n、HALTED 上报）。

**状态纪律**：全部状态落盘 `handoffs/pipeline-state.json`（gitignored），每个事件后用 bash 写回、每次派发前重读——禁止凭对话记忆计数或推进。

初始 state：
```json
{"stage":"PLAN","replan_round":0,"cursor":0,"tickets":[],"attempts":{}}
```

# 转移表（唯一合法路径，禁止跳步）

```
PLAN ──PlanHandoff 校验通过──→ TEST_AUTHOR ──红证据提交──→ EXECUTE(cursor=0)
EXECUTE ──单票 commit──→ cursor++ ──cursor==len(tickets)──→ GATE ──绿──→ CONFORMANCE ──PASS──→ MERGE_WAIT
任意阶段 REPLAN 请求 ──→ replan_round++ ──>3──→ HALTED（保留全部 handoff/证据，上报用户，禁止继续）
Execute 单票失败满 3 次 attempts ──→ 强制 REPLAN（计入 replan_round）
```

# Handoff 校验（父会话对照字段清单，LLM 逐项核对）

- PlanHandoff：`spec`、`tickets[{id,title,acceptance[],depends_on[],files[]}]`、`dag`、`allowed_paths`、`protected_paths`、`test_command`、`ambiguities`——必填非空（ambiguities 可空）；acceptance 逐条可测（测试意图+断言+边界），写不出 → 该票退回 Plan
- TestHandoff：`commit`、`test_files`、`red_summary`、`green_baseline`
- ExecuteHandoff：`ticket`、`commit`、`test_output_summary`、`attempts`
- 字段缺失/类型错 → 原样退回该阶段（REPLAN，附缺失清单）

# 阶段模板（${...} 从 handoff JSON 用 python3/jq 提取填充，禁止手抄；填充后原样作为 task）

**通用尾部（追加到每个模板末尾）**：
```
受保护（不得写入）：.git/**, .gitignore, brief.md, package.json, handoffs/**（本模板另有声明以声明为准）。
需求歧义/测试与验收矛盾/需改受保护路径：立即停止返回 REPLAN 及证据，不得自行改契约。无文件修改不得返回成功总结。
最终响应附：commit SHA（若有写入）与关键命令输出摘要。
```

**PLAN**（oracle @ trendmicro/gpt-5.6-sol，fresh，只读）：
```
你是 planner-executor-pipeline 的 Plan 阶段。工作目录是目标仓库（launch 时给定 cwd）。
阶段内部 workflow：/grill-me → /to-spec → /to-tickets；brief 已含收敛问答则访谈精简，有未决歧义按协议访谈。
References（先 read 再按协议）：/grill-me ~/.agents/skills/grill-me/SKILL.md；/grilling ~/.agents/skills/grilling/SKILL.md；/to-spec ~/.agents/skills/to-spec/SKILL.md；/to-tickets ~/.agents/skills/to-tickets/SKILL.md
输入：read brief.md。
产出 PlanHandoff（最终响应一个 ```json 块）：{ "spec", "tickets": [{ "id", "title", "acceptance": string[], "depends_on": string[], "files": string[] }], "dag", "allowed_paths", "protected_paths", "test_command", "ambiguities" }；acceptance 必须可测，写不出并入 ambiguities。
supervisor 访谈载荷契约（模型硬门槛）：每次 contact_supervisor 必须同时携带 message（本轮全部 frontier 问题原文）与 interview（{"round":n,"questions":[...]}）；只发 reason 的空调用视为协议违规。
边界：全程只读（bash 仅限只读用法）；不得虚构用户未给出的决定。
```

**TEST_AUTHOR**（worker @ trendmicro/kimi-k3:high，fresh）：
```
你是 Test Author 阶段（唯一 writer，当前仅你写测试资产）。
输入：父会话已把 PlanHandoff 落盘为 handoffs/plan-handoff.json，先 read 它。
测试协议（References）：/tdd ~/.agents/skills/tdd/SKILL.md
Tickets：${每票一行：id 标题｜acceptance 分号连接}
要求：
1. 为每个 ticket 创建 red-first 验收测试（黑盒：真实子进程执行，断言 stdout/stderr/exit code，不 mock 内部）。此刻必须红且红因与验收一致；既有测试保持绿。
2. 运行 `${test_command}` 记录 red 证据。
3. 只提交测试文件；实现文件、package.json、brief.md 一律不碰。
4. 写 handoffs/test-handoff.json：{ "commit", "test_files", "red_summary", "green_baseline" }。
受保护（不得写入）：${protected_paths} 及 bin/**, src/**（以 PlanHandoff 为准，测试文件除外）。
```

**EXECUTE**（worker @ trendmicro/deepseek-v4-flash-0731-gmi-ray:high，fresh；逐票派发，单写手串行）：
```
你是 Execute 阶段（唯一 writer），只实现 ticket ${TICKET_ID}：${TICKET_TITLE}。
输入：read handoffs/plan-handoff.json（spec/验收）、handoffs/test-handoff.json（测试已冻结，commit 见其中）。
验收条件（逐条满足）：
${该票 acceptance 逐条编号}
边界：
- 你只允许写：${ALLOWED}；其余（含 test/**——测试已冻结、package.json、brief.md、handoffs/）全部受保护
- 运行 `${test_command}`：本票相关测试转绿、全量无回归后 git commit（message 以 feat(${TICKET_ID}): 开头）
- 测试红：携带完整输出重试；你最多 3 次尝试
```
写 handoffs/execute-handoff.json：{ "ticket": "${TICKET_ID}", "commit", "test_output_summary", "attempts", "open_issues": [] }。
ALLOWED 计算约定（父会话执行，禁止心算）：
```bash
python3 -c "
import json,re
p=json.load(open('handoffs/plan-handoff.json'))
t=[x for x in p['tickets'] if x['id']=='$TICKET_ID'][0]
prot=[x.replace('**','').rstrip('/') for x in p['protected_paths']]
print(','.join(f for f in t['files'] if not re.search(r'(^|/)(test|tests|__tests__|spec)(/|$)|\.test\.|\.spec\.',f) and not any(f.startswith(x) for x in prot)))"
```

**CONFORMANCE**（worker @ trendmicro/deepseek-v4-flash-0731-gmi-ray:high，fresh，Gate 绿后低量，只读）：
```
你是 Conformance 阶段（Gate 已全绿后的低量语义审查，仅 A 问）。只读，不写文件。
仅依据固定输入：handoffs/{plan,test,execute,gate-evidence}.json + git diff ${BASE_SHA}..HEAD + 实际源码。
只回答一个问题（A 问）：有没有硬编码/空壳骗测试？（为通过测试特判输入、伪造输出、检测测试环境走捷径、mock 内部实现）
输出（严格此格式）：
## Review
- Correct: <有证据的正确点>
- Finding: <P0/P1/P2 + 位置 + 证据 + 最小修复，若无则不写>
## Verdict
```json
{ "verdict": "PASS" | "FIX_EXECUTE" | "REPLAN", "reasons": string[], "findings": string[] }
```
```

# Pre-flight（一次性）

1. 未提交代码先 commit（用户 y/n）。
2. `BASE_SHA = git rev-parse HEAD`（禁止手抄 `--oneline` 前缀）。
3. 写初始 state 文件。

# Gate（父会话确定性执行，不可跳过、不可委托）

逐条全过才算绿，fail-closed：
1. `npm test`（或 test_command）退出码 0（超时/跳过/报告缺失均算失败）。
2. `git diff --name-only ${BASE_SHA}..HEAD` 每个文件 ∈ allowed_paths；测试 commit 后 test/** 升级 protected（Execute 不得触碰）。
3. handoffs/{test,execute}-handoff.json 的 commit 与 `git log` 一致（`git merge-base --is-ancestor`）。
4. anti-gaming：测试文件必须黑盒子进程断言（grep 排除 mock 内部模块）；每条 acceptance ≥1 断言命中。
5. 证据落盘 handoffs/gate-evidence.json（BASE_SHA 用 `git rev-parse` 实取）。

# 模型硬门槛

kimi-k3 禁用于含 contact_supervisor 访谈的阶段（载荷丢失缺陷，与通用能力无关）；访谈臂 = gpt-5.6-sol（备选 deepseek free）。worker 各阶段 need_decision 升级载荷缺失 → REPLAN fail-closed。

# References

- eval 日志与未测路径：`~/.pi/evals/planner-pipeline/eval-log.md`
- `/grill-me`: `~/.agents/skills/grill-me/SKILL.md`（协议正文 `/grilling`）
- `/to-spec`: `~/.agents/skills/to-spec/SKILL.md`
- `/to-tickets`: `~/.agents/skills/to-tickets/SKILL.md`
- `/tdd`: `~/.agents/skills/tdd/SKILL.md`
- subagent model routing: `~/.pi/agent/npm/node_modules/pi-subagents/docs/models.md`
- workflow orchestration: `~/.pi/agent/npm/node_modules/pi-subagents/docs/workflows.md`

Additional instructions from the slash command invocation (custom prompt):

$@
