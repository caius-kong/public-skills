// D1: 确定性管线状态机。计数器/路由/阶段转移全部 owned by code；LLM 只做阶段内模型工作。
// 设计收敛（相对旧 prompt 契约）：review_round 计数器删除——显式转移使"无状态变化重复审查"在构造上不可达。
import type { PlanHandoff, Ticket, GateEvidence, Verdict, TestHandoff, ExecuteHandoff } from "./schemas.ts";
import { PlanHandoffSchema, TestHandoffSchema, ExecuteHandoffSchema, GateEvidenceSchema, VerdictSchema } from "./schemas.ts";
import { deploymentFor, type LaunchConfig, type Role } from "./deployment.ts";
import { genPlanTask, genTestAuthorTask, genExecuteTask, genGateChecklist, genConformanceTask } from "./prompts.ts";

export const MAX_REPLAN_ROUNDS = 3;
export const MAX_ATTEMPTS_PER_TICKET = 3;

export type Stage = "PLAN" | "TEST_AUTHOR" | "EXECUTE" | "GATE" | "CONFORMANCE" | "MERGE_WAIT" | "HALTED";

export interface MachineState {
  stage: Stage;
  replanRound: number;
  attempts: Record<string, number>;
  plan?: PlanHandoff;
  testHandoff?: TestHandoff;
  baseSha?: string;
  ticketOrder: string[];
  ticketCursor: number; // 下一个待实现 ticket 的下标
  haltedReason?: string;
  history: Array<{ event: string; from: Stage; to: Stage }>;
}

export type Event =
  | { type: "PLAN_DONE"; planHandoff: unknown; baseSha: string }
  | { type: "TESTS_FROZEN"; testHandoff: unknown }
  | { type: "TICKET_DONE"; executeHandoff: unknown }
  | { type: "TICKET_FAILED"; ticketId: string; reason: string }
  | { type: "GATE_PASS"; gateEvidence: unknown }
  | { type: "GATE_FAIL"; reason: string }
  | { type: "CONF_VERDICT"; verdict: Verdict }
  | { type: "REPLAN_REQUEST"; reason: string };

export interface Dispatch {
  role: Role;
  deployment: LaunchConfig | null; // null = 父会话自行执行（GATE/MERGE）
  taskPrompt: string;
}

export interface StepResult {
  state: MachineState;
  dispatch?: Dispatch;
  gateChecklist?: string[];
  error?: string;
}

export function initialState(): MachineState {
  return { stage: "PLAN", replanRound: 0, attempts: {}, ticketOrder: [], ticketCursor: 0, history: [] };
}

/** 机器启动：返回初始 PLAN dispatch（不发事件） */
export function boot(): StepResult {
  const s = initialState();
  return { state: s, dispatch: dispatchForStage(s) };
}

function push(s: MachineState, event: string): void {
  s.history.push({ event, from: s.stage, to: s.stage });
}

function fail(s: MachineState, event: string, error: string): StepResult {
  return { state: s, error: `${event}: ${error}` };
}

function dispatchForStage(s: MachineState): Dispatch | undefined {
  switch (s.stage) {
    case "PLAN": {
      const replanned = s.replanRound > 0 ? `第 ${s.replanRound} 轮重规划` : undefined;
      return { role: "plan", deployment: deploymentFor("plan"), taskPrompt: genPlanTask("brief.md", { replanned }) };
    }
    case "TEST_AUTHOR":
      return {
        role: "testAuthor",
        deployment: deploymentFor("testAuthor"),
        taskPrompt: genTestAuthorTask(s.plan!, s.plan!.test_command),
      };
    case "EXECUTE": {
      const ticket = currentTicket(s);
      const left = MAX_ATTEMPTS_PER_TICKET - (s.attempts[ticket.id] ?? 0);
      return {
        role: "execute",
        deployment: deploymentFor("execute"),
        taskPrompt: genExecuteTask(s.plan!, ticket, left, s.plan!.test_command),
      };
    }
    case "CONFORMANCE":
      return {
        role: "conformance",
        deployment: deploymentFor("conformance"),
        taskPrompt: genConformanceTask(s.plan!, s.baseSha!),
      };
    default:
      return undefined;
  }
}

function currentTicket(s: MachineState): Ticket {
  const id = s.ticketOrder[s.ticketCursor];
  return s.plan!.tickets.find((t) => t.id === id)!;
}

function topoOrder(plan: PlanHandoff): string[] | string {
  const byId = new Map(plan.tickets.map((t) => [t.id, t]));
  const visited = new Map<string, "visiting" | "done">();
  const order: string[] = [];
  function visit(id: string): string | null {
    const mark = visited.get(id);
    if (mark === "done") return null;
    if (mark === "visiting") return `依赖环：${id}`;
    visited.set(id, "visiting");
    const t = byId.get(id);
    if (!t) return `未知 ticket 依赖：${id}`;
    for (const dep of t.depends_on) {
      const err = visit(dep);
      if (err) return err;
    }
    visited.set(id, "done");
    order.push(id);
    return null;
  }
  for (const t of plan.tickets) {
    const err = visit(t.id);
    if (err) return err;
  }
  return order;
}

