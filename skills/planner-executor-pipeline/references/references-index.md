# 外部引用（References）

> 由 `SKILL.md` 按需加载：需要解析 `/command` 或查阅上游文档时读取。

- 交接协议：`~/.agents/skills/handoff/SKILL.md`

## 每阶段复用的既有 skill（本 skill 只做编排，不重写流程）

| 节点 | skill | 怎么拿到 |
|---|---|---|
| PLAN | `grilling` | 注入：上游未隐藏，`agents/plan.md` 的 `skills:` 直接点名 |
| PLAN | `to-spec` | 注入：本 skill 的 `skills/to-spec/SKILL.md`（镜像） |
| PLAN | `to-tickets` | 注入：本 skill 的 `skills/to-tickets/SKILL.md`（镜像） |
| TEST_AUTHOR / EXECUTE | `tdd` | 注入：上游未隐藏，各 agent 的 `skills:` 点名 |
| EVIDENCE | `research` | 绝对路径 read：`~/.agents/skills/research/SKILL.md`（内置 agent 无法注入） |
| CONFORMANCE | `code-review` | 绝对路径 read：`~/.agents/skills/code-review/SKILL.md`（内置 reviewer 无法注入） |

PLAN 的三步是**注入的 skill**，不是引用文件：`agents/plan.md` 里 `skills: [grilling, to-spec, to-tickets]` 加 `skillPath: [.., ../skills]`，子 agent 的 `<available_skills>` 里直接出现这三项，按顺序逐个执行其原文。

**怎么执行**：把 skill 的原文当成本步骤的流程照做，**不要凭记忆复述它的要点**。文件里的 `/command` 形式与 tracker 发布在子 agent 里不可用，按下面「允许的偏离」处理；其余步骤（访谈的 design tree 与 frontier 规则、spec 模板、垂直切片与 blocking edges、seam 约定、red→green 循环、双轴评审）**必须原样执行**。

## 镜像（mirror）为什么存在

`to-spec` 与 `to-tickets` 上游带 `disable-model-invocation: true`，pi-subagents 在 `buildSkillInjection` 这个唯一收口处把这类 skill 从子 agent 的 prompt 里硬过滤掉——`skills:` 显式点名也送不进去。镜像保留上游 body **逐字节不变**，只去掉那一行标记，于是它重新成为 PLAN 可见的 skill。

- 生成：`python3 scripts/sync-skill-mirrors.py`
- 校验：`python3 scripts/sync-skill-mirrors.py --check`（body 与上游不一致即失败；`grilling`、`to-spec`、`to-tickets` 三项在 PLAN 侧的可达性也在这里查）
- 镜像不进主会话：pi 的 skill 扫描在含 `SKILL.md` 的目录处停止递归，所以 `skills/` 子目录只有 `skillPath` 点名了它的 agent 才看得见。

## 允许的偏离（除此外任何偏离都算违约）

- **发布目标**：`to-spec` / `to-tickets` 原文要求发布到 issue tracker；本流水线没有 tracker，产物是 `handoffs/plan-handoff.json`（spec 段照 to-spec 模板，tickets 段照 to-tickets 模板）。逐条写进 PlanHandoff 的 `deviations`。
- **`to-spec` 的「不要访谈」**：本节点在 to-spec **之前**用 grilling 完成访谈，故不冲突；不得因为「已经问过」而跳过 grilling。
- **`to-tickets` 的「quiz the user」**：与流水线的冻结点合并——切片问询在 PLAN 内完成，冻结确认由父会话在 PlanHandoff 提交后一次提出。
- **`code-review` 的双轴**：Standards 轴在本流水线由 GATE 的机械检查承担，CONFORMANCE 只承担 Spec/反作弊轴。

## pi 宿主的事实（不要照着猜）

- skill 对子 agent 的可见性由 `buildSkillInjection` 一个地方决定：`disable-model-invocation: true` 的 skill 永远不进子 prompt。本机现状：`grilling`、`domain-modeling`、`tdd`、`research`、`code-review` **可见**；`grill-me`、`grill-with-docs`、`to-spec`、`to-tickets`、`implement` **隐藏**。
- `grill-me` 与 `grill-with-docs` 的 body 只有一句「Call the Skill tool with ...」，而 pi 子 agent 没有 Skill 工具 → 别名没有意义，直接用 `grilling`（需要 ADR/词汇表时用 `domain-modeling`）。
- 内置 agent（`scout`、`researcher`、`reviewer`）的 skill 面由 pi-subagents 决定，改不了 → 它们只能靠绝对路径 read。
- subagent model routing: `~/.pi/agent/npm/node_modules/pi-subagents/docs/models.md`
- workflow orchestration: `~/.pi/agent/npm/node_modules/pi-subagents/docs/workflows.md`
