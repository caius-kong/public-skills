# 长任务 coding agent 工作流评估

## 总结
该流水线与业界共识的核心交集是：拆解任务、隔离上下文、用结构化工件交接、让确定性工具承担验证，并由编排器控制长程状态。它比“单 agent 一口气写完”更接近 Anthropic、OpenAI、Cognition 的生产实践。分歧在于它把流程过度固定化：严格红测/三次上限/纯 prompt 状态机并非普适最佳实践；业界通常保留动态重规划、持久化检查点和人工介入，且验证不应只查“空壳/硬编码”。

## 六项逐一判定
1. **五阶段流水线：Mixed（偏 aligned）。** Anthropic 的长程 harness 明确采用 planner、generator、evaluator，按 feature/sprint 工作，评估器用真实 UI/API/数据库验收；OpenAI 也建议 depth-first 拆成 design、code、review、test。故 Plan→Execute→独立 Gate 合理；但 Anthropic 后续发现更强模型可减少 sprint/evaluator，说明固定五阶段不是共识。Conformance 仅查作弊属于必要反欺骗层，不等于充分质量审查。来源：[Anthropic harness](https://www.anthropic.com/engineering/harness-design-long-running-apps)、[OpenAI harness](https://openai.com/index/harness-engineering/)。

2. **fresh context + JSON handoff：Aligned。** Anthropic 发现长任务需 context reset 加结构化 handoff；其 agentic coding 以文件通信，避免上下文焦虑和“电话游戏”。Anthropic multi-agent research 也让子 agent 独立探索、返回压缩结果。Cognition 的 Agentic MapReduce 使用 bounded shard 的 fresh child session。注意：fresh 不是永远优于继承；强模型可用 compaction/连续会话，且 handoff 丢失细节是已知风险。来源：[Anthropic context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)、[Anthropic harness](https://www.anthropic.com/engineering/harness-design-long-running-apps)、[Cognition MapReduce](https://devin.ai/blog/agentic-map-reduce)。

3. **状态机、replan/attempt 上限、fail-closed：Mixed（原则 aligned，数值非共识）。** LangGraph 将 checkpoint 用于恢复、容错、人工介入；确定状态和失败恢复是业界标准。Cognition 强调大任务拆为隔离 session、验证机制。≤3 是可审计的本地策略，但没有证据表明三次适用于所有任务；固定上限可能截断可恢复工作，宜允许人工批准/按失败类型动态预算。来源：[LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)、[Cognition 使用 Devin](https://cognition.com/blog/how-cognition-uses-devin-to-build-devin)。

4. **测试冻结、独立 Gate：Aligned（但测试策略 Mixed）。** 独立重跑、diff 范围核查、不信任自报，符合 OpenAI“环境/工具/验证机制”优先和 Anthropic evaluator 真实操作的思想；测试不可由执行者改绿也符合可重复评测。可是红测黑盒不能覆盖非功能、安全、回归和错误测试本身；Gate 应包含静态检查、类型、集成/安全和人工抽样。来源：[OpenAI harness](https://openai.com/index/harness-engineering/)、[Anthropic harness](https://www.anthropic.com/engineering/harness-design-long-running-apps)。

5. **轻模型 worker、旗舰仅 Plan：Divergent/未充分证实。** 官方资料支持按专门任务路由子 agent、控制成本（Claude Code subagents）；但 Anthropic 指出模型能力会改变 evaluator 和 reset 的收益，Cognition 也报告模型升级显著改变 multi-hour 架构。把旗舰限制在访谈是成本优化假设，不是行业最佳实践；应按任务风险、工具调用、验证失败动态升级。来源：[Claude Code subagents](https://docs.anthropic.com/en/docs/claude-code/sub-agents)、[Cognition Sonnet 4.5](https://cognition.com/blog/devin-sonnet-4-5-lessons-and-challenges)。

6. **纯 prompt 编排、无代码依赖：Divergent。** 概念上 prompt loop 可原型化，但生产长任务通常需要可持久化状态、重试、并发、权限和恢复。LangGraph 以 checkpointer 实现这些能力；OpenAI Agents SDK 明确提供 runtime loop、state、handoff；Cognition 的 MapReduce 把选择/分片做成确定性步骤。固定命令提取状态提高可读性，却不能替代原子写入、崩溃恢复和并发一致性。来源：[LangGraph checkpointer](https://docs.langchain.com/oss/python/langgraph/checkpoints)、[OpenAI Agents SDK](https://openai.com/index/introducing-the-agents-sdk/)、[Cognition MapReduce](https://devin.ai/blog/agentic-map-reduce)。

## 业界对照与总评
Anthropic、OpenAI、Cognition 的共同模式是“高层计划→小而可验证的工作单元→外部工件/记忆→确定性或独立验证”，并允许按模型能力调整脚手架。LangGraph/Agents SDK 则把 durable execution、checkpoint、人工门禁视为运行时基础，而非 prompt 约定。该设计在上下文工程和隔离交接上高度 aligned，在独立验证上方向正确；主要偏离是把动态策略硬编码为五阶段、三次上限、固定模型矩阵，并以 prompt 模拟生产状态机。建议保留 fail-closed 和审计性，但加入持久化 checkpoint、人工 override、按失败类型重规划、风险分级模型路由，以及超越反作弊的语义/安全/回归验证。

## 矛盾与缺失证据
未发现来源直接支持“≤3 次”或“旗舰只做 Plan”。也未找到足够公开、可比的证据证明纯 prompt 编排在崩溃恢复、并发和大规模代码库上优于代码化运行时；上述两点应视为待测假设。

## 主要来源
- Anthropic，《Harness design for long-running application development》—最直接的 planner/generator/evaluator 与 context reset 实验。
- Anthropic，《Effective context engineering》—compaction、结构化笔记、fresh subagent 的上下文原则。
- OpenAI，《Harness engineering》—depth-first 拆解与环境/验证优先。
- LangGraph Persistence/Checkpointers—durable execution、恢复和人工介入的一手文档。
- Cognition，《Agentic MapReduce》—确定性选择、bounded shard、fresh worker 的生产架构。