export function step(state: MachineState, event: Event): StepResult {
  const s: MachineState = structuredClone(state);

  // 全局可用：REPLAN_REQUEST（fail-closed 出口；GATE_FAIL 归一化到此）
  if (event.type === "REPLAN_REQUEST" || event.type === "GATE_FAIL") {
    const reason = event.type === "GATE_FAIL" ? event.reason : event.reason;
    s.replanRound += 1;
    if (s.replanRound > MAX_REPLAN_ROUNDS) {
      s.stage = "HALTED";
      s.haltedReason = `replan_round 耗尽（${MAX_REPLAN_ROUNDS}）：${reason}`;
      push(s, event.type);
      return { state: s };
    }
    s.stage = "PLAN";
    s.ticketCursor = 0;
    s.attempts = {}; // 新一轮重规划重置尝试
    push(s, event.type);
    return { state: s, dispatch: dispatchForStage(s) };
  }

  switch (s.stage) {
    case "PLAN": {
      if (event.type !== "PLAN_DONE") return fail(s, event.type, `PLAN 阶段不接受该事件`);
      const parsed = PlanHandoffSchema.safeParse(event.planHandoff);
      if (!parsed.success) {
        return fail(s, event.type, `PlanHandoff schema 校验失败：${parsed.error.issues.map((i) => `${i.path.join(".")}:${i.message}`).join("; ")}`);
      }
      const order = topoOrder(parsed.data);
      if (typeof order === "string") return fail(s, event.type, order);
      s.plan = parsed.data;
      s.baseSha = event.baseSha;
      s.ticketOrder = order;
      s.ticketCursor = 0;
      s.stage = "TEST_AUTHOR";
      push(s, event.type);
      return { state: s, dispatch: dispatchForStage(s) };
    }

    case "TEST_AUTHOR": {
      if (event.type !== "TESTS_FROZEN") return fail(s, event.type, `TEST_AUTHOR 阶段不接受该事件`);
      const parsed = TestHandoffSchema.safeParse(event.testHandoff);
      if (!parsed.success) {
        return fail(s, event.type, `TestHandoff schema 校验失败：${parsed.error.issues.map((i) => `${i.path.join(".")}:${i.message}`).join("; ")}`);
      }
      s.testHandoff = parsed.data;
      s.stage = "EXECUTE";
      s.ticketCursor = 0;
      push(s, event.type);
      return { state: s, dispatch: dispatchForStage(s) };
    }

    case "EXECUTE": {
      if (event.type === "TICKET_FAILED") {
        const id = event.ticketId;
        if (!s.ticketOrder.includes(id)) return fail(s, event.type, `未知 ticket：${id}`);
        s.attempts[id] = (s.attempts[id] ?? 0) + 1;
        if (s.attempts[id] >= MAX_ATTEMPTS_PER_TICKET) {
          // 尝试耗尽 → 强制 REPLAN（走统一出口）
          return step(s, { type: "REPLAN_REQUEST", reason: `ticket ${id} 实现尝试耗尽（${MAX_ATTEMPTS_PER_TICKET}）` });
        }
        push(s, event.type);
        return { state: s, dispatch: dispatchForStage(s) }; // 同票重试
      }
      if (event.type !== "TICKET_DONE") return fail(s, event.type, `EXECUTE 阶段不接受该事件`);
      const parsed = ExecuteHandoffSchema.safeParse(event.executeHandoff);
      if (!parsed.success) {
        return fail(s, event.type, `ExecuteHandoff schema 校验失败：${parsed.error.issues.map((i) => `${i.path.join(".")}:${i.message}`).join("; ")}`);
      }
      const expected = s.ticketOrder[s.ticketCursor];
      if (parsed.data.ticket !== expected) {
        return fail(s, event.type, `ExecuteHandoff.ticket=${parsed.data.ticket}，机器期望 ${expected}（DAG 顺序强制）`);
      }
      s.ticketCursor += 1;
      push(s, event.type);
      if (s.ticketCursor >= s.ticketOrder.length) {
        s.stage = "GATE";
        return { state: s, gateChecklist: genGateChecklist(s.plan!, s.baseSha!) };
      }
      return { state: s, dispatch: dispatchForStage(s) };
    }

    case "GATE": {
      if (event.type === "GATE_PASS") {
        const parsed = GateEvidenceSchema.safeParse(event.gateEvidence);
        if (!parsed.success) {
          return fail(s, event.type, `GateEvidence schema 校验失败：${parsed.error.issues.map((i) => `${i.path.join(".")}:${i.message}`).join("; ")}`);
        }
        const ge = parsed.data;
        if (ge.test_exit_code !== 0 || ge.allowed_paths_violation || ge.protected_paths_violation) {
          return fail(s, event.type, "GateEvidence 内容含失败标记（exit≠0 或越权），不允许 GATE_PASS");
        }
        if (ge.BASE_SHA !== s.baseSha) return fail(s, event.type, `GateEvidence.BASE_SHA=${ge.BASE_SHA} 与机器基线 ${s.baseSha} 不一致`);
        s.stage = "CONFORMANCE";
        push(s, event.type);
        return { state: s, dispatch: dispatchForStage(s) };
      }
      return fail(s, event.type, `GATE 阶段仅接受 GATE_PASS/GATE_FAIL`);
    }

    case "CONFORMANCE": {
      if (event.type !== "CONF_VERDICT") return fail(s, event.type, `CONFORMANCE 阶段不接受该事件`);
      const v = event.verdict;
      if (v.verdict === "PASS") {
        s.stage = "MERGE_WAIT";
        push(s, event.type);
        return { state: s };
      }
      if (v.verdict === "FIX_EXECUTE") {
        // 回当前 ticket 的 Execute（不耗 replan_round）；cursor 耗尽（全部票已完成）时指回最后完成的票
        if (s.ticketCursor >= s.ticketOrder.length) s.ticketCursor = s.ticketOrder.length - 1;
        s.stage = "EXECUTE";
        push(s, event.type);
        return { state: s, dispatch: dispatchForStage(s) };
      }
      // REPLAN → 统一出口
      return step(s, { type: "REPLAN_REQUEST", reason: v.reasons.join("; ") || "Conformance REPLAN" });
    }

    default:
      return fail(s, event.type, `阶段 ${s.stage} 为终态/父会话阶段，不接受事件`);
  }
}
