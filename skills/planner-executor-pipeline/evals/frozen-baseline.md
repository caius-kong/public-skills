---
description: planner-executor-pipeline：Plan→Test Author→Execute→Gate→Conformance 纯 prompt 工作流（无代码依赖）。父会话编排分阶段 subagent，模型分配见阶段要点。
argument-hint: "[custom_prompt]"
---

# 架构

**状态唯一权威 = `handoffs/pipeline-state.json`**（gitignored；父会话每个事件后用固定命令写回、每次派发前重读——禁止凭对话记忆计数或推进）。

父会话（orchestrator）只做四件事：
1. 读 state 确定当前阶段，按「阶段要点 + Handoff 契约」组装阶段 task prompt（交接协议见下）
2. 按 dispatch 启动 subagent（cwd=目标仓库，agent/model/context=阶段要点指定）
3. 执行确定性 Gate（GATE 阶段无 subagent），证据落盘
4. 用户确认点：PlanHandoff 展示后 y/n 冻结、Merge y/n、HALTED 上报

计数器由 state 文件 owns；禁止跳步或无 handoff 依据的状态推进。

# 编排循环

```
读 state ─→ 组装 task prompt ─→ 启动 subagent ─→ 子 agent 返回 handoff JSON
    ↑                                                    │
    └── 校验 handoff → 原样落盘 → 写 state（下一阶段）←────┘
```

- state 文件形如 `{"stage","replan_round","cursor","tickets","attempts"}`；REPLAN 请求 → replan_round++（>3 → HALTED：保留全部 handoff/证据并上报用户，禁止继续）；Execute 单票失败满 3 次 attempts → 强制 REPLAN（计入 replan_round）。
- writer 链单写手串行：每个 dispatch 只启动一个子 agent；上票 commit 后才派下票。
- **交接协议（skill:handoff）**：阶段 task prompt 按其协议组装——紧凑、已有 artifact 引路径不复制内容、附该阶段 References（suggested skills）、无敏感信息。边界条款为固定措辞，组装时原样附上，不得改写：`受保护（不得写入）：${protected_paths}（本任务指定产出的 handoff artifact 除外，如 test-handoff/execute-handoff.json；plan-handoff.json 契约文件始终不可改写）`；TA/Execute 按阶段要点附加冻结条款。

# Pre-flight（父会话，一次性）

1. 未提交代码先 commit（用户 y/n）。
2. 固化 `BASE_SHA = git rev-parse HEAD`（禁止手抄 `--oneline` 前缀拼 SHA）。
3. 写初始 state 文件（stage=PLAN）。

# 阶段要点（task prompt 按交接协议组装，边界条款固定）

- **PLAN**（oracle @ gpt-5.6-sol，fresh，只读）：`/grill-me` → `/to-spec` → `/to-tickets`；brief 已含收敛问答则访谈精简。产出 PlanHandoff JSON；allowed_paths 覆盖任务合法变更的全部路径——含因契约变更需重生成的既有产物（渲染输出/golden 快照等），此类不入 protected_paths；supervisor 访谈载荷契约：每次 contact_supervisor 必须同时携带 message 与 interview（{"round":n,"questions":[...]}），只发 reason 的空调用即协议违规。
- **Test Author**（worker @ glm-5.3-flash:max，fresh）：red-first 黑盒验收测试：在任务最高外部 seam 上断言可观察行为（子进程 stdout/stderr/exit code、公开 API 返回值、落盘产物等），不 mock 被测对象获得绿；此刻必须红且红因与验收一致；与本契约变更无关的既有测试保持绿，编码被本契约取代的既有测试属 red set——在同一提交中一并更新，红因同上。只提交测试资产，实现文件不碰；提交后测试冻结（对 Execute 受保护）。TestHandoff 含 existing_tests_updated（被改既有测试及理由）。
- **Execute**（worker @ glm-5.3-flash:max，fresh）：按 DAG 拓扑序逐票派发；task prompt 必须含：该票验收逐条编号、`你只允许写：${ALLOWED}`（ALLOWED 用下述命令从 handoff 提取，禁止心算）、`测试红：携带完整输出重试；你最多 3 次尝试`、`不得改测试获得绿色`。逻辑失败重试或 REPLAN，不升级模型档位。产出 ExecuteHandoff。

  ```bash
  python3 -c "
  import json,re
  p=json.load(open('handoffs/plan-handoff.json'))
  t=[x for x in p['tickets'] if x['id']=='$TICKET_ID'][0]
  prot=[x.replace('**','').rstrip('/') for x in p['protected_paths']]
  print(','.join(f for f in t['files'] if not re.search(r'(^|/)(test|tests|__tests__|spec)(/|$)|\.test\.|\.spec\.',f) and not any(f.startswith(x) for x in prot)))"
  ```
