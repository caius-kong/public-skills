---
description: planner-executor-pipeline v2：确定性状态机驱动。机器 owns 转移/计数器/路由/task prompt；父会话只调用机器、启动阶段 subagent、执行确定性 Gate、等待用户确认。
argument-hint: "[custom_prompt]"
---

# 架构

**状态机代码是唯一契约权威**：`~/.pi/evals/planner-pipeline/machine/`（run.ts 为唯一入口）。

父会话（orchestrator）主要负责四件事：
1. 调用机器拿 dispatch：`node <machine>/run.ts init` / `run.ts event < event.json`
2. 按 dispatch 启动 subagent（cwd=目标仓库，task=dispatch.taskPrompt，agent/model/context=dispatch.deployment）
3. 执行确定性 Gate（GATE 阶段无 subagent），证据落盘后回报机器
4. 用户确认点：PlanHandoff 展示后 y/n 冻结、Merge y/n、HALTED 上报

计数器（replan_round ≤3、per-ticket attempts ≤3）由机器 owns；禁止父会话手模拟任何状态转移或改写机器生成的 task prompt 的边界条款。

# 编排循环

```
run.ts init ─→ dispatch ─→ 启动 subagent ─→ 子 agent 返回 handoff JSON
    ↑                                                │
    └── run.ts event < event.json ←─ 父会话写事件文件 ←┘
```

- 事件文件 = `{"type": "...", ...}`，类型与载荷见 machine.ts `Event`（PLAN_DONE/TESTS_FROZEN/TICKET_DONE 携带对应 handoff 对象）；zod 校验失败返回 error（含字段级 detail），修复后重发同一事件。
- GATE 阶段机器返回 `gateChecklist`：父会话逐条执行（无 LLM），写 `handoffs/gate-evidence.json`，再发 `GATE_PASS`（附证据）或 `GATE_FAIL`。
- 机器返回 `HALTED` = fail-closed 终态：保留全部 handoff/证据并上报用户，禁止继续。
- writer 链单写手串行：每个 dispatch 只启动一个子 agent；上票 commit 后才派下票。

# Pre-flight（父会话，一次性）

1. 未提交代码先 commit（用户 y/n）。
2. 固化 `BASE_SHA = git rev-parse HEAD`（禁止手抄 `--oneline` 前缀拼 SHA）。
3. `run.ts init` 拿 PLAN dispatch；部署适配器须将 PLAN 作为 direct async single-agent 启动，配置 `timeoutMs: 86400000`，并加载 PLAN 专属访谈 timeout extension。

# 阶段要点（细节以机器生成的 task prompt 为准）

- **PLAN**（plan @ configured PLAN model，fresh，只读，direct async single-agent，24h run timeout；native interview request 24h）：同一 PLAN 内澄清→spec→tickets/DAG；用户非最终回复或暂离时安静等待，不终止/重派。产出 PlanHandoff JSON（结构 = schemas.ts PlanHandoffSchema）。访谈请求真实过期或用户取消时结束等待；hard kill 可能没有 handoff。PLAN run timeout/async launch 由部署层 dispatch 提供；访谈窗口由 PLAN 专属 extension 提供。
- **Test Author**（worker @ kimi-k3:high，fresh）：red-first 黑盒验收测试；提交后测试资产冻结（对 Execute 受保护）；TestHandoff。
- **Execute**（worker @ deepseek-v4-flash-0731-gmi-ray:high，fresh，免费）：机器按 DAG 拓扑序逐票派发；只写该票 `files`；逻辑失败不升级付费模型。
- **Gate**（父会话，确定性，不可跳过）：test_command 退出码 0；`BASE..HEAD` 累计 diff ∈ allowed_paths；测试 commit 后 test/** 升级 protected；handoff SHA 与 git log 核对；anti-gaming：测试必须黑盒子进程断言 + 每条 acceptance ≥1 断言命中；BASE_SHA 用 `git rev-parse` 实取。
- **Conformance**（worker @ deepseek free，fresh，Gate 绿后低量）：仅 A 问（硬编码/空壳骗测试）；输出 PASS/FIX_EXECUTE/REPLAN。
- **模型硬门槛**：kimi-k3 禁用于含 contact_supervisor 访谈的阶段；访谈臂 = gpt-5.6-sol（备选 deepseek free）。worker 各阶段 need_decision 载荷缺失 → REPLAN fail-closed。

# Handoff 契约

结构唯一权威 = schemas.ts 的 zod schema（PlanHandoff/TestHandoff/ExecuteHandoff/GateEvidence/Verdict）。handoff 以文件落盘 `handoffs/*.json`（gitignored）+ 事件 JSON 双份存在；不传父会话 transcript。子 agent 最终响应里的 handoff JSON 由父会话原样落盘，不改写。

# References

- 状态机与 CLI：`~/.pi/evals/planner-pipeline/machine/`（run.ts 为唯一入口）
- `/tdd`: `~/.agents/skills/tdd/SKILL.md`
- subagent model routing: `~/.pi/agent/npm/node_modules/pi-subagents/docs/models.md`
- workflow orchestration: `~/.pi/agent/npm/node_modules/pi-subagents/docs/workflows.md`

Additional instructions from the slash command invocation (custom prompt):

$@
