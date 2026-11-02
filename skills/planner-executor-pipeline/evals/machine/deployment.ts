// D2: 角色 → per-run launch 参数。机器步进的唯一路由来源，pipeline prompt 不再手写模型。
export interface LaunchConfig {
  agent: string;
  model: string; // provider/model[:thinking]
  context: "fresh" | "fork";
  note?: string;
}

export type Role = "plan" | "testAuthor" | "execute" | "gate" | "conformance" | "merge";

export const DEPLOYMENT: Record<Role, LaunchConfig | null> = {
  plan: {
    agent: "oracle",
    model: "trendmicro/gpt-5.6-sol",
    context: "fresh",
    note: "访谈臂：kimi-k3 在 contact_supervisor 可选参数上 4/4 生成失败，禁用于含访谈阶段",
  },
  testAuthor: { agent: "worker", model: "trendmicro/glm-5.3-flash:max", context: "fresh" },
  execute: {
    agent: "worker",
    model: "trendmicro/glm-5.3-flash:max",
    context: "fresh",
    note: "对齐 README worker 档（flash+满档）；逻辑失败重试或 REPLAN，不升级模型档位",
  },
  gate: null, // 父会话确定性执行，无 LLM
  conformance: {
    agent: "worker",
    model: "trendmicro/glm-5.3-flash:max",
    context: "fresh",
    note: "收敛后仅保留 A 问（硬编码/空壳）；对齐 README worker 档（flash+满档），Gate 绿后低量语义审查",
  },
  merge: null, // 父会话 + 用户 y/n
};

export function deploymentFor(role: Role): LaunchConfig | null {
  return DEPLOYMENT[role] ?? null;
}