- **Gate**（父会话，确定性，不可跳过）：test_command 退出码 0；`BASE..HEAD` 累计 diff ∈ allowed_paths；测试冻结机械核查：从 test-handoff.json 实取 commit/test_files，`git diff <TA_commit>..HEAD -- <test_files>` 必须为空（TA 提交后测试被改 → FIX_EXECUTE，不采信任何理由）；冻结强度核查（对照 BASE，逐 test 文件）：断言计数与用例数不降（干跑收集，如 pytest --collect-only -q）、无新增跳过/禁用标记（skip/xfail/skipif/todo 等）、无测试文件删除，test_command 全量执行，不得含用例选择/过滤参数（如 -k/--deselect/--ignore）——违反 → REPLAN（TA 侧缺陷，不采信理由）；handoff SHA 与 git log 核对；anti-gaming：测试必须黑盒断言（断言外部可观察行为，非实现细节/mock）+ 每条 acceptance ≥1 断言命中；BASE_SHA 用 `git rev-parse` 实取。产出 gate-evidence.json（含 BASE_SHA/HEAD/exit code/diff 文件清单/冻结核查结果/violation 判定）。
- **Conformance**（worker @ glm-5.3-flash:max，fresh，Gate 绿后）：仅 A 问（有没有硬编码/空壳骗测试）；输出 PASS/FIX_EXECUTE/REPLAN。
- **模型硬门槛**：kimi-k3 禁用于含 contact_supervisor 访谈的阶段；访谈臂 = gpt-5.6-sol（备选 glm-5.3:max）。worker 各阶段 need_decision 载荷缺失 → REPLAN fail-closed。

# Handoff 契约

handoff 以文件落盘 `handoffs/*.json`（gitignored）；子 agent 最终响应里的 handoff JSON 由父会话**原样落盘，不改写**；不传父会话 transcript。五 artifact：PlanHandoff/TestHandoff/ExecuteHandoff/GateEvidence/Verdict。

父会话校验（对照字段清单，逐项核对；字段缺失/类型错/acceptance 不可测 → 原样退回该阶段并附缺失清单）：
- PlanHandoff：`spec`、`tickets[{id,title,acceptance[],depends_on[],files[]}]`、`dag`、`allowed_paths`、`protected_paths`、`test_command`、`ambiguities`（可空）
- TestHandoff：`commit`、`test_files`、`red_summary`、`green_baseline`、`existing_tests_updated`（可空：被改既有测试 文件:函数 + 理由）
- ExecuteHandoff：`ticket`、`commit`、`test_output_summary`、`attempts`
- Verdict：`verdict`(PASS/FIX_EXECUTE/REPLAN)、`reasons`、`findings`

# References

- 交接协议：`~/.agents/skills/handoff/SKILL.md`
- `/grill-me`: `~/.agents/skills/grill-me/SKILL.md`（协议正文 `/grilling`）
- `/to-spec`: `~/.agents/skills/to-spec/SKILL.md`
- `/to-tickets`: `~/.agents/skills/to-tickets/SKILL.md`
- `/tdd`: `~/.agents/skills/tdd/SKILL.md`
- subagent model routing: `~/.pi/agent/npm/node_modules/pi-subagents/docs/models.md`
- workflow orchestration: `~/.pi/agent/npm/node_modules/pi-subagents/docs/workflows.md`

Additional instructions from the slash command invocation (custom prompt):

$@
