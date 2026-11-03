---
name: planner-executor-pipeline
description: Plan→Test Author→Execute→Gate→Conformance staged pipeline for turning a goal into shipped, verified code. Use when the user wants a goal planned and implemented end-to-end with contract handoffs between stages, wants an auditable multi-stage agent workflow (PLAN / TEST_AUTHOR / EXECUTE / GATE / CONFORMANCE), or asks for /planner-executor-pipeline; also use when discussing or modifying this pipeline's protocol.
---

# planner-executor-pipeline

A prompt-driven workflow: the parent orchestrates stages and passes contract artifacts between subagents. The stage graph and state machine remain instructions; the platform adapter may load a narrowly scoped extension when native supervisor timing needs a per-agent override.

**Scope note:** §一–§二 and the artifact contract are portable protocol. Node dispatch is stated in the portable `Agent(...)` call contract; the concrete realization — which named agent, how the child is launched, how the interview channel and the read-only tool surface are enforced — lives in `references/pi-adapter.md` (pi) and is replaceable. The core carries no platform agent or model names: models live in `config.json` / `config.template.json`, reached through `@node` symbols.

| Load on demand | When |
|---|---|
| `references/artifacts.md` | Assembling or validating any handoff, or running GATE checks |
| `references/pi-adapter.md` | Dispatching on pi (named agents, launch parameters, interview channel, model verification), or porting to another platform |
| `config.json` / `config.template.json` | Resolving a `@node` model symbol, or changing any model/thinking |

# 一、工作流状态机

## Preflight

本 skill 编排的每个外部 skill 都按已安装路径 read 使用；仓库里不放任何副本。

- `grilling`: `~/.agents/skills/grilling/SKILL.md`
  - If missing: `npx skills add mattpocock/skills --skill grilling -g -y`
- `to-spec`: `~/.agents/skills/to-spec/SKILL.md`
  - If missing: `npx skills add mattpocock/skills --skill to-spec -g -y`
- `to-tickets`: `~/.agents/skills/to-tickets/SKILL.md`
  - If missing: `npx skills add mattpocock/skills --skill to-tickets -g -y`
- `tdd`: `~/.agents/skills/tdd/SKILL.md`
  - If missing: `npx skills add mattpocock/skills --skill tdd -g -y`
- `research`: `~/.agents/skills/research/SKILL.md`
  - If missing: `npx skills add mattpocock/skills --skill research -g -y`
- `code-review`: `~/.agents/skills/code-review/SKILL.md`
  - If missing: `npx skills add mattpocock/skills --skill code-review -g -y`

路径由仓库根的 `run-evals.sh` 机械校验；缺任何一个，run 之前就失败，不会跑到一半才发现。

## 节点序

```
EVIDENCE? ─→ PLAN ─→ TEST_AUTHOR ─→ EXECUTE(逐票) ─→ GATE ─→ CONFORMANCE
    ↑           │                                              │
    └───────────┘ needs_research 回路                  FIX_EXECUTE / REPLAN 回路
```

- `EVIDENCE?` 为可选节点：仅当 PLAN 输出 `needs_research`，或 pre-flight 判定既有预研不足以支撑规划时进入。
- `EXECUTE` 按 DAG 拓扑序逐票循环；单票不是状态机节点，是带计数的循环体。

## 状态权威

**唯一权威 = `handoffs/pipeline-state.json`**（gitignored）。父会话每个事件后用固定命令写回、每次派发前重读——**禁止凭对话记忆计数或推进**。计数器由 state 文件 owns，禁止跳步或无 handoff 依据的状态推进。

state 为**封闭字段清单**（不得省略；新增字段须同时更新此处与校验规则）：

```json
{
  "stage": "EVIDENCE|PLAN|TEST_AUTHOR|EXECUTE|GATE|CONFORMANCE|HALTED",
  "replan_round": 0,
  "research_round": 0,
  "plan_revision_round": 0,
  "cursor": [],
  "tickets": [],
  "attempts": {},
  "dispatch_failures": {},
  "interview_log": [],
  "base_sha": "",
  "brief_path": "",
  "authorized_test_edits": [],
  "orchestrator_commits": []
}
```

