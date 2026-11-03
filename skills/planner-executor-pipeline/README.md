# planner-executor-pipeline

一个**编排骨架**：把「目标」变成「通过需求验收的代码」。每个阶段的流程来自它复用的既有 skill（`grilling` / `to-spec` / `to-tickets` / `tdd` / `research` / `code-review`），本 skill 只负责节点边界、handoff 契约、上下限与门禁。

`SKILL.md` 是契约本身；本文件只讲**怎么装、怎么接、怎么验**。

## 目录

```
SKILL.md                    # 节点定义、路由表、用户确认点、跨节点规则
config.json                 # 每节点 model@thinking 推荐值
config.template.json        # 同上，占位符版（换宿主/换模型时从这里改）
agents/                     # 节点专用 agent 定义（plan / test-author / executor）
extensions/                 # 节点守卫（写边界）+ 访谈窗口
references/
  artifacts.md              # 五个 handoff / GATE 七检查 / 归档模板
  pi-adapter.md             # pi 落地：agent 映射、派发形态、已知限制
  references-index.md       # 每阶段复用的 skill 与其绝对路径、允许的偏离
  intent-template.md        # spec.intent 的字段表与强制者约定
scripts/
  preflight.py              # 运行前解析 8 条外部依赖路径，缺则打印安装命令并非零退出
  verify-models.py          # 核对子 run 实际生效的 model/thinking
  check-verdict.py          # 核对 CONFORMANCE 的 answer_key
  gate.py                   # GATE 七检查的唯一实现
  intent-check.py           # spec.intent 的 C0–C9 校验
evals/                      # 回归夹具（改配置/改契约前必须全跑）
```

## pi 侧接入点（两处，缺一不可）

**1. 让 pi 发现本 skill 的节点 agent。** agent 定义放在 `agents/` 下，跟随 skill 走；pi 需要一次扫描根才能看到它们——在 `~/.pi/agent/settings.json`：

```json
{
  "subagents": {
    "agentScanDirs": ["~/.pi/agent/skills/planner-executor-pipeline/agents"]
  }
}
```

> 优先级陷阱：固定的 `~/.pi/agent/agents/` **高于**扫描根。同名文件留在那里会**静默遮蔽**本 skill 的版本，表现为「一切正常但改动不生效」。旧的 `plan.md` 等必须删干净。

**2. 模型绑定。** `config.json` 的 `nodes` 是每节点 `model@thinking`；换模型前按 `SKILL.md` 的 dispatch 契约跑完 `evals/regression/` 并亲自读结果。

## 验证安装

```bash
python3 evals/regression/check-install.py   # 扫描根 / 遮蔽 / 相对路径 / 扩展是否存在
node   evals/regression/check-node-guard.mjs # 节点写边界（20 条正负例，零模型调用）
python3 evals/regression/check-config.py    # T1：声明的 model@thinking 与实际启动一致
```

退出码约定：`0` 断言成立、`1` 证实不一致、`2` 无法判定。**崩溃绝不能读成通过。**

## 运行时依赖

- **既有 skill**：外部 skill 一律按 `~/.agents/skills/<name>/SKILL.md` read；agent 的 `skills:` 只留本 skill 自身契约，`skillPath` 不再指向任何副本。细节见 `references/references-index.md`。
- **pi-subagents**：派发、workflow、native supervisor channel（访谈回执）。
- **内置 agent**：`scout` / `researcher`（EVIDENCE）、`reviewer`（CONFORMANCE）。

## 改这个 skill 之前

`evals/regression/README.md` 是回归清单；`evals/eval-log.md` 记录每轮改了什么、被什么证据推翻过。任何「应该能行」的改动都要先有一条会失败的夹具。
