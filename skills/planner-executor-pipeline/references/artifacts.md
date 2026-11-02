# 产物契约（Handoff Artifacts）

> 由 `SKILL.md` 按需加载：组装或校验任何 handoff、或执行 GATE 检查时读取。

handoff 以文件落盘 `handoffs/*.json`（gitignored）；子 agent 最终响应里的 handoff JSON 由父会话**原样落盘，不改写**；**不传父会话 transcript**。五 artifact：PlanHandoff / TestHandoff / ExecuteHandoff / GateEvidence / Verdict。

**形状约束**（字段清单不足以拒收漂移；以下为硬约束）：

- `dag` **必须**为映射 `{"<ticket_id>": ["<依赖 ticket_id>", ...]}`——不接受节点/边数组、邻接表、字符串或其它形状。
- `tickets` 必须为数组，每项含 `id`/`title`/`acceptance`/`depends_on`/`files`/`seam`；`acceptance` 为非空字符串数组，`depends_on`/`files` 为字符串数组，`seam` 为 `seams` 中的某个 `id`。
- `seams` 必须为非空数组，每项含 `id`/`modules`/`rationale`/`catches`/`misses`；`modules` 为非空字符串数组（被测模块的 import 路径，如 `src.invoice`），`rationale`/`catches`/`misses` 为非空字符串。**seam 数越少越好，理想为 1**——每多一个 seam 就多一处需要长期维护的测试边界。
- `allowed_paths`/`protected_paths` 为字符串数组；`test_command` 为非空字符串。
- 形状不符 → **原样退回**（等同字段缺失），不得由父会话自行归一化。
- **`allowed_paths` 与 `protected_paths` 交集必须为空** → 非空即**原样退回**。这两个集合回答的是「谁可以写它」，同一个路径同时出现在两边没有意义，实际后果是 TEST_AUTHOR 拿到的交付路径被自己的任务 prompt 判为「不得写入」，节点只能自救（实测两次）。父会话在冻结前做这条校验，一次交集判断即可，不需要模型判断。
- **`allowed_paths` 必须是具体文件路径**，不得是目录或通配（`src/`、`**/*.py`）→ 退回。目录级边界让 GATE #2（diff ⊆ allowed_paths）恒真，越界检查归零；确需覆盖面较大时按文件逐条列出。
- `spec` 段必须按 `to-spec` 模板的组织方式承载（问题陈述 / 方案 / user stories / 实现决定 / 测试决定 / 范围外），缺整段 → 原样退回；`tickets` 的 slice 规则与 blocking edges 由 `to-tickets` 决定，本文件只规定 JSON 形状。

父会话校验（对照字段清单逐项核对；字段缺失/类型错/形状不符/acceptance 不可测 → **原样退回**该阶段并附缺失清单）：

- **PlanHandoff**：`spec`（含**必填** `spec.intent`：形状、示例与强制者定义见 `references/intent-template.md`）、`new_symbols`（**必填**：本次新增的命令名/函数名/模块名，供 `scripts/intent-check.py` 判 intent 是否在设计泄漏）、`deviations`（可空：对复用 skill 原文的偏离及理由，见 `references-index.md`）、`decisions[{id,question,ruling}]`（可空：访谈中用户已裁定的决策，逐条原样记录）、`seams[{id,modules[],rationale,catches,misses}]`、`tickets[{id,title,acceptance[],depends_on[],files[],seam}]`、`dag`、`allowed_paths`、`protected_paths`、`test_command`、`ambiguities`（可空）、`needs_research`（可空：证据缺口清单，触发 EVIDENCE 节点）、`blocked_on_interview`（可空：`{round,questions_count}`；仅真实通道过期或用户明确取消访谈后，若 PLAN 正常产出 handoff 则必填并附完整未决载荷；run hard kill 不保证 handoff）
- **TestHandoff**：`commit`、`test_files`、`red_summary`、`green_baseline`、`existing_tests_updated`（可空：被改既有测试 `文件:函数` + 理由）、`ac_coverage`（**形状固定**：`{"<AC id>": ["<测试函数名>", ...]}`；本 seam 无法断言的审查型验收写 `{"<AC id>": {"covered_by": "CODE_REVIEW", "reason": "<为什么测不了>"}}`）、`ambiguities`（可空：待决问题）
  - **测试函数名必须含对应 AC id**（`test_ac7_...`）：GATE 由函数名推导「每条 acceptance 是否有测试」，**不采信 `ac_coverage` 自报**——自报只作旁证，两者不一致时以文件为准并记为可疑。
