# 外部引用（References）

> 由 `SKILL.md` 按需加载：需要解析 `/command` 或查阅上游文档时读取。

- 交接协议：`~/.agents/skills/handoff/SKILL.md`（见 `## Preflight`）

## 每阶段复用的既有 skill（本 skill 只做编排，不重写流程）

| 节点 | skill | 怎么拿到 |
|---|---|---|
| PLAN | `grilling` | read 绝对路径：`~/.agents/skills/grilling/SKILL.md` |
| PLAN | `to-spec` | read 绝对路径：`~/.agents/skills/to-spec/SKILL.md` |
| PLAN | `to-tickets` | read 绝对路径：`~/.agents/skills/to-tickets/SKILL.md` |
| TEST_AUTHOR / EXECUTE | `tdd` | read 绝对路径：`~/.agents/skills/tdd/SKILL.md` |
| EVIDENCE | `research` | read 绝对路径：`~/.agents/skills/research/SKILL.md` |
| CONFORMANCE | `code-review` | read 绝对路径：`~/.agents/skills/code-review/SKILL.md` |

每个节点都**执行 skill 原文**，不是引用要点；所有外部 skill 一律 read 绝对路径（原因见下），按顺序逐个执行其 Process 与模板。

**怎么执行**：把 skill 的原文当成本步骤的流程照做，**不要凭记忆复述它的要点**。文件里的 `/command` 形式与 tracker 发布在子 agent 里不可用，按下面「允许的偏离」处理；其余步骤（访谈的 design tree 与 frontier 规则、spec 模板、垂直切片与 blocking edges、seam 约定、red→green 循环、双轴评审）**必须原样执行**。

## 依赖怎么拿

每个外部 skill 一律 read `~/.agents/skills/<name>/SKILL.md`；仓库里不放副本，也不依赖注入。路径与安装命令在 `SKILL.md` 的 `## Preflight` 里。

## 允许的偏离（除此外任何偏离都算违约）

- **发布目标**：`to-spec` / `to-tickets` 原文要求发布到 issue tracker；本流水线没有 tracker，产物是 `handoffs/plan-handoff.json`（spec 段照 to-spec 模板，tickets 段照 to-tickets 模板）。逐条写进 PlanHandoff 的 `deviations`。
- **`to-spec` 的「不要访谈」**：本节点在 to-spec **之前**用 grilling 完成访谈，故不冲突；不得因为「已经问过」而跳过 grilling。
- **`to-tickets` 的「quiz the user」**：与流水线的冻结点合并——切片问询在 PLAN 内完成，冻结确认由父会话在 PlanHandoff 提交后一次提出。
- **`code-review` 的双轴**：Standards 轴在本流水线由 GATE 的机械检查承担，CONFORMANCE 只承担 Spec/反作弊轴。

## pi 宿主的事实（不要照着猜）

- `grill-me` 与 `grill-with-docs` 的 body 只有一句「Call the Skill tool with ...」，而 pi 子 agent 没有 Skill 工具 → 别名没有意义，直接用 `grilling`（需要 ADR/词汇表时用 `domain-modeling`）。
- 内置 agent（`scout`、`researcher`、`reviewer`）的 skill 面由 pi-subagents 决定，改不了 → 它们只能靠绝对路径 read。
- subagent model routing: `~/.pi/agent/npm/node_modules/pi-subagents/docs/models.md`
- workflow orchestration: `~/.pi/agent/npm/node_modules/pi-subagents/docs/workflows.md`