- `attempts` **按票累计**（`{ticket_id: n}`），**仅计子 agent 产出失败**（测试红/验收未过）——不因 infra 抖动而增加。
- `dispatch_failures` **按阶段累计**（`{stage: n}`），计派发错误返回、handoff 校验退回等 infra/契约失败。**同一事件只计一个计数器**：产出失败 → `attempts`；infra/校验失败 → `dispatch_failures`。
- **上限优先级**：多个计数器同时触顶时取更终局者（HALTED > REPLAN）。
- Keep the existing `interview_log` as `{question, answer}` pairs. After each user reply, append the exact question and verbatim reply, including explanations and partial answers; PLAN distinguishes discussion from settled decisions. A pending unanswered request remains in the live native channel, not as a half-filled pair. Ignore a legacy `interview_round` field and drop it on the next state write; it no longer limits interviews. `base_sha` is fixed during pre-flight; `brief_path` points to the brief.
- `authorized_test_edits`：经父会话裁决授权修改冻结测试的记录，条目 `{file, commit, reason, authorized_at}`。**裁决即记录**（授权只在对话里 = 无授权）；GATE 判定测试冻结时**先查此记录**。
- `orchestrator_commits`：父会话自身提交（非任何 ticket 产出）的 `{commit, files, reason}`——用于 GATE 区分「生命周期提交」与「越界实现」。
- **恢复范围**：阶段 handoff 完成后，仅凭 state + `handoffs/` 恢复；活跃访谈中的未答请求由原 PLAN run 与 native channel 持有，不保证 hard stop 时生成 handoff。

## 转换与守卫

每个箭头（状态推进）必须同时满足才允许：

1. 该阶段 handoff 已产出并通过字段校验（见 `references/artifacts.md`）；
2. handoff 与 state 字段一致（tickets/attempts/cursor 对得上）；
3. 该阶段的**质量验收**通过（见「跨节点规则」）——质量未满足时不得推进，也不得以低成本为由判定通过。

任一不满足 → 原样退回该阶段并附缺失清单。（EVIDENCE 不产 handoff JSON，其守卫见 `references/artifacts.md` 的「EVIDENCE 证据包的最小校验」。）

## 循环与终态

| 回路 | 触发 | 处理 | 上限 |
|---|---|---|---|
| `needs_research` | PLAN 判定证据包不足 | 进 `EVIDENCE`，产出证据包后 **fresh 重派 PLAN** | `research_round` 2 轮；超限 → 升级为用户访谈或 HALTED |
| `plan_revision_round` | 用户拒绝冻结、要求修订 | 回 PLAN 修订 | **3 次**；超限 → HALTED（防活跃迭代无限重付最贵模型） |
| `契约外提交` | GATE 发现 diff 含无 ticket 归属的文件（父会话提交/生命周期变更） | 已登记于 `orchestrator_commits` → 放行并记录；未登记 → **REPLAN**（让 PLAN 重定义 allowed_paths 追认）或 HALTED（人工裁决） | 计入 replan_round / 直接 HALTED |
| `blocked_on_interview` | A native request expires or the user cancels | If PLAN returns a handoff, retain the unresolved questions; a hard termination may produce none | No interview-turn limit; the PLAN run has its 24-hour deadline |
| `REPLAN` | Gate 判定契约缺陷 / Conformance 判 REPLAN / **Execute 失败且 attempts 耗尽** | `replan_round++`，回 PLAN | >3 → **HALTED** |
| `FIX_EXECUTE` | Gate 判**未授权**测试被改 / Conformance 判硬编码空壳 | 回 EXECUTE：**指向 violation 证据定位的票；无法定位时指回最后完成票**（不得指向越界 cursor）。**注意**：EXECUTE 被禁止改测试——若 violation 的修复动作本身需要改测试，则 FIX_EXECUTE 无合法动作，应直接走 `REPLAN`（契约/测试缺陷）或 `HALTED`（需人工裁决），不得反复派发空任务 | 计入该票 attempts |
| `attempts` | Execute 单票失败 | 重试同票（**逻辑失败先重试，耗尽后才 REPLAN**）。state.attempts[T] 仅在**该次派发以失败告终**时 +1；ExecuteHandoff.attempts 是票内自报尝试数，守卫对账**以后者为准** | 满 3 次 → 强制 REPLAN（计入 replan_round） |
| `dispatch_failures` | 派发返回错误/无 handoff（infra/网络/配额）/ handoff 校验退回 | 原样退回或重派该阶段并附缺失清单 | 每阶段 **3 次**；超限 → HALTED（不得静默继续） |
| `HALTED` | 上述任一上限触顶 | **保留全部 handoff/证据并上报用户，禁止继续** | 终态 |

执行失败重试或 REPLAN，**不升级模型档位**。

## 用户确认点（三段）