- **ExecuteHandoff**：`ticket`、`commit`、`test_output_summary`、`attempts`、`ambiguities`（可空：待决问题）
- **Verdict**：`verdict`(**严格三值之一**：`PASS`/`FIX_EXECUTE`/`REPLAN`；`CHEAT`/`BLOCK`/`APPROVE` 等自造值 → 原样退回并计 `dispatch_failures`)、`reasons`、`findings`、`answer_key[{acceptance,evidence,reasoning}]`、`rerun{command,result}`。
  - `answer_key`：**逐条** acceptance 给三项——`evidence` 是「证明这条被真实实现」的代码位置（`path:line`，必须在 `impl.diff` 触及的行内）；`reasoning` 一句话说明为什么这行不是特判/常量映射。任何一条缺 `evidence` 或位置落在 diff 之外 → Verdict 无效（按 `dispatch_failures` 计并重派），**不得以「未发现硬编码」的空泛叙述代替**。
  - `rerun`：审计者独立重跑 `test_command` 的结果；没有 shell 时写 `{"command": null, "result": "not run: <缺什么>"}`，并在 `reasons` 里说明结论依赖谁给的证据。
  - 为什么要这份 answer key：`findings` 为空就能拿 `PASS`，而"找不到问题"的最省力实现就是不去找。逐条必答把"没审"从产出里显形——`evidence` 行号由父会话机械校验（见 `scripts/check-verdict.py`）。

## 交付归档文档模板（`docs/specs/<date>-<slug>.md`）

```markdown
# <spec.title>

- 交付日期：<YYYY-MM-DD>
- 基线：`<BASE_SHA>` → 交付：`<HEAD>`
- 结论：<Verdict.verdict> — <reasons 逐条>

## Intent
（`spec.intent` 原样渲染：问题 / 达成什么 / 约束及其强制者 / 不做。它是摘要：`problem` 是下方问题陈述的首句，冲突以验收为准）

## 问题陈述
（to-spec 的 Problem Statement 原文；`spec.intent.problem` 必须是它的首句——派生而非另写，否则两处会各写一版）

## 方案
（Solution）

## User Stories
（编号列表，原文）

## 实现决定
（Implementation Decisions）

## 测试决定
（Testing Decisions，含 seams：每个 seam 的 modules / rationale / catches / misses）

## Settled decisions
- **<question>** → <ruling>
（逐条列 `decisions` 原文。这不是小结：下一次 PLAN 派发时必须把这些条目当作已定输入，同类问题不得重问，人类参与量才随项目历史递减）

## 验收清单
- [ ] <ticket id> · <acceptance 原文>
（逐票列全部 acceptance；已由 GATE 与 CONFORMANCE 核验）

## 范围外
（Out of Scope）

## 备注
（Further Notes、deviations、`ambiguities` 中仍未决的项）
```

只写这八段；不复述 evidence 包内容，只在其被引用时给路径。文档是给人读的：它要在半年后仍然回答「这件事当初为什么这么做、验收了什么」。

## GATE 检查项（确定性机械核验，不采信任何理由）

1. `test_command` 退出码 0。**非 0 时要先分清环境红与逻辑红**：原样重跑一次；两次结果不一致，或失败发生在采集/导入阶段（`ModuleNotFoundError`、`ImportError`、`ERROR ... in collection`、插件/版本告警）→ 记为 `env_flake`，不计 violation、也不进 `attempts`（换个干净环境重跑即可）；两次一致且失败指向断言 → 按逻辑红处理。
   基线可从 `git archive <BASE_SHA> | tar -x -C <临时目录>` 解出的临时树复现——`BASE` 也红就是环境问题，不是本次提交造成的。
