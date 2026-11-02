# 研究：模型路由经济学与编排确定性

## 总结
该流水线在“按角色分配模型、结构化交接、确定性门禁、失败即升级/停机”上与长任务 agent 的主流工程方向高度一致；尤其是轻模型承担重复执行、父进程独立验证，符合成本—可靠性分离原则。但“旗舰只用于 Plan”不是普适最佳实践：路由研究表明应按任务难度及可观测质量动态升级。纯 prompt 循环可做原型，却牺牲持久化、幂等、可重放和可观测性；生产长任务通常代码化状态机。

## 六项对照
1. **五阶段、Gate/Conformance 分离：Aligned（高）**。LangGraph 官方明确主张在同一图中混合确定性步骤与 LLM 步骤，并提供持久执行和人工介入；这支持“LLM 产出、确定性 Gate 验证”的分工。[LangGraph Overview](https://docs.langchain.com/oss/python/langgraph/overview)（直接证据）。但 Conformance 仅查空壳/硬编码，覆盖面窄；Artificial Analysis 的 coding-agent 评测包含真实仓库、终端操作及二进制 verifier，且指出不同任务能力不等价。[Coding Agent Index](https://artificialanalysis.ai/agents/coding-agents)（直接证据）。因此流程结构对，验证语义需扩展。

2. **fresh context + JSON handoff：Mixed（中高）**。结构化状态、节点边界和持久恢复是工业编排常见做法；LangGraph 的 checkpoint/interrupt 支持恢复并避免重跑已完成任务。[Functional API](https://docs.langchain.com/oss/python/langgraph/use-functional-api)（直接证据）。但其官方也强调恢复时节点会从头执行，副作用必须幂等。[Human-in-the-loop](https://docs.langchain.com/oss/python/langgraph/graph-api.md)（直接证据）。fresh context 降低上下文污染，却丢失隐性事实；JSON 契约必须带版本、证据、错误和幂等键，而非只传摘要（研究者推论）。

3. **replan/attempt 上限，缺载荷即 fail-closed：Aligned（高），但阈值非共识**。固定预算、递归上限和 HALTED 能防止无限循环；LangGraph 暴露 recursion limit，并建议在达到上限前优雅降级。[Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api.md)（直接证据）。≤3 是产品策略，不是行业标准；应按任务类型、成本和失败原因校准（推论）。

4. **测试冻结、独立 Gate 重跑：Aligned（高）**。独立 verifier 与“不信任 agent 自报”直接契合 Artificial Analysis 的做法：attempt 即使干净完成，未满足 verifier 仍计零，并使用 pass@1/真实执行结果。[Methodology](https://artificialanalysis.ai/methodology/coding-agents-benchmarking/)（直接证据）。冻结测试防止 reward hacking；但仅 diff 范围核查不能替代安全、依赖、回归和集成测试（推论）。

5. **轻 worker + 满档 thinking，旗舰仅 Plan：Mixed（中）**。成本/质量按模型和设置显著变化；Artificial Analysis 同时报告 pass、token、API 成本和运行时间，并警告结果是“agent variant”而非裸模型。[Coding Agent Index](https://artificialanalysis.ai/agents/coding-agents)（直接证据）。cascade-routing 论文证明级联可改善成本—质量，但关键是事前难度估计和事后质量估计；其 SWE-Bench 实验最高提升 14%。[A Unified Approach](https://arxiv.org/html/2410.10347v3)（直接证据）。因此“便宜优先、失败升级”合理；“旗舰只访谈”过硬，复杂 ticket、失败修复或低置信审查也应可升级。OpenAI Cookbook 的路由示例亦把任务送往能处理它的最便宜模型，并计入路由器开销。[Model routing](https://github.com/openai/openai-cookbook/pull/2811)（直接证据）。

6. **纯 prompt 编排 vs 代码化：Divergent（中高）**。prompt 定义状态机便于零依赖移植、快速试验；但工业运行时强调 durable execution、持久状态、人审和可恢复性。[LangGraph Overview](https://docs.langchain.com/oss/python/langgraph/overview)（直接证据）。官方还要求 interrupt 前副作用幂等，说明这些性质需运行时保证而非文字约定。[Human-in-the-loop](https://github.com/langchain-ai/langgraph/blob/main/docs/docs/concepts/human_in_the_loop.md)（直接证据）。固定命令+JSON 可模拟纪律，却难可靠保证并发、锁、崩溃恢复、审计和注入防护（推论）。

## 业界对照与总评
共识交集：角色化模型、成本感知路由、级联升级、结构化状态、独立 verifier、人工/确定性门禁，均有工程或研究支持。主要分歧：行业更倾向“代码化 durable graph + LLM 节点”，而非全 prompt；路由通常由质量信号动态决定，不把旗舰永久限定在规划。该设计适合作为受控、低并发原型或强命令环境；若用于生产长任务，应把状态机、锁/重试、幂等、checkpoint、遥测和策略化模型升级移入代码，并以本组织任务集测量成本—成功率 Pareto，而不能仅凭模型档位假设省钱。

## 矛盾与缺失证据
- 未发现支持“旗舰只做 Plan”这一普适规则的证据；现有研究反而强调质量估计与后验升级。
- 尚无该具体 prompt pipeline 的端到端成本、成功率、恢复时间或并发实验；≤3 次上限、满档 thinking 的收益仍未验证。

## 来源取舍
- 保留：LangGraph 官方文档（生产编排原理）；Artificial Analysis（端到端 coding agent 成本/质量方法）；Cascade Routing 论文（路由/级联实证）；OpenAI Cookbook（实际路由范式）。
- 降权：营销性博客/社媒材料，未作为关键结论依据。

## 下一步
用真实 ticket 做固定预算 A/B：全旗舰、全轻模型、轻模型级联升级、当前六阶段；记录每票成本、pass@1、重试率、升级准确率、Gate 漏报及恢复时间。