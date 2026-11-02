import type { PlanHandoff, Ticket } from "./schemas.ts";
import { deploymentFor, type LaunchConfig, type Role } from "./deployment.ts";

// D3: task prompt 生成器 —— 确定性、由 handoff 数据驱动。
// 约束引用文件路径（# References 模式），不内联 skill 正文。

const SKILLS_ROOT = `${process.env.HOME ?? "~"}/.agents/skills`;

export const REF = {
  grillMe: `${SKILLS_ROOT}/grill-me/SKILL.md`,
  grilling: `${SKILLS_ROOT}/grilling/SKILL.md`,
  toSpec: `${SKILLS_ROOT}/to-spec/SKILL.md`,
  toTickets: `${SKILLS_ROOT}/to-tickets/SKILL.md`,
  tdd: `${SKILLS_ROOT}/tdd/SKILL.md`,
};

const SUPERVISOR_PAYLOAD_CONTRACT = `supervisor 访谈载荷契约（模型硬门槛）：每次 contact_supervisor 必须同时携带 message（本轮全部 frontier 问题原文）与 interview（{"round":n,"questions":[...]}）。只发 reason 的空调用视为协议违规；父侧校验无载荷即 REPLAN。`;

export function genPlanTask(briefPath: string, opts?: { replanned?: string }): string {
  return `你是 planner-executor-pipeline 的 Plan 阶段。工作目录是目标仓库（launch 时给定 cwd）。

阶段内部 workflow：/grill-me → /to-spec → /to-tickets
${opts?.replanned ? `REPLAN 上下文（第 ${""}轮重规划）：${opts.replanned}\n` : "若 brief 已含收敛问答，访谈可精简；若有未决歧义，按协议访谈。"}
按以下 References 执行（先 read 文件，再按其协议）：
- /grill-me: ${REF.grillMe}
- /grilling: ${REF.grilling}
- /to-spec: ${REF.toSpec}
- /to-tickets: ${REF.toTickets}

输入：read ${briefPath}（用户 brief）。

产出 PlanHandoff（最终响应一个 \`\`\`json 块）：
{ "spec": string, "tickets": [{ "id", "title", "acceptance": string[], "depends_on": string[], "files": string[] }], "dag": string, "allowed_paths": string[], "protected_paths": string[], "test_command": string, "ambiguities": string[] }
每个 ticket 的 acceptance 必须是可测断言（测试意图、断言、边界）；写不出则并入 ambiguities。

${SUPERVISOR_PAYLOAD_CONTRACT}

边界：全程只读（bash 仅限只读用法）；ambiguities 非空时先访谈再收敛；不得虚构用户未给出的决定。`;
}

export function genTestAuthorTask(plan: PlanHandoff, testCommand: string): string {
  const tickets = plan.tickets
    .map((t) => `- ${t.id} ${t.title}｜验收：${t.acceptance.join("；")}`)
    .join("\n");
  return `你是 Test Author 阶段（唯一 writer，当前仅你写测试资产）。

输入：父会话已把 PlanHandoff 落盘为 handoffs/plan-handoff.json，先 read 它。
测试协议（References）：/tdd: ${REF.tdd}

Tickets：
${tickets}

要求：
1. 为每个 ticket 创建 red-first 验收测试（黑盒：真实子进程执行 CLI，断言 stdout/stderr/exit code，不 mock 内部）。此刻必须红且红因与验收一致；既有测试保持绿。
2. 运行 \`${testCommand}\` 记录 red 证据。
3. 只提交测试文件；实现文件、package.json、brief.md 一律不碰。
4. 写 handoffs/test-handoff.json：{ "commit", "test_files", "red_summary", "green_baseline", "manifest_sha256" }。

受保护（不得写入）：${[...plan.protected_paths, "bin/**", "src/**"].join(", ")}（以 PlanHandoff 为准，测试文件除外）。
测试与验收矛盾时停止并报告 REPLAN，不得自行改契约。最终响应附 commit SHA 与 ${testCommand} 摘要。`;
}