1. Pre-flight：探测 `merge_mode`，未提交代码 → commit。`y` 继续，`n` → 等待用户处理（不推进）；
2. PlanHandoff 展示后 → 冻结：展示以 `spec.intent` 为主体（原样给出那几行：问题 / 达成什么 / 每条约束及其强制者 / 不做），tickets 与验收清单作为脚注；`y` 进 TEST_AUTHOR；`n` → 回 PLAN 修订（计入 `plan_revision_round`，上限 3；与「用户不可达」语义分离）；
3. 交付：`direct` → 接受即完成（归档后止，**永不 push**）；`branch` → 打开 PR 并**等用户确认 merge**。`n` → 保留全部产物并停止（不回滚，由用户决定处置）；`HALTED` → 上报用户。

## merge_mode（探测所得，不靠「任务简单」这类判断）

`HEAD` 在集成分支上（`git symbolic-ref refs/remotes/origin/HEAD`，取不到则 `main`/`master`）且不是 linked worktree（`git rev-parse --git-dir` 与 `--git-common-dir` 相同）→ `direct`；否则 `branch`。结果写入 `state.merge_mode`。

| 模式 | 节点提交 | 归档 | 末步 |
|---|---|---|---|
| `direct` | 直接提交在工作分支 | 工作分支上一个独立提交 | 接受即完成；**永不 push** |
| `branch` | 分支内自由提交 | **同一个分支上**，让 PR 带着 spec | 开 PR；缺 `gh` 时只报告分支与待执行命令，不 push；**merge 必须等用户确认** |

## 交付物归档（merge `y` 之后，父会话执行）

`handoffs/` 是一次性的、gitignored 的机器产物。交付完成后把它里面**给人看的部分**固化进仓库，让下一次交付不必从零开始：

1. 写 `docs/specs/<YYYY-MM-DD>-<slug>.md`（无 `docs/` 则创建），内容见 `references/artifacts.md` 的模板：`spec.intent` 渲染在最前（人读一屏）+ `spec` 的六节 + tickets 的 acceptance 清单 + Verdict 结论与 `reasons`；
2. **不写**五个 handoff 的 JSON 全文、不写证据包正文（只留路径）；
3. 单独一个提交 `docs(spec): <title>`，并把它登记进 `state.orchestrator_commits`（否则 GATE 重跑会判它越界）；
4. PLAN 保持只读、不参与这一步——归档是父会话的职责，与「原样落盘 handoff」同类。

仓库里已有既定约定（如 `docs/adr/`、`docs/rfc/`）时**跟随现有约定**，不要另起一套；没有约定才用 `docs/specs/`。

## 编排循环（父会话保持薄编排）

```
读 state ─→ 组装 task prompt ─→ 派发 subagent ─→ 子 agent 返回 handoff JSON
    ↑                                                    │
    └── 校验 handoff → 原样落盘 → 写 state（下一阶段）←────┘
```

1. 读 state 确定当前阶段，按「节点定义 + 产物契约」组装阶段 task prompt；
2. 按 dispatch 契约启动阶段 agent（cwd=目标仓库；平台落地见 adapter）；**派发失败（错误返回/无 handoff）→ 计入 `dispatch_failures` 并重派，超限 HALTED**；
3. 执行确定性 Gate（GATE 节点无 subagent），证据落盘；
4. 用户确认点。

# 二、节点定义

每个节点统一给：**职责 / 内部步骤 / 输入 / 输出 / 禁令 / 阻塞语义**。

## dispatch 契约

每阶段一次独立派发：

```text
Agent(description="<节点名>", prompt="<组装结果>", model=@<节点符号>)
```

| 节点 | model 符号 | context | 复用的既有 skill | 硬约束 |
|---|---|---|---|---|
| EVIDENCE | `@evidence` | fresh | `research` | 按缺口类型选择具备对应检索能力的 agent |
| PLAN | `@plan` | fresh | `grilling` → `to-spec` → `to-tickets` | 只读 |
| TEST_AUTHOR | `@test_author` | fresh | `tdd` | 只提交测试资产 |
| EXECUTE | `@execute` | fresh | `tdd` | 只写 allowed_paths |
| CONFORMANCE | `@conformance` | fresh | `code-review` | 只读；模型家族异于 EXECUTE |

**本 skill 只做编排**：每个阶段的**流程与判据来自该阶段复用的既有 skill**，本文件只规定节点边界（输入/输出/只读或可写/上下限），不重写它们的步骤。引用 skill 时给**路径原文**，不给摘要——摘要会随作者更新而过期，且把别人的方法变成我的转述。宿主没有这些 skill 时按同样的语义自行映射，并在派发时说明缺哪一个。

