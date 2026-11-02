# skill-gate 报告（严格版，2026-09-21）

目标：两个 SKILL.md 的**最新一次改动**是否通过 skill-gate 硬门禁。
分支：**SKILL.md edits (hard gate)** —— 必须走 `skill-creator` 协议。

本次是**重做**。此前三次改动（含我自己那一次）都**没有走 skill-creator**，只用
自写正则 + 自己读。本报告按协议把缺的环节补齐，并因此**推翻了此前的两个结论**。

---

## 结论

| 文件 | 本次改动 | 硬门禁 | 判定 |
|---|---|---|---|
| `planner-executor-pipeline/SKILL.md` | `3b43252` 去平台名词（1 行） | ✅ 三步齐 | **ACCEPT** |
| `tech-debt-cleanup/SKILL.md` | 未提交：删 `## 核心设计` 段 | ⚠️ 文本 ✅ / eval ✗ | **ITERATE** |

---

## 一、planner-executor-pipeline（本次改动 `3b43252`）

### 1. skill-creator 路由 —— 本次已走完协议

基线 = `3b43252~1`（改动前），WITH = 现工作区版本。

| 协议环节 | 状态 |
|---|---|
| 两臂 fresh 进程（绝不 fork） | ✅ |
| **臂隔离** | ✅ **（本次修的严重缺陷，见下）** |
| `evals.json`（skill-creator schema） | ✅ 4 evals |
| `eval_metadata.json` | ✅ 4 份 |
| **独立 grader**（`agents/grader.md`，fresh worker，逐条引证 + claims + eval_feedback） | ✅ 8/8 |
| `grading.json` | ✅ 8 份 |
| `benchmark.json` / `benchmark.md`（官方 `aggregate_benchmark.py`） | ✅ |
| 失真元数据修正（工具硬编码 3 runs → 实际 n=1） | ✅ |

### 2. 修复的严重缺陷：臂隔离失效（独立 grader 发现）

**独立 grader 抓到我漏掉的问题**：eval-0 的 WITHOUT 臂 transcript 明文写着

> "the skill points to the artifact contract at `references/artifacts.md`, which I
> located in the **sibling `WITH/` variant** and read."

即：WITH 与 WITHOUT 是**兄弟目录**，基线臂越界读了对手臂的 `references/artifacts.md`
——**把被测规则本身导入进来**。该臂的 `references/` 本该是空的。
→ **eval-0 的区分度曾是无效的**，而我这边的正则判分完全没察觉。

**修复**：每臂在**独立沙箱根**运行（兄弟路径不可达），并加**自检**：transcript 若出现
`sibling` / `/WITH/` / `/WITHOUT/` 即判 FATAL。修复后 8/8 transcript 无越界。

### 3. 隔离 + 独立判分后的真实矩阵（iteration-6）

| eval | WITH | WITHOUT | 区分 |
|---|---|---|---|
| 0 `handoff-contract-shape` | **4/4** | 2/4 | ✅ |
| 1 `gate-authz-before-violation` | **4/4** | **0/4** | ✅ 强 |
| 2 `bounded-wait-terminal` | **4/4** | 3/4 | 弱（n=1） |
| 3 `frozen-test-fix-route` | **4/4** | **4/4** | ✗ 不区分 |

**官方工具汇总：WITH 100% vs WITHOUT 56.2%，delta +0.44。**

⚠️ **此前的结论被推翻**：污染版曾显示 eval-0 *不区分*、eval-3 *强区分*。隔离后**正好倒转**。
原因即上面的兄弟目录泄漏。

### 4. Context Concise 句级审计（本次改动的那一句）

```
前: ...一视同仁（worker 侧走 `need_decision`，同样禁止重发/空转）。
后: ...一视同仁（worker 侧的裁决请求同样禁止重发/空转）。
```

| 测试 | 判定 |
|---|---|
| delete | **不可删** —— 前句"一视同仁"列的是 PLAN…CONFORMANCE 的状态机节点；worker 侧的裁决通道是**另一条路径**（走 handoff `ambiguities`，非 `blocked_on_interview`），删掉会丢失该绑定 |
| reword | ✅ 改动本身即 reword |
| rewrite | ✅ 无有害指令 |
| generalize | ✅ **正是本次改动目的**：原句含平台专有名词 `need_decision`（pi-subagents 的 reason 值），核心层不得出现；`references/platform-adapter.md:20` 保留映射 → **无信息损失** |

