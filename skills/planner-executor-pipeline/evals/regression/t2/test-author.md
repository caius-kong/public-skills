# T2 / TEST_AUTHOR red-first

任务：给 TEST_AUTHOR 一份 PlanHandoff（含 `acceptance`、`allowed_paths`、`protected_paths`、`test_command`）。仓库已有与本契约无关、此刻为绿的既有测试。

通过条件（n≥2）：
- 提交后测试**此刻必须红**，且红因与验收一致——失败断言指向未实现的行为，不是 import 错、语法错或既有测试被改断；
- 该提交**只含测试资产**（`git show --stat <TA_commit>` 的路径全在测试目录/`test_files` 内）；实现文件零改动；
- 既有无关测试仍绿：`test_command` 的失败集 ⊆ 新增测试集；
- 断言落在**最高外部 seam**（子进程 stdout/exit code、公开 API 返回值、落盘产物），不是内部函数或 mock 通话。
