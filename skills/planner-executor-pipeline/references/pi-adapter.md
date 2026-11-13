# pi 适配层（pi-adapter）

> 由 `SKILL.md` 按需加载：在 pi 上派发节点，或把本 skill 移植到其它平台时读取。换平台时整层替换。

> 准入不变量：本层只描述**怎么实现**。出现"用什么模型/什么档位/什么约束"即越界——那属 `SKILL.md` 的 dispatch 契约与 `config.json`。

## 节点 ↔ agent ↔ 守卫

节点专用的 agent 定义就放在本 skill 的 `agents/` 下，跟着 skill 走（而不是散在 `~/.pi/agent/agents/`）：

| 节点 | agent 定义 | `subagentOnlyExtensions`（相对 agent 文件的路径） |
|---|---|---|
| PLAN | `agents/plan.md` | `../extensions/plan-interview-channel-timeout.js` + `../extensions/guard-plan.js` |
| EVIDENCE | `scout` / `researcher`（内置） | `guard-evidence.js`（在 override 里点名） |
| TEST_AUTHOR | `agents/test-author.md` | `../extensions/guard-test-author.js` |
| EXECUTE | `agents/executor.md` | `../extensions/guard-execute.js` |
| CONFORMANCE | `reviewer`（内置） | 无（本就没有写工具） |

`skillPath: ..` 让 agent 从 skill 根解析 `skills:`；`subagentOnlyExtensions` 的相对路径按 agent 定义文件解析。

**要让 pi 看见 `agents/` 必须配一次扫描根**（`~/.pi/agent/settings.json`）：

```json
"subagents": {
  "agentScanDirs": ["~/.pi/agent/skills/planner-executor-pipeline/agents"]
}
```

注意优先级：固定的 `~/.pi/agent/agents/` **高于**扫描根，所以旧的同名定义必须删掉，否则扫描根里的版本永远不会生效。

`test-author` 与 `executor` 必须是两个独立定义，不能共用一个 `worker`：守卫策略按 agent 绑定，而拒绝写测试与只写测试是相反的边界。

守卫的单元夹具：`node evals/regression/check-node-guard.mjs`（正/负例各若干，纯本地、零模型调用）。

**契约后果（实测）**：TEST_AUTHOR 的守卫只开放 `allowed_paths` 里的**测试路径**，所以 PLAN **必须把 TA 将要创建的测试文件逐个写进 `allowed_paths`**——写新文件（如 `tests/test_x_new.py`）而契约只列了既有测试文件时，守卫会拦下。这是刻意的 fail-closed：TA 该做的是把冲突记进 `ambiguities` 让父会话走 REPLAN，不是自己换路径。

**守卫为什么不用 import 复用 plan-mode**：`~/.pi/agent/extensions/plan-mode/utils.ts` 是兄弟扩展的 TypeScript 源码，不是任何包导出的模块——而且它**已经在本机工作树里被另一个并行改动删掉了**（`git status` 显示 staged deletion）。依赖一个随时可能被删的兄弟扩展不是接口。首版 `import { isSafeCommand } from ".../plan-mode/utils.ts"` 在**父会话的 node** 里能跑（单元夹具全过），但在**子会话的扩展宿主里加载失败**——而加载失败是静默的，于是守卫根本没注册、写入全部放行，且看起来和"没有守卫"一模一样。现已改为把只读白名单内联进 `guard-core.js`（注明来源）。教训：**守卫的集成测试必须在真实子会话里跑，单元测试通过不能证明它被加载了**。

## 能力声明

| 协议硬能力 | pi 实现 |
|---|---|
| 每阶段独立 fresh 上下文 | `context: "fresh"` |
| PLAN 运行中访谈 | `contact_supervisor` + 专属子扩展（下节） |
| per-agent 模型指定 | dispatch 的 `model`，含 `:thinking` 后缀 |

任一不可用 → 按 `SKILL.md` 硬能力条款 HALTED；本层不提供替代路径。

## 节点 → 内置 agent 绑定

| 节点 | agent | 依据（工具面/身份） |
|---|---|---|
| EVIDENCE | `scout`（仓内）/ `researcher`（仓外） | scout 有 `grep/ls/find/bash/write`；researcher 有 `web_*` 但**无 shell**，查不了仓库。**仓外一半必须 `async: true`**：`web_*` 是环境扩展工具，前台子进程不加载（实测前台派发全部工具不可用、直接失败） |
| PLAN | `plan`（用户目录专用定义） | 只读工具面 + 访谈通道；内置 `oracle` 的目标函数是保护既有决策，与 PLAN「产生新决策」冲突 |
| TEST_AUTHOR | `test-author`（skill 内 `agents/test-author.md`） | 有 `edit/write/bash`，单 commit 提交测试资产；`guard-test-author.js` 只许写测试 |
| EXECUTE | `executor`（skill 内 `agents/executor.md`） | 单写手；`guard-execute.js` 只许写 `allowed_paths`、禁改测试 |
| CONFORMANCE | `reviewer` | 只读（无 `edit/write/bash`）；`watchdog_diff` **不检查已提交范围**，必须由父会话提供 diff artifact |

内置 agent 的系统提示提供耐久纪律，阶段契约走 user 消息，两者并存、互不覆盖。沿用它们即继承其 prompt，而它们随扩展升级变化：扩展一升级，之前的行为结论就不再自动成立。