悬空引用：核心层 0 处 `need_decision`；adapter 层保留 1 处。✅

### 判定：**ACCEPT**

**遗留（不阻塞）**：eval-3 不区分；eval-2 仅 1 bit 且 n=1；`claims` 中若干
"would persist/dispatch" 属假设性表述（只读 probe 无法观测执行）——独立 grader 已如实标注。

---

## 二、tech-debt-cleanup（未提交改动）

### 1. 文本（Context Concise）—— ✅ 通过

删除 `## 核心设计` 段 + 一条实测案例句。独立审查确认：三条原则在操作层文本中已有对应
（三类自动删除表 / 两项事务与两轮协议 / "宁可不做，不可做坏"），why 的归宿存在
（`references/design-history.md`）。无悬空引用。**文本层面改善简洁度。**

### 2. eval —— ✗ 结构上无法验证该改动

我补了它的 runner（此前只有 `evals.json`，无 runner，唯一记录的 run 落在 `/tmp`），
严格单变量：**`SKILL.md` 不同，`scripts/` 与 `references/` 逐字节相同**。

独立 grader 判分：

| eval | WITH | WITHOUT | 可区分? |
|---|---|---|---|
| 1 `scan-quality` | 6/6 | 6/6 | ✗ |
| 2 `safety-gate` | 4/4 | 3/4 | 弱（1 bit，方向受混淆） |
| 3 `dangling-ref-disposition` | 4/4 | 4/4 | ✗ |

独立 grader 的原话：

> "`scripts/`, `references/`, and `repo/` are **byte-identical between arms in all
> three evals; only SKILL.md differs**… **Cannot discriminate**: eval-1 A2/A3/A4 (all
> produced by the shared scanner); eval-1 A1/A5 and eval-2 A1/A3 (dictated by the
> SKILL.md portion identical in both variants)… **Only actual discriminator in the
> whole set**: eval-2 A4 backup/rollback… n=1, and the failing arm is the one whose
> SKILL.md explicitly names the 备份/回滚 pipeline — **direction confounded**."

即：**3 个 eval 里只有 1 条断言可能区分，且方向被混淆，不能归因于本次文本改动。**

### 判定：**ITERATE**

文本通过，但 **eval 集无法为这次改动提供证据**。要让门禁可判，至少需要一个 eval 测
**驻留在 SKILL.md 文本里**的规则（如两轮门禁：是否拒绝在未确认轮直接执行），而非已固化在
共享 `scripts/` 中的行为。

---

## 三、方法论收获（本次最重要的产出）

1. **自写正则判分不可信**：它给出的是"WITH 劣于 WITHOUT"之类的**反向结论**
   （否定句/引用规则被当成违规），且**完全没发现臂污染**。协议要求独立 grader 正是为此。
2. **臂隔离是 benchmark 有效性的前提**，不是卫生问题。一个兄弟目录可达就足以让
   基线臂读到被测量的规则，把 delta 变成假象。
3. **独立 grader 能推翻我的结论**：eval-0 与 eval-3 的区分度在隔离前后**完全倒转**。
4. **工具自身会撒谎**：`aggregate_benchmark.py` 硬编码 `runs_per_configuration=3`，
   在 n=1 时该字段为假——已修正并在报告标注。

---

## 证据索引

| 路径 | 内容 |
|---|---|
| `skills/pi/planner-executor-pipeline/evals/run-evals.sh` | runner（含臂隔离 + 越界自检） |
| `...-workspace/iteration-6/` | 隔离后的 runs + 独立 grading.json + benchmark |
| `...-workspace/iteration-6/benchmark.md` | WITH 100% / WITHOUT 56.2% |
| `skills/tech-debt-cleanup/evals/{run-evals.sh,grade.py,results.json}` | tdc harness |
| `skills/tech-debt-cleanup-workspace/iteration-2/` | tdc runs + 独立 grading.json |
| `/tmp/gate-strict/planner/{baseline,revised}-SKILL.md` | 本次改动的两臂材料 |