- `@<节点符号>` 取 `config.json` 的推荐值（缺则 `config.template.json`），**节点级整条替换**，不合并字段。
- **改配置必须过回归**：变更任何 `model`/`thinking` 前，先跑完 `evals/regression/` 的全部检查并亲自读结果；没跑完或没过，不得把这些值当作已验证。
- 派发后核对实际生效的 model/thinking 与声明一致；不一致 → **HALTED**。
- 硬能力：每阶段独立的 fresh 上下文、PLAN 运行中访谈、per-agent 模型指定、每个节点绑定所需的工具面与启动模式。宿主缺少任一且 adapter 未预声明该通路 → **HALTED**，不得现场降级（派发后才发现同样计一次 `dispatch_failures`）。

**特殊通道**：当前 agent 是 pi 且已装 pi-subagents → 参照 `references/pi-adapter.md`，沿用其内置 agent 与启动参数；其它宿主按同一契约自行映射。

## EVIDENCE（检索型 · 可选节点）

- **职责**：把 PLAN 的 `needs_research` 缺口清单，或 pre-flight 判定的预研不足，变成**固化证据包**——路径 + 摘要 + 边界说明，供 PLAN 只读消费。**证据由父会话前置补齐，而非让 PLAN 本体多轮探索**。
- **内部步骤**：按缺口清单逐项检索（代码/文档/数据/外部来源）；每项产出「结论 + 证据路径 + 不确定性」；写入 `handoffs/research/*.md`。仓内缺口与仓外缺口分别派发给具备对应检索能力的 agent（同一轮可多次派发）。
- **输入**：`needs_research` 清单（或 pre-flight 预研任务）。
- **输出**：每缺口一份证据包 + 回执（路径清单）。**不需要 handoff JSON**。子 agent 只产出内容，由父会话**原样落盘**到 `handoffs/research/<gap>.md`（同 handoff 处理：不改写）；运行时的输出重定向不算落盘。
- **禁令**：不产出 spec/tickets/dag（那是 PLAN 的推理产物）；不改目标仓库代码。
- **阻塞语义**：检索受阻（需要凭证/联网受限）→ 在证据包中标注为不确定性，不阻塞。

## PLAN（推理型 · 只读）

- **职责**：消费证据包与既有 brief，给出**深度推理后的规划见解**：spec、tickets、DAG 与路径边界。
- **内部步骤**：按顺序逐项执行三个 skill——`grilling` → `to-spec` → `to-tickets`（`grilling` 注入，后两个用 read 打开绝对路径；见 `references/references-index.md`）。不自行改写、不跳步、不合并。这三步之外的差异只有「发布目标」（无 issue tracker，产物是 `handoffs/plan-handoff.json`），必须逐条记入 PlanHandoff 的 `deviations`；任何其它偏离都视为违反本节点契约。
- **输入**：Evidence pack (referenced by path), brief, the full interview context from `state.interview_log`, and the **prior decisions**——父会话派发时把 `docs/specs/*.md` 的 `Settled decisions` 段与既有的 `GLOSSARY.md` / ADR 路径写进 task prompt。取舍：与本次目标同领域的全收，其余只收最近 3 份（先例越多越容易误继承）。已定决策不得重问；**与本次需求冲突时必须显式指出冲突并重新裁定**，不得默默继承。
- **输出**：PlanHandoff JSON（`references/artifacts.md`），含 `seams`（每票测试要打的边界；越少越好，理想 1 个）与 `decisions`（用户已裁定的决策，供归档沉淀）。
- **只读状态（同业界 plan mode：先探索后规划，写入须待批准）**：
  - **允许**：读文件、检索代码、只读检查命令——把计划落在真实代码上优于凭摘要猜测；仅限计划实际依赖的范围（入口点、将在 ticket 中引用的类型与接口、既有测试约定、将入 `allowed_paths` 的路径）。
  - **探索边界（硬性）**：**不得调查与本次契约无关的故障或异常**（如环境噪声、工具链不一致、既有测试的偶发失败）。遇到此类现象：**停止调查**，在 `ambiguities` 中记录现象与影响即可（一次记录，不追根因）；若它阻塞规划，走 `needs_research` 或访谈。禁止把探索预算投入无法在本次交付中解决的问题。
  - **禁止写作与副作用**：不编辑/不写入/不执行变更状态命令，不改动目标仓库。
  - **禁止外部调研**（联网/抓取/生产研究产物）——属 EVIDENCE 职责；此类缺口列 `needs_research`。
  - 缺口分派：仅用户能定的 → 访谈；仓内可查的 → 自行只读查看；需外部调研的 → `needs_research`。
  - **等待用户输入期间零输出**：不发进度类空转消息。