const TEST_PATH_RE = /(^|\/)(test|tests|__tests__|spec)(\/|$)|\.test\.[cm]?js$|\.spec\.[cm]?js$/;

export function genExecuteTask(plan: PlanHandoff, ticket: Ticket, attemptsLeft: number, testCommand: string): string {
  // 测试冻结：Test Author 提交后测试资产对 Execute 受保护——即使 ticket.files 列出它们也不可写
  const allowed = ticket.files.filter(
    (f) =>
      !TEST_PATH_RE.test(f) &&
      !plan.protected_paths.some((p) => f.startsWith(p.replace(/\*\*$/, "").replace(/\/$/, ""))),
  );
  const prior = plan.tickets
    .filter((t) => t.depends_on.includes(ticket.id) || ticket.depends_on.includes(t.id))
    .map((t) => t.id)
    .join(",");
  return `你是 Execute 阶段（唯一 writer），只实现 ticket ${ticket.id}：${ticket.title}。

输入：read handoffs/plan-handoff.json（spec/验收）、handoffs/test-handoff.json（测试已冻结，commit 见其中）。

验收条件（逐条满足）：
${ticket.acceptance.map((a, i) => `${i + 1}. ${a}`).join("\n")}

边界：
- 你只允许写：${allowed.join(", ")}；其余（含 test/**——测试已冻结、package.json、brief.md）及 handoffs/** 受保护（本任务指定产出的 execute-handoff.json 除外）
- 运行 \`${testCommand}\`：本票相关测试转绿、全量无回归后 git commit（message 以 feat(${ticket.id}): 开头）
- 测试红：携带完整输出重试；你最多 ${attemptsLeft} 次尝试
- 发现需求歧义/测试与验收矛盾/需改受保护路径：立即停止返回 REPLAN，不得改测试获得绿色
- 无文件修改不得返回成功总结
${prior ? `依赖上下文：${prior}` : ""}

写 handoffs/execute-handoff.json：{ "ticket": "${ticket.id}", "commit", "test_output_summary", "attempts", "open_issues": [] }。
最终响应附 commit SHA 与 ${testCommand} 摘要。`;
}

export function genGateChecklist(plan: PlanHandoff, baseSha: string): string[] {
  return [
    `在集成 HEAD 运行 \`${plan.test_command}\`，退出码 0 才通过（超时/跳过/报告缺失均 fail closed）`,
    `git diff --name-only ${baseSha}..HEAD —— 每个文件必须 ∈ allowed_paths；test/** 在测试 commit 后升级为 protected`,
    `校验 handoffs/{test,execute}-handoff.json 中 SHA 与 git log 一致`,
    `anti-gaming：测试文件必须为黑盒子进程断言（grep 排除 mock 内部模块）；每条 acceptance ≥1 个断言命中`,
    `证据落盘 handoffs/gate-evidence.json（BASE_SHA 用 git rev-parse 实取，禁止手抄 --oneline 前缀）`,
  ];
}

export function genConformanceTask(plan: PlanHandoff, baseSha: string): string {
  return `你是 Conformance 阶段（Gate 已全绿后的低量语义审查，仅 A 问）。只读，不写文件。

仅依据固定输入：handoffs/{plan,test,execute,gate-evidence}.json + git diff ${baseSha}..HEAD + 实际源码。

只回答一个问题（A 问）：有没有硬编码/空壳骗测试？（为通过测试特判输入、伪造输出、检测测试环境走捷径、mock 内部实现）

输出（严格此格式）：
## Review
- Correct: <有证据的正确点>
- Finding: <P0/P1/P2 + 位置 + 证据 + 最小修复，若无则不写>
## Verdict
\`\`\`json
{ "verdict": "PASS" | "FIX_EXECUTE" | "REPLAN", "reasons": string[], "findings": string[] }
\`\`\``;
}

export function dispatchFor(role: Role, taskPrompt: string): { role: Role; deployment: LaunchConfig | null; taskPrompt: string } {
  return { role, deployment: deploymentFor(role), taskPrompt };
}
