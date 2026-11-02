# T2 / seam 一致性（GATE #7）

任务：给一份 PlanHandoff（声明 `seams=[{id:"S1",modules:["src.fmt"]}]`）配两种 TestHandoff，判定测试是否只打在声明的 seam 上。

通过条件（两种输入都必须判对，n≥1 每态）：

- **合规态**：测试 `from src.fmt import ...` → `PASS`；
- **越界态**：测试 `from src._fmt_impl import ...`（或 `from src.fmt._internals import ...`）→ **`REPLAN`**，且 gate-evidence 的 `7_seam.offending` 指出该文件与越界模块；
- **漏报态**：越界测试文件**被 TA 从 `test_files` 里省掉**——仍然必须 `REPLAN`（扫描对象是 diff 中全部测试文件与 `test_files` 的并集，不信自报）；
- 判定必须精确匹配：声明 `src.fmt` **不**覆盖 `src.fmt.totals`；import 路径任一段以 `_` 开头一律视为绕过（`src._fmt_impl`、`src.fmt._internals`）。

判错方式（夹具失败）：把越界判成 `PASS`（前缀匹配放宽到子模块、或只信 `test_files`）；把合规判成 `REPLAN`（精确匹配误伤标准库或测试框架 import）。

已知实测（2026-10-23）：实现初版用了前缀匹配，`src.fmt._internals` 被 `src.fmt` 覆盖 → 越界态误判 `PASS`；改精确匹配 + `_` 段规则后纠正。这正是「机械判据也要有反向夹具」的例子：一个只会说 PASS 的检查看起来和真的检查一模一样。
