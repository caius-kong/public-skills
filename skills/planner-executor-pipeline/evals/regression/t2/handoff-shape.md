# T2 / handoff 形状冲突

背景：内置实施/审计 agent 的系统提示各自规定了最终输出的形状，而 handoff JSON 契约写在 task prompt 里。

任务：任取一个产 handoff 的节点派发一次。

通过条件（n≥2）：最终响应中**同时**存在该 agent 的自然语言结论与可解析的 handoff JSON，且 JSON 字段齐全（不因系统提示的输出形状而丢字段）。
