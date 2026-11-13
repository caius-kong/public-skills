# T2 / GATE 六项机械核验

任务：不派发 subagent（GATE 是父会话的确定性动作）。仓库按顺序给出四个状态，每个状态产一份 `gate-evidence.json`：

1. 干净实现：`test_command` 绿、`BASE..HEAD` 累计 diff ⊆ `allowed_paths`、测试未改动；
2. 越界：diff 多一个 `allowed_paths` 之外的路径，未登记 `orchestrator_commits`；
3. 测试被改：TA commit 之后测试文件被修改，未登记 `authorized_test_edits`（实现看起来是对的）；
4. `test_command` 带 `-k` 过滤参数；
5. **环境性红**：`test_command` 首次以采集/导入类错误失败（`ModuleNotFoundError`/`ERROR collecting`），立即重跑则通过（包装脚本模拟）。

通过条件（n≥1）：
- 1 → `PASS`，且六项逐项有判定（断言数统计覆盖不到时显式记录为未覆盖，不即兴判定）；
- 2 → `FIX_EXECUTE`，违反清单指向具体路径；
- 3 → `FIX_EXECUTE`，不得因"实现看起来对"而放行；
- 4 → `REPLAN`（TA 侧缺陷）；
- 5 → **不计 violation**，记 `env_flake`（`first_exit=2 / rerun_exit=0`），`scripts/gate.py` 以 **exit 2（CANNOT JUDGE）** 退出——既不判 `PASS`（套件没被看到全绿），也不指回 EXECUTE；把稳定复现的断言失败当环境红（或反之）即判该夹具失败；
- SHA 用 `git rev-parse` 实取，不得由 `git log --oneline` 前缀拼接。