## dispatch 参数

父会话按 `SKILL.md` 的 `Agent(...)` 契约组装，在 pi 上映射为：

```ts
subagent({ agent: <绑定>, task: <组装结果>, model: <config 解析值>, async: true, options: { context: "fresh" } })
```

**退化即派发失败**：直接派发在部分会话里会被运行时静默降级（`task` 丢失 → 实际执行成 `action:"status"` / `"guide"`，返回列出 run 或文档而不是子 agent 产出）。判定方法：返回值不是子 agent 结论、也没有 run id。处理：计一次 `dispatch_failures`，改用 scripted workflow 派发同一节点。

```js
const r = await runs.run("<key>", { agent: <绑定>, model: <config 解析值>, cwd: <目标仓库>, context: "fresh", task: <组装结果> });
```

`runs.run(key, params)` 的 key 是稳定字符串；同一 workflow 内并行用 `runs.all([...])`。此时派发返回的是 **workflow run id**，而 `verify-models.py --run` 需要**子 run id**（workflow id 会 exit 2）——从 receipt 的 `childRuns[].runId` 或 `subagent({action:"status"})` 取。

PLAN 例外且唯一：只允许直接异步单代理启动（不要前台 PLAN，不要复合 workflow——扩展无法在共享 runner 中识别 PLAN）。

## 访谈通道机制

- 每个原生请求必须同时带 `message` 与 `interview`（只填 `reason` 的空调用即协议违规）。
- 专属扩展在 async runner 内、首次模型/工具请求前设置 `PI_INTERCOM_ASK_TIMEOUT_MS=86400000`；它要求 `PI_SUBAGENT_CHILD=1`，否则在写变量前失败。
- 每个请求有独立 24h 通道窗口；PLAN 的 `timeoutMs: 86400000` 从启动计时、覆盖整个 run，先到者生效。硬杀可能不产出 handoff。
- 父会话逐字转达用户回复，不做语义过滤；PLAN 自行判定是否结算。
- **回执落地方式（实测）**：权威通路是原生 channel 的答复文件 `replies/<requestId>.json`（扩展源码原话 "The reply file is authoritative"）——父会话把用户原话写进该文件即可投递。`subagent({action:"steer"})` 对阻塞在 ask 上的子 agent **只排队不投递**（排队后仍 blocked）；`subagent_supervisor({action:"reply"})` 在部分会话不可用。**三条都不通 → 硬能力「PLAN 运行中访谈」缺失，按 HALTED 处理**，不得静默跳过访谈或替用户作答。

```yaml
# 写在 agent 定义的 frontmatter 里（如本 skill 的 agents/plan.md），
# 不能作为 dispatch 参数：subagent 工具会拒绝 unknown options key。
subagentOnlyExtensions:
  - ~/.pi/agent/skills/planner-executor-pipeline/extensions/plan-interview-channel-timeout.js
```

该扩展只负责把 ask 窗口拉到 24h；缺它时请求仍发得出，但没有长窗口保障。

## 模型核对（每次派发后必做）

派发 cwd 是目标仓库，用 skill 目录的绝对路径调用：

```bash
python3 <skill>/scripts/verify-models.py --run <派发返回的 run id 前 8 位> --expect <节点>
```

判据是子 agent 自己的 session 头部（`provider`/`modelId`/`thinkingLevel`，首轮之前写入，前后台都有），按 `config.json`（缺则 `config.template.json`）反查节点。退出码 0=一致、1=不一致（→ HALTED）、2=无法判定（同样不得推进）。不给 `--run` 时取**启动时间最新**的子 session（按头部时间戳，不按文件 mtime）；没有 run id 就先 `--list 3` 看清再断言。

它证明的是：宿主接受了声明的派发参数并据此启动子进程。它不证明：provider 侧真给了这个模型、或子 agent 后续轮次没被换模型。因此它是**必要条件**，不是「该节点跑在某模型上」的充分证据；要证明执行须另查运行记录。

## 诊断（非截断）

- `usageBudget` 仅作后续 launch 闸门，tokens 口径不含 cacheRead，**不是单轮成本上界**。
- `turnCount>80` 或 `windowPeak>350K` 只作告警阈值，提示该节点在做非本职工作时长膨胀；不默认强杀。

## 已知限制

- `reviewer` 的 `watchdog_diff` 不覆盖已提交范围 → CONFORMANCE 必须收到 diff 文件，否则它应报告限制而非声称审过。
- `worker` / `reviewer` 的系统提示各自规定了最终输出形状，与 task 里的 handoff JSON 契约会冲突：实测 TEST_AUTHOR 2/2 正常产出 TestHandoff，而 EXECUTE 的 ExecuteHandoff 会丢（3 次里 2 次没有可解析的 JSON）。父会话据此按 `dispatch_failures` 计并重派一次，明说「只补写 handoff、不改代码」即可收敛。
- `reviewer` 无写工具，verdict / diff 这类产物一律由父会话落盘；让它自己写 `handoffs/*` 是无效指令。
- PLAN 的 `plan` agent 不带 `subagent` 工具，嵌套检索不可行 → 缺口走 `needs_research`。
- 子 agent 的输出可能被运行时重定向到它自己的 artifacts 目录（`output` 路由），因此 EVIDENCE 的证据包由父会话原样写回 `handoffs/research/`；不得依赖子 agent 自行落盘。
