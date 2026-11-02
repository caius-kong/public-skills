# planner-executor-pipeline v2 最终报告

> 交付日期 2026-09-20 ｜ 从"缺陷修复"演化为"协议重构 + 端到端验证 + 独立审查"

---

## 一、结论摘要

**协议本体可投产；但有三项前置条件（见 §7）。**

| 维度 | 结果 |
|---|---|
| 端到端流水线 | ✅ 全节点跑通，**40/40 测试全绿** |
| 成本（vs 事故） | **≈105× 降低**（$0.46 vs $48.39） |
| 事故根因修复 | ✅ 三项全部修复并**实测验证** |
| 独立对抗性审查 | ✅ 三轮，发现并修复 15 + 5 项问题 |
| 协议缺口 | 发现 5 项（G1–G5），**全部修复并回归验证** |
| 未闭合项 | 见 §6（诚实清单） |

---

## 二、交付物清单（已核验）

### 协议本体（skill 形态）

```
~/.agents/skills/planner-executor-pipeline/
├── SKILL.md                              179 行  状态机 + 节点定义 + 跨节点规则
└── references/
    ├── artifacts.md                       63 行  产物契约 + GATE 检查项 + verdict 映射
    ├── platform-adapter.md                45 行  模型路由 / 裁决通道 / 工具面 / dispatch
    └── references-index.md                14 行  外部引用
```

**分层原则**：§一–§三（核心协议）**零平台专有名词**（实测验证）；平台细节全部下沉 references，可整体替换。

### 配套

| 文件 | 作用 | 状态 |
|---|---|---|
| `~/.pi/agent/agents/plan.md` | PLAN 专用 agent（只读探索、禁写、探索边界） | ✅ 3961B |
| `~/.pi/agent/settings.json` | `plan` override → `glm-5.3:high` | ⚠️ 见 §7-C1 |

---

## 二·补 设计依据（业界对照，2026-09）

本协议的设计来自三角度独立研究（长程架构 / 验证纪律 / 模型路由，全文见本目录 `evals/research/`）收敛出的业界共识层：

1. **长任务 = 计划 → 小可验证单元 → 结构化交接 → 独立验证**，而非单 agent 一口气（Anthropic long-running harness、OpenAI harness engineering、Cognition、GitHub Spec Kit / Kiro）
2. **上下文是稀缺资源：fresh 隔离 + 工件交接优于对话继承**（Anthropic context engineering、Cognition Agentic MapReduce）
3. **验证独立于执行者且不可被其篡改；反 reward hacking 是一等公民**（METR 实证、AA 评测法、red-green TDD 实践）
4. **失败确定性停止：预算上限 + fail-closed，而非无限循环**（LangGraph recursion limit、Claude Code 官方实践）
5. **LLM 管语义产出，确定性工具管门禁与状态**（LangGraph 确定性/LLM 混图）

非共识层为本地取舍（详见本目录 `evals/eval-log.md`）：阶段数与重试阈值无行业标准；旗舰模型仅用于访谈（业界倾向按质量信号动态升级，留观）；纯 prompt 编排适用于低并发单 writer 场景（生产规模业界倾向代码化 durable runtime）。

调度者（父会话）模型推荐 `deepseek-v4.1-flash`：编排为机械型任务，管线 fail-closed 机制不依赖父会话判断；父会话是全 run 唯一长会话（多 turn 共享增长前缀），deepseek cache 折扣在此访问模式下最大化——与 worker 阶段弃 deepseek（fresh 交接取不到缓存）正交。

## 三、核心改进（与原始设计对比）

| 维度 | 原设计 | 现设计 | 依据 |
|---|---|---|---|
| **PLAN 承载 agent** | `oracle`（外部审计者） | **专用 `plan` agent** | oracle 的 systemPrompt 明写"保护既有决策、防漂移、不成为第二决策者"，与 PLAN"产生新决策"**目标函数冲突**；实测旧配置下 oracle 甚至**不输出 PlanHandoff**（返回其固有报告格式） |
| **PLAN 探索策略** | （事故中）无边界自由探索 → 147 次调用 | **业界 plan mode 标准**：只读探索**允许**，写入**禁止**，外部调研归 EVIDENCE | Claude Code / xAI / Addy Osmani 一致做法："explore first, plan second, act after approval" |
| **卡片式骨架** | 单文件混排 | **状态机 + 节点定义 + 附录**（你的建议） | 编排机制与阶段定义分离，可读性与可维护性 |
| **平台绑定** | 混在协议正文 | **三层分离**（核心 / 适配 / 引用） | 你的要求："我期望通用，没有框架绑定" |
| **形态** | prompt template（16.5KB 全文进上下文） | **skill（渐进披露）** | 匹配分层结构；获得 gate 硬门保护 |

