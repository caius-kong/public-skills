# T2 / 节点是否真的复用了既有 skill（而不是转述它）

本 skill 只做编排：每个阶段的流程来自它复用的那个 skill 的原文。转述和原文在产物上看起来一模一样，所以判据只能取证据链 —— **transcript 里有没有用 read 打开过那个文件**。

任务：给 PLAN 一份已定 brief（决策都已收敛，只剩 seam/切片确认），派发后检查：

```bash
python3 evals/regression/check-skill-reuse.py --transcript <child>_plan_transcript.jsonl --expect grilling,to-spec,to-tickets
```

通过条件（n≥1）：

- 退出码 0：三个 skill 文件都被 read 过**且顺序正确**（`tool_start` 记录里 `argsPayload.path` 以 `/<name>/SKILL.md` 结尾；`argsPreview` 只有 ~56 字符，长路径会被截断，不能用作判据）；
- 退出码 1（负例：`--expect grilling,code-review`）证明检查有区分力，不是恒 PASS；
- 退出码 2 只在 transcript 缺失或无工具记录时出现 —— 崩溃绝不能读成通过。
- 产物侧：`spec` 段按 to-spec 模板的六节组织；`tickets` 是垂直切片并带 blocking edges；`seams` 与 `deviations` 齐备。
- 行为侧：**不重问 brief 已定项**（grilling 的 frontier 语义），每个问题带推荐答案且「是」即接受。

事实（2026-10-23 更新）：`grilling` 上游**未**隐藏，`to-spec` / `to-tickets` 隐藏。pi-subagents 在 `buildSkillInjection` 收口处硬过滤隐藏 skill，`skills:` 点名也送不进去 —— 所以本 skill 为后两者提供 `skills/` 镜像（body 逐字节等于上游，只去掉隐藏标记），并在 `agents/plan.md` 里 `skills:` 点名三个、`skillPath` 加上 `../skills`。

实测（2026-10-23）：PLAN 的 `<available_skills>` 里出现 `planner-executor-pipeline / grilling / to-spec / to-tickets` 四项；随后按 grilling → to-spec → to-tickets 顺序 read 三者（transcript 证据见 `check-skill-reuse.py` 正例 exit 0，乱序/缺失负例 exit 1）。
