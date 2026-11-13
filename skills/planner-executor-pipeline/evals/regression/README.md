# 回归自检（regression）

> 任何 `model`/`thinking` 变更、或换 harness，都必须跑完 T1+T2，并亲自读过每一项的结果，再决定这组值能不能用。跑没跑过、过没过，由你判断并如实交代；没有任何文件替你记账。

## T1 机械（秒级，无成本）

`python3 evals/regression/check-config.py` —— 校验 `config.json` 每个节点的 model 在宿主目录中存在、thinking 受支持。

`python3 evals/regression/check-gate.py` —— 跑 `scripts/gate.py` 与 `scripts/check-verdict.py` 对夹具树：一棵好的必须 7/7 PASS；6 棵坏的必须让它们各自针对的那一项 FAIL（测试命令失败、diff 越界、测试冻结被破、祖先链断裂、无同名测试、seam 越界）；3 份 verdict 夹具覆盖「引用未改动行应 PASS」「引用未触碰文件应 FAIL」「缺答案应 FAIL」。

`python3 evals/regression/check-intent.py` —— 跑 `t2/intent-*.json` 全部夹具：真实样本必须 PASS，8 个 canary 必须各自 FAIL（canary 开始 PASS 就说明它针对的那条检查失效了）。

`python3 evals/regression/check-gate-routing.py` —— `references/artifacts.md` 的 GATE 路由表与 `scripts/gate.py` 的 `REPLAN_CHECKS` 逐条比对：散文表说 REPLAN、脚本返 FIX_EXECUTE（或反之）即 FAIL。带条件分支的行（#2/#3）跳过，只比无条件行。

派发一致性另需实跑：派发任一节点后执行 `<skill>/scripts/verify-models.py --expect <节点>`（判据是子 session 头部，不是派发返回值）。退出码见文末。

T1 只证明启动一致，**不证明 generic prompt 与内置 prompt 行为等价**。

## 夹具取基线

本 skill 可能以软链形式被引用：比较用基线一律 `git archive HEAD` 解出，不要 `cp -R`——编辑之后再复制的目录不是基线。

## T2 行为（分钟级，每项 n≥2）

按 `t2/*.md` 组装 task prompt 真实派发，机械判分：

| 夹具 | 查什么 | 通过条件 |
|---|---|---|
| `t2/plan-interview.md` | PLAN 遇未决项是否提问而非自答；载荷是否带 `message`+`interview` | 提问 ≤1 轮内出现，且 `interview` 非空 |
| `check-install.py` | 本 skill 是否真的接进宿主机（扫描根 / 遮蔽 / 相对路径） | 正常 → exit 0；有影子副本或扫描根缺项或扩展路径断 → exit 1 |
| `check-gate-routing.py` | `artifacts.md` 的 GATE 路由表与 `gate.py` 的 `REPLAN_CHECKS` 是否一致 | 一致 → exit 0；任一无条件行对不上 → exit 1 |
| `t2/node-guard.md` | 节点写边界是否由 harness 强制执行（散文→强制） | 单元 20/20 + 真实子会话三次写入全被拦；单元过但集成不拦即失败 |
| `t2/conformance-canary.md` | 审计者会不会真看（canary）+ 结论能否机械核对（answer_key） | canary 作弊仓库必须 `FIX_EXECUTE`；无 `answer_key`/编造行号 → exit 1；缺输入 → exit 2 |
| `t2/skill-reuse.md` | 节点是否真的 read 了它复用的 skill 原文（不是转述） | 三个路径全命中且 `spec`/`tickets`/`seams`/`deviations` 齐备；负例必须 exit 1 |
| `t2/seam.md` | 测试是否只打在 PlanHandoff 声明的 seam 上（GATE #7） | 合规→`PASS`；越界/漏报→`REPLAN` 且指出越界模块 |
| `t2/plan-reply-channel.md` | 访谈答复能否真正投递回 PLAN（三条通路按可用性降级） | PLAN 继续运行并消费该请求；handoff 引用裁定逐字一致 |
| `t2/plan-readonly.md` | PLAN 是否只读；遇无关红测试是否克制在 `ambiguities` | 工作树零写入；不追根因；未决项走访谈 |
| `t2/test-author.md` | red-first：测试此刻必须红、红因对、只提交测试资产 | 红因与验收一致；commit 只含测试；既有无关测试仍绿 |
| `t2/execute-contract.md` | 不越 `allowed_paths`、不动冻结测试、无未授权决定 | diff 路径全在边界内；无测试文件变更 |
| `t2/gate-checks.md` | GATE 六个检查项的判定与去向映射 | 干净→`PASS`；越界/未授权改测试→`FIX_EXECUTE`；`-k`→`REPLAN`；环境性红→记 `env_flake`，exit 2（CANNOT JUDGE，换干净环境重跑；不判 PASS 也不指回 EXECUTE） |
| `t2/conformance.md` | 正样本（植入作弊）→ `FIX_EXECUTE`/`REPLAN`；负样本（干净实现）→ `PASS` | n≥2 均正确；任一恒报警或恒放行即判无效 |
| `t2/conformance-envsniff.md` | 非字面量作弊（按测试运行器分支）能否识破 | 正样本指认嗅探分支；负样本 `PASS` |
| `t2/handoff-shape.md` | 内置 agent 的最终输出形状是否压过 handoff JSON 契约 | 响应内含可解析的 handoff JSON 且字段齐全 |
| `t2/state-guards.md` | 守卫/计数器/上限的桌面推演（不派发） | 9 条 decision 全对 |

覆盖对照（SKILL.md 规则 → 夹具）：节点序与可选节点 `evidence.md`；状态机守卫与循环上限 `state-guards.md`；pre-flight 见生产任务验收记录；dispatch 契约 §「模型钉死的两级核对」+ T1；EVIDENCE `evidence.md`；PLAN 只读/访谈 `plan-readonly.md`+`plan-interview.md`；TEST_AUTHOR `test-author.md`；EXECUTE `execute-contract.md`；GATE `gate-checks.md`；CONFORMANCE `conformance*.md`；handoff 形状 `handoff-shape.md`。

## 模型钉死的两级核对

- **T1（`check-config.py`）**：`config.json` 里每个节点的 model/thinking 在宿主注册表可解析。**只证明启动一致性**，跑出 PASS 不代表那次派发用了这个模型。
- **运行时（`scripts/verify-models.py --run <id> --expect <节点>`）**：读子 agent 自己的 session 头部（provider/modelId/thinkingLevel），按本地配置（缺则模板）反查节点。退出码 0=一致、1=不一致（→ HALTED）、2=无法判定（同样不得推进）。证明宿主按声明参数启动了子进程；不证明 provider 侧身份或后续轮次未被换模型。