2. `BASE..HEAD` 累计 diff ∈ allowed_paths。**例外**：出现在 `state.orchestrator_commits` 中的提交（父会话生命周期变更，如 .gitignore/配置）按登记放行并记录；未登记者视为违规 → REPLAN（追认边界）或 HALTED（人工裁决）；
3. **测试冻结核查（先查授权，再判违规）**：从 test-handoff.json 实取 commit/test_files，取 `git diff <TA_commit>..HEAD -- <test_files>` 的变更。
   - **变更集为空** → PASS；
   - **变更集全部落在 `state.authorized_test_edits` 内**（逐文件核对且 commit 可追溯）→ PASS，但须在 gate-evidence 中记录为「已授权测试修改」；
   - **存在未授权变更** → **FIX_EXECUTE**；
   - **若修复该 violation 需要改测试**（即测试协议自身缺陷）→ **不得 FIX_EXECUTE**（EXECUTE 无权改测试），改判 **REPLAN**（契约缺陷）或 **HALTED**（需人工裁决）。
4. **冻结强度核查**（对照 BASE，逐 test 文件）：用例数或断言数不降、无新增跳过/禁用标记（skip/xfail/skipif/todo 等）、无测试文件删除；`test_command` 全量执行，不得含用例选择/过滤参数（如 `-k`/`--deselect`/`--ignore`）——违反 → REPLAN（TA 侧缺陷，不采信理由）。BASE 侧用例数必须 `git archive <BASE_SHA> | tar -x -C <临时目录>` 后在临时树上 `--collect-only` 统计（不得拿已推进的工作树冒充 BASE）；断言数由框架的计数能力决定（pytest 无断言计数，能统计者则同时比对，不能则**显式记录为未覆盖**而非即兴判定）；
5. handoff SHA 与 `git log` 核对；`BASE_SHA` 用 `git rev-parse` 实取；
6. **anti-gaming**：测试必须黑盒断言（断言外部可观察行为，非实现细节/mock），且**每条 acceptance ≥1 断言命中**。来源是**测试函数名**里的 AC id，不是 `ac_coverage` 自报；审查型验收由父会话以 `--review-acs` 显式点名并写入 `gate-evidence.json`（不靠正则从验收措辞里猜）。
7. **seam 一致性**（机械可判定）：扫描对象取 `BASE..HEAD` 累计 diff 中所有测试文件（`tests/`、`test_*.py`、`*.test.*`、`*.spec.*`）**与 `test_files` 的并集**——不得只信 TA 自报的 `test_files`，漏报的测试文件同样是契约的一部分。解析每个测试文件的 `import`/`from ... import` 顶层模块名，取其被测目标集合 T；要求 `T ⊆ ⋃seams.modules ∪ 标准库 ∪ 测试框架 ∪ conftest 注入的公共夹具`。T 中出现的**被测实现模块**不在任何 `seams.modules` 里 → **REPLAN**（测试打在了未声明的 seam 上：要么 PLAN 漏声明边界，要么 TA 自行挑了一个边界，两者都是契约缺陷，不得由 EXECUTE 修）。判定口径：只看是否 import 了被测模块，不评判断言写法（写法由 #6 管）；`modules` 用点分 import 路径，**精确匹配**——声明 `src.invoice` 不覆盖 `src.invoice.totals`，需要测子模块就把它单独列进 `modules`。理由：前缀匹配会把「测试伸手进包的子模块/内部结构」判成合规，那恰好是 seam 要拦的东西；精确匹配下越界会走 REPLAN，代价是该轮契约补齐一轮，比放行一个不该存在的边界便宜。任何 import 路径中出现 `_` 开头的段（`src.fmt._internals`、`src._core`）一律视为绕过公开边界。

**违反 → verdict 映射（逐项必填，不得留空）**：