- **Interview and wait**: 方法用注入的 `grilling`，尤其**每问必带推荐答案、措辞使「yes」即采纳**。裁定权只在用户。An explanation request, partial answer, discussion, or brief absence is not final: incorporate the verbatim reply and explain or ask only about what remains unresolved; do not repeat settled questions or answer for the user.
  - Each native interview request must include valid `message` and `interview` fields. The parent relays the user's reply verbatim; PLAN alone determines whether it settles the decision.
  - Wait quietly without heartbeat messages, repeated requests, or polling. Return `blocked_on_interview` only when the channel request actually expires or the user explicitly cancels; a hard stop or PLAN run-deadline kill may terminate without a handoff.
  - Keep ordinary discussion in the original PLAN run; do not relaunch or resume it.
- **allowed_paths**：覆盖任务合法变更的全部路径——含因契约变更需重生成的既有产物（渲染输出/golden 快照等），此类不入 `protected_paths`。

## TEST_AUTHOR（实施型 · 只写测试）

- **职责**：red-first 黑盒验收测试。
- **内部步骤**：在任务**最高外部 seam** 上断言可观察行为（子进程 stdout/stderr/exit code、公开 API 返回值、落盘产物等）；跑一次确认**此刻必须红**且红因与验收一致。
- **输入**：PlanHandoff。
- **输出**：TestHandoff（`references/artifacts.md`）。
- **禁令**：不 mock 被测对象获得绿；实现文件不碰，**只提交测试资产**；提交后测试冻结（对 EXECUTE 受保护）。
- **既有测试处理**：与本契约变更无关的既有测试保持绿；编码被本契约取代的既有测试属 **red set**——在同一提交中一并更新，红因同上。TestHandoff 记 `existing_tests_updated`。

## EXECUTE（实施型 · 按票循环）

- **职责**：按 DAG 拓扑序逐票实现。
- **内部步骤**：父会话从 DAG 拓扑序取下票 → 组装 task prompt（见下必含项）→ 派发 → 收 ExecuteHandoff → 校验 → 写 state。
- **task prompt 必含**：该票验收**逐条编号**；`你只允许写：${ALLOWED}`（ALLOWED 从 handoff 提取，**禁止心算**，提取命令见 `references/artifacts.md`）；`测试红：携带完整输出重试；你最多 3 次尝试`；`不得改测试获得绿色`。
- **输入**：PlanHandoff 单票 + TestHandoff 冻结的测试。
- **输出**：ExecuteHandoff（`references/artifacts.md`）。
- **禁令**：不改测试；不越 allowed_paths；单次派发只启动一个子 agent。
- **未获授权的决定**：契约缺口或需要新决策时，按本节点阻塞语义上报（`ambiguities`，或 `need_decision`），不自行拍板。
- **完成声明**：没有实际变更时不得返回成功总结；只交付契约要求的实现，不留冒充完成的空壳或占位。
- **阻塞语义**：逻辑失败 → 重试同票（≤3）；环境/契约缺陷 → REPLAN。

## GATE（父会话 · 确定性 · 无 subagent · 不可跳过）

- **职责**：机械核验，**不采信任何理由**。检查项与产出见 `references/artifacts.md`。

## CONFORMANCE（审计型 · 只读 · Gate 绿后）

- **职责**：仅 A 问——有没有硬编码/空壳骗测试。
- **输入**：`handoffs/impl.diff`（父会话落盘，覆盖 `BASE_SHA..HEAD`）、`BASE_SHA` 与 `HEAD`、变更文件清单、`allowed_paths`、冻结测试路径清单。审计 agent 的 diff 工具不覆盖已提交范围，其只读面也不保证含 `.git`；缺这些输入它会（正确地）自陈限制，而不是声称审过。
- **禁令**：只读——不改代码、不代为实现；证据不足时如实报告限制，不推断。
- **输出**：Verdict：`PASS` / `FIX_EXECUTE` / `REPLAN`（`references/artifacts.md`），必须带 `answer_key`（逐条 acceptance 的代码位置与理由）与 `rerun`（独立重跑结果或缺什么）。空泛的「未发现硬编码」不算回答。
- **不许只报结论**：`answer_key` 的 `evidence` 由父会话用 `scripts/check-verdict.py` 机械校验（文件存在、行号在 `impl.diff` 触及范围内）；校验不过按 `dispatch_failures` 重派。
- **canary 校准**：`findings` 为空即可 `PASS`，而"不查"是最省力的满足方式。每次流水线运行至少一次，用注入已知作弊的仓库副本、同模型同 prompt 派发本节点，必须报 `FIX_EXECUTE`；报 `PASS` → 该节点本轮不可信，正式结论降级（流程见 `references/artifacts.md`）。

