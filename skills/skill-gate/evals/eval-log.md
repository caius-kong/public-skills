# eval-log

## Round 1（2026-11-03）— 外部依赖约束的双臂验证

**问题**：给 skill-gate 加了一条硬约束（引用别的 skill 必须声明已安装路径 + 安装命令、禁止 vendor 副本、必须过路径检查）。这条约束值不值得留？

**预注册判据**（跑之前写死）：受审对象是一个引用了 `bar`、无 `## Preflight`、把 `bar` 逐字节 vendor 进自己目录的 skill `foo`。WITH 臂必须**同时**指出「缺 Preflight」与「vendor 副本」并判 iterate；WITHOUT 臂（`993b0123^` 的旧版）若也同时指出，则该约束冗余、应删。

**第一轮作废**：夹具把副本放在 `skills/bar/`（foo 的兄弟），而正文写 "in this skill"。两臂都去查"路径不存在"，测的不是那条约束。夹具错，eval 不算数——重做。

**第二轮（修正夹具后）**：

| 臂 | 结论 | 是否点名「缺 Preflight」 | 是否点名「vendor 副本」 |
|---|---|---|---|
| WITH | iterate | **是**（引用硬约束逐子句判定） | **是**（`diff` 证明逐字节一致） |
| WITHOUT | iterate | **否** —— 明说"本规程下不可引用为违规" | 只批了那句 rationale 与指令矛盾，没把 vendoring 本身判为违规 |

**判定：约束保留。** 判据是"点名哪类违规"而非最终结论——两臂都判 iterate，因为夹具还带了别的问题。差别在于 WITHOUT 说不出这条规则，只能绕道 delete-test 与指令矛盾；换一个没有那些附带问题的变体，它就会放行。

**代价**：4 次 worker 调用（含作废的第一轮），模型 `trendmicro/deepseek-v4.1-flash @high`，实际花费约 $0.05。
