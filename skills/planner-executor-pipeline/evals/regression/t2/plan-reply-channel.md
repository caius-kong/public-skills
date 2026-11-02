# T2 / 访谈回执通路

任务：给 PLAN 一个含未决项的 brief，等它发出访谈请求后，父会话把用户原话投递回去，PLAN 应当据答复继续并产出 handoff。

投递方式（三选一，按可用性降级）：

1. `subagent_supervisor({ action: "reply", replyTo: <requestId>, message: "<用户原话>" })`；
2. 原生 channel 的答复文件：`$TMP/pi-subagents-uid-<uid>/supervisor-channels/<runId>-<agent>-<childIndex>/replies/<requestId>.json`，内容 `{"type":"subagent.supervisor.reply","requestId":"<id>","createdAt":<ms>,"message":"..."}`（扩展源码：The reply file is authoritative）；
3. 都不行 → 硬能力「PLAN 运行中访谈」缺失 → **HALTED**，不得替用户作答或跳过访谈。

通过条件（n≥1）：

- 投递后 PLAN **继续运行**并且 `requests/` 中该请求被消费（文件消失），而不是一直 blocked；
- 最终产出字段齐全的 PlanHandoff，且 `spec` 中引用的用户裁定与投递内容**逐字一致**；
- 投递内容是用户原话，PLAN 未把你的答复再解释成自己的决定。

已知事实（2026-10-23 实测）：`subagent({action:"steer"})` 对阻塞在 ask 上的子 agent **只排队不投递**；`subagent_supervisor` 在部分会话里正文丢失（`message is required`）；答复文件通路在同样会话里可用，两次投递后 PLAN 正常收敛并产出 handoff。