### 事故三联根因的处理

| 根因 | 机制 | 处理 | 验证 |
|---|---|---|---|
| ① ask 超时被 `throw` 成"工具失败" → 重发 | `native-supervisor-channel.ts:264` | 协议：**有界等待 + 超时即终局 + `blocked_on_interview`**，明确"超时是预期结果不是失败" | ✅ 专项注入实测（§5） |
| ② 桥接模板召唤 `progress_update` → 74 次空转 | `intercom-bridge.ts:33` | 协议：**等待期零输出**；不依赖框架改动 | ✅ 实测 0 次 |
| ③ PLAN 自行探索 → 147 次调用 | 无职责分离 | **职责分离 + EVIDENCE 节点 + 探索边界** | ✅ 实测 13 次（且为定向只读） |

---

## 四、端到端实测（fixture `/tmp/e2e-pipeline`）

**任务**：基金持仓周报 CLI（持仓/量具池分离 → 指标 → 建议规则 → Markdown 周报）
**基线**：greenfield + 1 既有绿测试，BASE_SHA `c98a9360dcac`

| 节点 | 结果 | turns | cost |
|---|---|---|---|
| PLAN | ✅ 契约全字段、`dag` 形状正确 | 8 | $0.166 |
| TEST_AUTHOR | ✅ 39 红 / 1 绿 / 0 收集错误（重派 1 次） | — | ~$0.008 |
| EXECUTE T1 | ✅ 10 passed | 41 | $0.093 |
| EXECUTE T2 | ✅ 14 passed | 14 | $0.012 |
| EXECUTE T3 | ✅ 6 passed（含授权 fixture 修正） | 16 | $0.027 |
| EXECUTE T4 | ✅ 3 passed（含授权锚点修正） | 12 | $0.088 |
| EXECUTE T5 | ✅ 6 passed（`thinking:low`） | 19 | $0.028 |
| GATE | ⚠️ PASS_WITH_RECORDED_VIOLATIONS（见 §6） | — | — |
| CONFORMANCE | ✅ **PASS**（含对抗性数据探测） | 21 | $0.041 |

**最终：40 passed（全绿）｜总成本 ≈$0.46**

### 成本对比

| | 事故 run2 | 本次全流程 |
|---|---|---|
| 模型 | `gpt-5.6-sol:max` | `glm-5.3`(:high) / `glm-5.3-flash` |
| turns | 189 | ~131 |
| 工具调用 | 224（147 探索 + 74 空转） | ~110（0 空转、13 定向探索） |
| **成本** | **$48.39** | **≈$0.46** |
| **倍数** | 1× | **≈105×** |

### `thinking` 档位的实测影响（n=1/票，非受控）

| 票 | thinking | cost | output tokens |
|---|---|---|---|
| T1 | max | $0.093 | 41,580 |
| T4 | max | $0.088 | 74,192 |
| **T5** | **low** | **$0.028** | **12,808** |

T5 任务量最大（5 文件 + CLI + 示例数据 + README）却是成本次低，output 仅 T4 的 1/6。

### CONFORMANCE 的质量（值得单独指出）

它做了**对抗性探测**而非静态检查：
> **反向实证**：用全新数据（ZZ001–ZZ010、金额 100/300/600、阈值 0.06、日期 2031-12-31）跑 CLI，输出全部按入参正确计算——**证明计算是真实输入驱动的**

比"grep 没有硬编码"强得多。4 条 low 级 findings 均准确（"实现严于测试的防御分支"）。

---

## 五、专项注入测试（你要求的方法论修正）

**关键认知**：此前的"ask 重发 = 0"是**空真**（访谈被秒回，等待窗口从未出现）。本次让等待真实发生：

**配置**：`PI_INTERCOM_ASK_TIMEOUT_MS=12000`，父会话**全程不回复**，最小 greenfield fixture。

| 断言 | 期望 | 实测 | 判定 |
|---|---|---|---|
| A. `interview_request` 恰 1 次，无重发 | 1 | **1** | ✅ |
| B. `progress_update == 0` | 0 | **0** | ✅ |
| C. 终局 = PlanHandoff + `blocked_on_interview` | 是 | **`{round:1,questions_count:4,outcome:"timeout_no_ruling",resume_instruction:"..."}`**，9KB 完整载荷，state=**completed** | ✅ |
| D. 耗时有界 | ~窗口 | **257s**（有界，未挂死） | ⚠️ 部分：**"≈窗口"不成立**，建议重述为"有界" |
| E. 迟答复重派复现问题 | — | **0 次重问**；D1–D4 全落地；`interview_log` 重放成功 | ✅ |

