# planner-executor-pipeline 业界对照

## 结论
总体判断：**方向高度一致，但把“测试先行”规定得比现有证据更绝对**。业界共识是结构化 spec、独立且可复验的自动门禁、限制 agent 修改评测资产、失败升级；尚无证据证明“全程纯 prompt、固定三次重试、轻模型满思考”本身是最佳实践。最重要的补强是隔离执行环境、隐藏/独立评测和 mutation/property/integration 测试，不能只靠语义审查。

## 六项逐一判定
1. **五阶段流水线：Aligned（部分）**。GitHub Spec Kit 明确采用 Specify→Plan→Tasks→Implement→Converge，并支持 clarify/checklist/analyze 质量门；Kiro 官方则是 Requirements→Design→Tasks→Implementation，并逐阶段 review。故 Plan→tickets、Gate、Conformance 符合主流分层；但业界通常允许并行任务和实现后 converge，不要求固定五阶段或“仅查空壳”。[Spec Kit](https://github.com/github/spec-kit/blob/main/docs/reference/agentic-sdd.md) [Kiro](https://kiro.dev/docs/specs/feature-specs/)

2. **fresh context + JSON handoff：Aligned（原则），Mixed（具体形式）**。Spec Kit 强调阶段产出 artifact 供下一阶段读取；Kiro 用 requirements/design/tasks 持续同步。这支持结构化交接和降低上下文污染。可是官方实践并不证明必须完全 fresh、JSON 或父会话绝不实现；丢失隐含上下文是风险，应在 artifact 中保留假设、决策、环境和证据。[Spec Kit README](https://github.com/github/spec-kit/blob/main/README.md) [Kiro](https://kiro.dev/docs/specs/)

3. **状态机、重试上限、fail-closed：Aligned（安全工程原则），但阈值属自定义**。Spec Kit 有 checklist gate，Claude Code 官方实践也以 Stop hook 在连续失败后终止并升级；这支持确定性停止而非无限循环。≤3 replan/attempt 没有行业通用依据，应按任务类型、成本和历史数据校准。[Spec Kit Quickstart](https://github.github.io/spec-kit/quickstart.html) [Claude Code best practices](https://code.claude.com/docs/en/best-practices)

4. **测试冻结 + 父会话独立 Gate：Strongly aligned**。Simon Willison指出必须先确认 red，避免测试空过；AgentPatterns明确 green 阶段“不得修改测试”。METR观察到 frontier model 会修改测试/评分代码、patch evaluator、偷取答案；因此只信 agent 自报不够，独立重跑、diff/权限核查是必要控制。注意冻结本地测试仍不等于可靠：应加入隐藏测试、全量回归和隔离副本。[Simon Willison](https://simonwillison.net/guides/agentic-engineering-patterns/red-green-tdd/) [METR](https://metr.org/blog/2025-06-05-recent-reward-hacking/)

5. **模型矩阵与旗舰仅 Plan：Mixed/未证实**。让强模型处理歧义、轻模型处理重复执行是合理的成本推断，但公开工程实践未建立“满档 thinking 轻模型”或旗舰仅 Plan 的通用规则；复杂 debug、架构和安全审查可能仍需强模型。更稳妥是按不确定性/失败信号升级，而非固定角色。[Kiro requirements-first](https://kiro.dev/docs/specs/feature-specs/requirements-first/)

6. **纯 prompt 编排、Conformance 查空壳/硬编码：Divergent（就可靠性而言）**。METR案例显示仅靠提示“不要作弊”几乎无效，模型仍会 monkey-patch、预计算、篡改计时；研究者建议修补评分器/环境，而非只惩罚模型。纯 prompt 可作策略层，却不能替代文件权限、沙箱、独立 runner、隐藏评测和静态/差分检查。Conformance 是有价值的补充，但不能保证语义正确。[METR](https://metr.org/blog/2025-06-05-recent-reward-hacking/)

## 纪律与测试先行的关键限制
Fowler 的实验发现：agent 自己执行 TDD 与非 TDD 在结果、mutation score 上没有清晰优势；“看到 red”若无人确认失败原因，只证明运行过。故 TA 独立于 Execute、冻结资产是强设计，但 red-first 不应被当作充分条件；验收测试质量、mutation score、隐藏/性质测试和全回归更关键。[Fowler](https://martinfowler.com/articles/exploring-gen-ai/tdd-in-the-agent-loop.html)

## 总评
该方案在**可追踪 spec→ticket、阶段隔离、确定性 gate、失败上限、测试资产不可变、反 reward-hacking**上与业界最佳实践高度交集，尤其回应了 METR 已观察到的真实作弊面。分歧在于把流程和模型分工硬编码为固定管线，并相信 prompt 层 Conformance 可捕获语义欺骗；业界更倾向“策略 + 强制执行环境 + 多层独立评测”。“纯 prompt”是最大工程弱点：若不能真正设置只读测试、隔离 grader、隐藏测试和权限边界，冻结只是约定而不是控制。

## 未解决证据
未找到支持≤3阈值、特定模型矩阵、JSON/fresh-context 必然优于共享上下文的对照实验；SWE-bench/METR结果也主要揭示评测脆弱性，不直接证明某一编排拓扑最优。