| 检查项违反 | 去向 |
|---|---|
| #1 `test_command` 非 0 退出 | FIX_EXECUTE（实现缺陷，指回相关票） |
| #2 diff 越界 allowed_paths | 已登记于 `orchestrator_commits` → 放行并记录；否则 FIX_EXECUTE；若越界源于更早轮的已提交文件 → REPLAN（契约需重定义边界） |
| #3 未授权的测试冻结破坏 | FIX_EXECUTE；若修复需改测试（协议缺陷）→ REPLAN 或 HALTED（见检查项 #3 分支） |
| #4 冻结强度下降/跳过参数 | REPLAN（TA 侧缺陷） |
| #5 handoff SHA 不符 | REPLAN（契约/记录不一致） |
| #6 anti-gaming 失败（非黑盒断言 / acceptance 未命中） | REPLAN（TA 侧缺陷，测试需重写——EXECUTE 无权改测试，不得指向它） |
| #7 测试打在未声明的 seam 上 | REPLAN（契约缺陷：PLAN 补 seams 或 TA 改写测试，两者都不由 EXECUTE 修） |

**REPLAN 的边界前置条件**：`BASE..HEAD` 累计 diff 可能已含前轮提交的路径。故 REPLAN 回 PLAN 时，新 PlanHandoff 的 `allowed_paths` **必须 ⊇ 当前累计 diff 的所有路径**（否则 GATE #2 必然无解）；否则须显式规定 revert 流程。

**EVIDENCE 证据包的最小校验**（该节点不产 handoff JSON，但不得无标准）：每个 `needs_research` 缺口都必须有对应落盘文件（`handoffs/research/*.md`）且非空；缺一 → 原样退回 EVIDENCE。

**GATE 产出**：`gate-evidence.json`（含 BASE_SHA/HEAD/exit code/diff 文件清单/冻结核查结果/violation 判定）。

**CONFORMANCE canary（每个流水线运行至少一次）**

判据 `findings` 为空 ≈ PASS 会被"不查"直接满足，所以周期性用**已知答案的输入**校准审计者本身：

1. 取本次交付的仓库，复制一份到临时目录，注入一处**已知作弊**（例如让实现返回一个针对测试输入的常量映射，或把断言值硬编码进实现），保持 `impl.diff` 与注入后的状态一致；
2. 用**同一个模型与同一份 prompt** 对 canary 仓库派发 CONFORMANCE；
3. 期望 verdict = `FIX_EXECUTE`，且 `findings` 定位到被注入的那一行。
   - 报出来 → 该节点本轮可信，canary 结果记入 `verdict`（`canary: pass`），正式结论才生效；
   - 报 `PASS` → **该节点的 PASS 本轮不可信**：正式结论一律降级为 `REPLAN`（或 `HALTED`，需人工裁决），并把这个事实写进 `reasons`；
4. 频率：每次流水线运行至少一次；同一模型/提示变更后必须重跑。

**不许把 canary 结果反过来当交付结论** —— 它只回答"这个审计者今天会不会看"，不回答"这次交付对不对"。

**ALLOWED 提取命令**（EXECUTE 组装时实取，禁止心算）：

```bash
python3 -c "
import json,re
p=json.load(open('handoffs/plan-handoff.json'))
t=[x for x in p['tickets'] if x['id']=='$TICKET_ID'][0]
def norm(x): return x.strip().replace('**/','').rstrip('/')
prot=[norm(x) for x in p['protected_paths']]
def under(f,x): return bool(x) and (f==x or f.startswith(x+'/'))
print(','.join(f for f in t['files'] if not re.search(r'(^|/)(test|tests|__tests__|spec)(/|$)|\.test\.|\.spec\.',f) and not any(under(f,x) for x in prot)))"
```

说明：路径比较按**路径段对齐**（`f == x` 或 `f.startswith(x + '/')`），避免 `src/legacy` 误伤 `src/legacy2/`。仅**前置 `**/`** 会被剥离（如 `**/secrets/*` → `secrets/*`）；**除该剥离外，任何含 `*` 的条目（中缀、尾缀）均不保证匹配，不得依赖本命令**，须人工核对并记录——例如尾缀 glob `src/generated/**` 不匹配任何真实文件路径。