**决定性证据**（证明不是空真）：
```
toolName:"contact_supervisor", isError:true, text:"Timed out waiting for supervisor reply."
```
超时**确实**以工具错误返回（与事故诱发重试的机制**完全相同**），但 PLAN **不重发、不空转，直接按契约终局**。

**n=1**（一次有效运行；另一次因 fixture 缺陷作废，见 §6-G4）。

---

## 六、独立对抗性审查（三轮）

| 轮次 | Reviewer 判定 | 关键产出 |
|---|---|---|
| 1 | **BLOCK**（15 项发现） | 抓到无界访谈回路、state 不自足、计数器无增量定义、dag 漂移无约束；**F2 为其事实错误**（我证伪） |
| 2 | **BLOCK 收窄** | 抓到 **N2 = 我的真实失误**（批量 edit 原子回滚 → 声称修了但文件里没有）；**N1 = 我引入的新矛盾**（三计数器重叠） |
| 3 | **可放行（附条件）** | 文件直读核实全部修复；放行条件 R1/R2 + 随行 R3–R5 |

### 三轮审查的净收益

1. **修复了我的真实失误**：批量 `edit` 因一处匹配失败而**整批原子回滚**，但我的清单报了"已修复"——若无它通读文件，F7/F9/F12 会带着"已修复"标签留在文件里
2. **修复了我引入的新矛盾**：我修 F3/F4 时造出三计数器重叠，其中"**3 次 429 → 误触发最贵 REPLAN**"是实质成本回归
3. **Reviewer 自纠事实错误**：F2 假阴性（目录级 grep 静默跳过）→ 确立纪律"**否定性结论必须以直接文件访问复核**"
4. **双方共守的纪律**：**修复清单不可作为合并依据，必须以文件为准**

### 端到端暴露的协议缺口（G1–G5）

| # | 缺口 | 证据 | 修复 | 验证 |
|---|---|---|---|---|
| **G1** | 无授权例外通道：授权修正在机械核查面上**与作弊不可区分** | GATE V2（advisor +4、report 1±1） | state 增 `authorized_test_edits` + "**裁决即记录**"纪律；GATE #3 改**先查授权再判违规** | ✅ 正例 PASS / 反例仍抓 |
| **G2** | 无"生命周期提交"归属：父会话自身提交在映射表无归属 | GATE V1（我的 `.gitignore` 越界） | state 增 `orchestrator_commits`；GATE #2 已登记放行 | ✅ 同 |
| **G3** | 映射表 #3→FIX_EXECUTE 与 EXECUTE 禁令"**不改测试**"直接冲突 → **死锁** | 推演 `/tmp/deadlock-probe/probe.md` | FIX_EXECUTE 加"若修复需改测试则**不得** FIX_EXECUTE，改判 REPLAN/HALTED" | ✅ 死锁闭合（二重兜底） |
| **G4** | PLAN 只读探索**被无关噪声捕获**（无硬边界） | 注入 run0：20 次 pytest 排查 → 600s 超时失败 | SKILL.md + plan.md **双写**探索边界 | ✅ **行为回归**（见下） |
| G5 | 测试协议缺陷需人工裁决 | T3/T4 各一次 | 无需修复（正常流程，但需授权留痕） | — |

### G4 行为回归（最强的一条验证）

| 指标 | run0（修复前） | g4-regress（修复后） |
|---|---|---|
| bash 调用 | **20**（全部 pytest 排查） | **2**（仅 `--version` / `git status`） |
| `pytest_calls` | 反复执行 | **0** |
| 结局 | **600s timeout → failed** | **completed**，完整 PlanHandoff |
| cost | $0.2516 | **$0.1135** |

**PLAN 的 `ambiguities` 原文**（证明它引用了条款并遵守）：
> "既有环境噪声（**一次性记录，按边界条款不追因，不阻塞规划**）：tests/test_env_noise.py 依赖环境变量 SOME_LEGACY_FLAG=1... 影响：全量 pytest 本底为红，与本次交付无关，故 test_command 仅指向新增测试文件。"

三项要求全部满足：**停止调查**（读到噪声文件但零 pytest）→ **记录一次** → **不阻塞规划**。

---

## 七、投产前置条件与未闭合项