# 三、跨节点规则

- **Decision channel**: PLAN stays in its current run and continues clarifying after explanation requests, partial answers, discussion, and other non-final replies. PLAN waits quietly without polling or progress heartbeats; stage-agent questions retain their existing handoff behavior and are recorded in `ambiguities`, or `reasons` when that field is unavailable.
- **PLAN expiry**: End a PLAN interview only when its native request actually expires, the user explicitly cancels, or the run terminates. Record unresolved content after normal expiry; hard termination may yield no handoff.
- **质量验收不可牺牲（成本仅为诊断指标）**：PLAN user rulings must come from the user's verbatim reply; explanations or partial answers never become default decisions. Evidence paths must exist and state must match the handoff. Do not waive quality for cost.
- **Fail closed**: Route a missing or unparsable stage-agent decision payload to REPLAN rather than guessing or skipping it. PLAN corrects an invalid interview request before asking and never infers the user's answer.
- **writer 链单写手串行**：每个 dispatch 只启动一个子 agent；上票 commit 后才派下票。
- **交接协议（skill:handoff）**：阶段 task prompt 按其协议组装——紧凑、已有 artifact **引路径不复制内容**、附该阶段 References（suggested skills）、无敏感信息。artifact 以**已验证的绝对路径**给出。
- **边界由 harness 强制，不由散文**：每个节点在派发时加载绑定的守卫（`extensions/guard-*.js`），越界写入与写文件的 bash 命令会被 **block**，不是被劝说。散文版边界条款仍保留在 task prompt 里作为**说明**，但不作为唯一防线。
  - 节点 ↔ 守卫：PLAN=只读（bash 走 plan-mode 的只读白名单）；EVIDENCE=只写 `handoffs/research/`；TEST_AUTHOR=只写契约开放的测试路径 + `test-handoff.json`；EXECUTE=只写 `allowed_paths` 且不在 `protected_paths`；CONFORMANCE 无写工具。
  - 守卫**只管主写入面**：`write`/`edit` 全量校验，bash 只拦明显的写文件形态（重定向、`sed -i`、`tee`、`mv/rm/cp`、`git commit/checkout/reset` 等），**不构成 bash 沙箱**——EXECUTE 必须能跑测试与提交，而任意 shell 命令里没有路径信息。EXECUTE 的路径边界最终仍由 GATE #2 事后核验。
  - 读不到 `handoffs/plan-handoff.json` 时契约驱动的守卫**默认禁写**（fail closed），不是放开。
- **明确不机械化的三条（保留散文，不许假装已强制）**：`探索边界`（「不得调查无关故障」是内容判断）、`等待用户输入期间零输出`（父会话行为）、`证据不足如实报告限制`（诚实性）。它们写在节点定义里，标注为散文约束。
- **边界条款为固定措辞**：按节点取对应一版，组装时原样附上，不得改写。
  - EXECUTE：`受保护（不得写入）：${protected_paths}（本任务指定产出的 handoff artifact 除外，如 execute-handoff.json；plan-handoff.json 契约文件始终不可改写）`。
  - TEST_AUTHOR：`受保护（不得写入）：${protected_paths 去掉测试路径后的剩余项}（测试路径与 test-handoff.json 是本节点的交付物，必须写入并提交；plan-handoff.json 契约文件始终不可改写）`。测试目录常同时出现在 `protected_paths` 里——那是给 EXECUTE 的约束，不得照抄给本节点。
- **Pre-flight（父会话，一次性）**：
  1. 未提交代码先 commit（用户 y/n）；
  2. 固化 `BASE_SHA = git rev-parse HEAD`（**禁止手抄** `--oneline` 前缀拼 SHA）；
  3. 写初始 state 文件：默认 `stage=PLAN`；若 pre-flight 判定预研不足则 `stage=EVIDENCE`（两者互斥，不冲突）。