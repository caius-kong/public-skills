# T2 / 状态机守卫与计数器（桌面推演）

任务：读 `SKILL.md`（必要时 `references/artifacts.md`），对下列场景**逐条**给决策。**不派发任何 agent**。输出单一 JSON 数组，每项 `{"id","decision","counter","value"}`，`decision` ∈ `retry|replan|halted|return_to_stage|proceed`。

场景（每条独立，其余字段为常规初值）：

| id | 场景 |
|---|---|
| g1 | EXECUTE 票 t1 逻辑失败（测试红），第 1 次 |
| g2 | EXECUTE 票 t1 第 3 次失败 |
| g3 | EXECUTE 派发返回错误、无 handoff，第 1 次 |
| g4 | EXECUTE 派发错误第 3 次 |
| g5 | PlanHandoff 的 `dag` 是边数组而非映射 |
| g6 | CONFORMANCE 判 `FIX_EXECUTE`，但修复动作本身需要改测试 |
| g7 | GATE 发现 `BASE..HEAD` 有个 `.gitignore` 变更，已登记于 `orchestrator_commits` |
| g8 | `replan_round` 已是 3，又触发一次 REPLAN |
| g9 | 同一事件 `attempts` 触顶、`dispatch_failures` 也触顶 |

通过条件（n≥1）：9 条 `decision` 全对，`counter`/`value` 就低对：

- g1 `retry`，`attempts[t1]=1`；g2 `replan`，`attempts[t1]=3`（不是 `halted`）；
- g3 `retry`，`dispatch_failures.EXECUTE=1` 且 `attempts` 不变；g4 `halted`，`dispatch_failures.EXECUTE=3`；
- g5 `return_to_stage`，`dispatch_failures.PLAN=1`（原样退回，不得归一化形状）；
- g6 `replan`（EXECUTE 无权改测试，FIX_EXECUTE 无合法动作）；
- g7 `proceed`（已登记放行）；g8 `halted`；g9 `halted`（HALTED > REPLAN）。
