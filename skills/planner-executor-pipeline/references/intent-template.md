# spec.intent — 一屏意图

PLAN 在冻结前产出 `spec.intent`，父会话把它原样展示给用户确认。它是**摘要**：验收条目才是判据，两者冲突以验收为准，intent 不改判定。

## 强制者是什么

`enforced_by` 里的每一项必须指得出谁在守：

| 强制者 | 含义 |
|---|---|
| `ACn` | 本票 `acceptance` 里的第 n 条（`AC1`…`ACn`），一条在最高外部 seam 上**可机械断言**的行为 |
| `review-only` | 本 seam 无法断言（流式内部实现、改动落点一类的约束），由 CONFORMANCE 读代码确认 |
| `GATE#n` | 由第 n 道门禁机械检查（例如 `GATE#2` = diff 必须落在 `allowed_paths` 内） |

**指不出强制者的句子删掉**，不要降级成一句希望。

## 字段

| 字段 | 是什么 | 不写什么 |
|---|---|---|
| `status` | `draft` → `accepted`；冻结前 `draft`，用户确认后 `accepted` | 不记进度、不写作者（作者可从 `decisions[].user_reply` 还原） |
| `problem` | `problem_statement` 的**首句**（同一句话，不另写）：改动**之前**世界里谁在疼、疼多少 | 不写方案；不写文件名/函数名/新命令名；不写"用户希望/需要…"式转述 |
| `outcome` | 改完后**外部可观察**的样子，≤2 句 | 不复述验收清单；不出现验收编号；不写实现路径 |
| `constraints[{text,enforced_by[]}]` | 无论怎么实现都必须成立的底线 | 不写怎么实现；不写无法验证的形容词（足够/尽量/健壮/友好） |
| `not_doing[]` | 本次明确不做的事（可为空；由 `GATE#2` 挡范围蔓延） | 不写"以后再说"——那是未决问题，只能走访谈并在冻结前答掉 |

不存在 `open_questions` 字段：未决问题必须走访谈，冻结前答掉。

`PlanHandoff` 顶层同期必填 `new_symbols[]`（本次新增的命令名/函数名/模块名）：`problem` 与 `outcome` 描述的是改动前后的世界，不能靠新名字叙述，检查器要用它来判。

## 示例（学语气与密度）

来源：Anthropic — *AI-native SDLC playbook · Capture as intent.md*。删去 `Author`、`Affected users and systems`、`Open questions`；约束后括注是**占位**，真实标注须指向本票真实存在的强制者。

```markdown
Status: draft.

## Problem
Customers phone the contact center to ask where their claim is.
Handlers spend roughly a third of call time on status-only queries.

## Proposed outcome
Customers see claim status, next step and expected date in the portal.

## Constraints
No new PII in the portal session. （AC2）
Existing authentication only. （GATE#2）
```

落到字段上（同一份意图的中文渲染，字段即产出形状）：

```json
{
  "status": "draft",
  "problem": "客户打电话问理赔进度；坐席约三分之一通话时间在处理这类纯查询。",
  "outcome": "客户在门户里自己看到状态、下一步和预计日期。",
  "constraints": [
    {"text": "门户会话不得引入新的个人数据。", "enforced_by": ["AC2"]},
    {"text": "沿用现有认证方式，不新增登录路径。", "enforced_by": ["GATE#2"]}
  ],
  "not_doing": ["第三方 loss adjuster 的访问（未决，走访谈）"]
}
```

## 反例（真实发生过的漂移，不是编的）

设计泄漏进 intent —— 约束写成了实现：

```json
{"text": "新增 stdin_count.py，提供 count_lines(lines) -> int 逐行消费", "enforced_by": ["AC5"]}
```

漂亮话 —— 无强制者、无外部可观察面：

```json
{"text": "计数必须足够快，大输入下也要稳", "enforced_by": []}
```

## 检查

`python3 scripts/intent-check.py handoffs/plan-handoff.json --require-accepted`（归档时加 flag）。C9 `problem` 必须派生自 `problem_statement` 首句；C0 未定义字段、C1 实现标识、C2 引用新符号、C3 强制者缺失或不存在、C4 `outcome` 变成清单、C5 `not_doing` 是未决问题、C6 无法验证的措辞、C7 `status` 非两态、C8 出现 `open_questions`。回归夹具：`evals/regression/t2/intent-*.json`。