### 投产前置条件（3 项，必须满足）

| # | 条件 | 原因 |
|---|---|---|
| **C1** | **每次加载 profile 后核验 `plan` override 仍在** | 实测：`paid.json` profile 曾**静默删除** `plan` override → PLAN 会回落到 `defaultModel`(=flash)，违反"规划档位不得降级"。建议：把 override 同时写进各 profile，或在使用前用一行命令核验 |
| **C2** | **首次真实运行需人工全程盯守** | 本次验证在 fixture（greenfield + 单一任务）；真实项目的复杂度、既有测试规模、state 恢复路径均未验证 |
| **C3** | 启动前 `export PI_INTERCOM_ASK_TIMEOUT_MS=3600000` | 默认 10m 会在长访谈中误超时（协议已适配"超时即终局"，但会多一轮重派） |

### 未闭合项（诚实清单）

| # | 项 | 影响 | 建议 |
|---|---|---|---|
| U1 | **D 断言措辞**："耗时 ≈ 超时窗口"不成立（实测 257s） | 文档不准确 | 重述为"**有界**" |
| U2 | **原噪声未复现**：run0 的 pycache 污染在最小 fixture 中**无法稳定重现** | G4 验证用的是同类但不同的噪声源 | 标注为已知局限；G4 条款针对"无关故障"这一类，非某一具体形态 |
| U3 | **未在真实项目验证**（fund-tracker 仍未恢复） | 结论不可直接外推 | 首次真实运行盯守（C2） |
| U4 | **多数结论 n=1** | 概率性行为（prompt 级）可能不稳定 | 关键路径（ask 终局、探索边界）建议再跑 2–3 次 |
| U5 | **GATE 的 V1/V2 判定依赖人工** | 授权与越界的区分需人判断 | 已通过 `authorized_test_edits`/`orchestrator_commits` 部分机械化；完全机械需 PlanHandoff 侧约定 |
| U6 | **协议缺"探索预算"硬上限** | G4 靠措辞（实测有效但非结构强制） | 观察；若复发，再考虑工具面收紧 |
| U7 | thinking 档位对比非受控（不同票任务量不同） | 无法量化 thinking 的独立贡献 | 如需结论，做同任务两档对照 |

---

## 八、给用户的建议路径

**建议：先做一次"试点运行"而非直接投产。**

1. **准备**（5 分钟）
   - 核验 `plan` override 存在（C1）
   - `export PI_INTERCOM_ASK_TIMEOUT_MS=3600000`（C3）
   - `/reload` 使配置生效

2. **试点**（推荐 fund-tracker，你原本暂停的真实任务）
   - 你全程盯守（C2），重点观察：PLAN 首轮访谈是否收敛、`needs_research` 是否触发、state 恢复路径
   - 若 PLAN 发起访谈 → **正常回答**（这是设计行为，不再是故障）

3. **试点后**
   - 把观察到的偏差补进 skill（过 gate）
   - 修 U1（一行措辞）
   - 再决定是否常态化使用

---

## 九、方法论层面的三条收获

1. **"空真"识别**：`ask 重发=0` 看似通过，实为**等待窗口从未出现**。你指出的这一点，把一个假阳性变成了真证据——**验证必须让被验证的条件真实发生**。
2. **"修复清单 ≠ 交付物"**：三轮审查中，reviewer 坚持"以文件为准"抓出了我"批量 edit 原子回滚但报成功"的失误。授权与修复都必须**落盘留痕**，否则与未发生无异。
3. **审查的价值在抓错，不在确认**：三轮中真正有价值的是两个**我自己看不见的失误**（批量回滚、我引入的计数器矛盾），而非任何"看起来没问题"的确认。

---

## 附：证据文件索引

| 内容 | 路径 |
|---|---|
| 端到端报告 | `/tmp/e2e-summary.md` |
| GATE 证据（含两个违规） | `/tmp/e2e-pipeline/handoffs/gate-evidence.json` |
| 注入测试 verdict | `/tmp/inject-min/verdict.md` |
| 死锁推演 + 缺口分析 | `/tmp/deadlock-probe/probe.md` |
| 归因更正（pytest 9 说法证伪） | `/tmp/e2e-final-fix.md` |
| G1–G4 句级审计 | `/tmp/g1g4-audit.md` |
| 语义基线（39 原子） | `/tmp/refactor/semantic-inventory.md` |
| 审查修复记录（三轮） | `/tmp/reviewer-round1-fixes.md` |
| 全部备份 | `/tmp/backup-*.{md,json}`、`/tmp/bk-*.md` |