import { test } from "node:test";
import assert from "node:assert";
import { initialState, step, MAX_REPLAN_ROUNDS, MAX_ATTEMPTS_PER_TICKET, type MachineState } from "./machine.ts";
import { DEPLOYMENT, deploymentFor } from "./deployment.ts";
import { genPlanTask, genTestAuthorTask, genExecuteTask, genConformanceTask, genGateChecklist } from "./prompts.ts";
import type { PlanHandoff } from "./schemas.ts";

const BASE = "cce636142c552bcba05371abb18548956fedbb2d";

const PLAN: PlanHandoff = {
  spec: "spec text",
  tickets: [
    { id: "T2", title: "second", acceptance: ["T2 acceptance a1"], depends_on: ["T1"], files: ["bin/cli.js"] },
    { id: "T1", title: "first", acceptance: ["T1 acceptance a1", "T1 acceptance a2"], depends_on: [], files: ["bin/cli.js"] },
  ],
  dag: "T1 -> T2",
  allowed_paths: ["bin/cli.js", "test/cli.test.js"],
  protected_paths: ["brief.md", "package.json"],
  test_command: "npm test",
  ambiguities: [],
};

function happyToGate(s: MachineState): MachineState {
  let r = step(s, { type: "PLAN_DONE", planHandoff: PLAN, baseSha: BASE });
  assert.strictEqual(r.error, undefined, r.error);
  r = step(r.state, { type: "TESTS_FROZEN", testHandoff: { commit: "fa2a00cbaceb5a7", test_files: ["test/cli.test.js"], red_summary: "4 red", green_baseline: "2 green", manifest_sha256: "abc123" } });
  assert.strictEqual(r.error, undefined, r.error);
  r = step(r.state, { type: "TICKET_DONE", executeHandoff: { ticket: "T1", commit: "a0810238f9d761e", test_output_summary: "green", attempts: 0, open_issues: [] } });
  assert.strictEqual(r.error, undefined, r.error);
  r = step(r.state, { type: "TICKET_DONE", executeHandoff: { ticket: "T2", commit: "2b3c521fcf7e63c", test_output_summary: "green", attempts: 0, open_issues: [] } });
  assert.strictEqual(r.error, undefined, r.error);
  return r.state;
}

const GATE_EVIDENCE = {
  BASE_SHA: BASE,
  INTEGRATION_HEAD: "2b3c521fcf7e63c4a1d4d2bb3d0ba72621b62122",
  test_command: "npm test",
  test_exit_code: 0,
  cumulative_diff_files: ["bin/cli.js", "test/cli.test.js"],
  allowed_paths_violation: false,
  protected_paths_violation: false,
};

test("happy path: PLAN→TEST_AUTHOR→EXECUTE(T1)→EXECUTE(T2)→GATE→CONFORMANCE→MERGE_WAIT", () => {
  let r = step(initialState(), { type: "PLAN_DONE", planHandoff: PLAN, baseSha: BASE });
  assert.strictEqual(r.state.stage, "TEST_AUTHOR");
  assert.strictEqual(r.dispatch?.role, "testAuthor");
  assert.strictEqual(r.dispatch?.deployment?.model, "trendmicro/glm-5.3-flash:max");
  assert.match(r.dispatch!.taskPrompt, /T2 acceptance a1/);

  r = step(r.state, { type: "TESTS_FROZEN", testHandoff: { commit: "fa2a00cbaceb5a7", test_files: ["test/cli.test.js"], red_summary: "4 red", green_baseline: "2 green", manifest_sha256: "abc123" } });
  assert.strictEqual(r.state.stage, "EXECUTE");
  assert.strictEqual(r.dispatch?.role, "execute");
  assert.strictEqual(r.dispatch?.deployment?.model, "trendmicro/glm-5.3-flash:max");
  assert.match(r.dispatch!.taskPrompt, /ticket T1：/); // DAG 拓扑序：T1 先行

  r = step(r.state, { type: "TICKET_DONE", executeHandoff: { ticket: "T1", commit: "a0810238f9d761e", test_output_summary: "green", attempts: 0, open_issues: [] } });
  assert.strictEqual(r.state.stage, "EXECUTE");
  assert.match(r.dispatch!.taskPrompt, /ticket T2：/);

  r = step(r.state, { type: "TICKET_DONE", executeHandoff: { ticket: "T2", commit: "2b3c521fcf7e63c", test_output_summary: "green", attempts: 0, open_issues: [] } });
  assert.strictEqual(r.state.stage, "GATE");
  assert.ok(r.dispatch === undefined, "GATE 无子代理 dispatch");
  assert.ok(r.gateChecklist!.length >= 4);

  r = step(r.state, { type: "GATE_PASS", gateEvidence: GATE_EVIDENCE });
  assert.strictEqual(r.state.stage, "CONFORMANCE");
  assert.strictEqual(r.dispatch?.deployment?.model, "trendmicro/glm-5.3-flash:max");

  r = step(r.state, { type: "CONF_VERDICT", verdict: { verdict: "PASS", reasons: [], findings: [] } });
  assert.strictEqual(r.state.stage, "MERGE_WAIT");
});

test("DAG 拓扑排序：T2 depends_on T1 → 执行序 T1 先", () => {
  let r = step(initialState(), { type: "PLAN_DONE", planHandoff: PLAN, baseSha: BASE });
  assert.deepStrictEqual(r.state.ticketOrder, ["T1", "T2"]);
});

test("依赖环 → PLAN_DONE 报错且状态不变", () => {
  const cyc = { ...PLAN, tickets: [{ id: "A", title: "a", acceptance: ["x"], depends_on: ["B"], files: ["f"] }, { id: "B", title: "b", acceptance: ["x"], depends_on: ["A"], files: ["f"] }] };
  const r = step(initialState(), { type: "PLAN_DONE", planHandoff: cyc, baseSha: BASE });
  assert.match(r.error!, /依赖环/);
  assert.strictEqual(r.state.stage, "PLAN");
});

test("PlanHandoff schema 校验失败 → error（父会话随后发 REPLAN_REQUEST）", () => {
  const bad = { spec: "", tickets: [], allowed_paths: [], test_command: "", ambiguities: [] };
  const r = step(initialState(), { type: "PLAN_DONE", planHandoff: bad, baseSha: BASE });
  assert.match(r.error!, /schema 校验失败/);
  assert.strictEqual(r.state.stage, "PLAN");
  const r2 = step(r.state, { type: "REPLAN_REQUEST", reason: "handoff 坏" });
  assert.strictEqual(r2.state.stage, "PLAN");
  assert.strictEqual(r2.state.replanRound, 1);
});

test("REPLAN_REQUEST ×3 后第 4 次 HALTED（fail closed）", () => {
  let s = initialState();
  for (let i = 1; i <= MAX_REPLAN_ROUNDS; i++) {
    const r = step(s, { type: "REPLAN_REQUEST", reason: `reason ${i}` });
    assert.strictEqual(r.state.stage, "PLAN");
    assert.strictEqual(r.state.replanRound, i);
    s = r.state;
  }
  const r = step(s, { type: "REPLAN_REQUEST", reason: "one too many" });
  assert.strictEqual(r.state.stage, "HALTED");
  assert.match(r.state.haltedReason!, /耗尽/);
});

test("TICKET_FAILED：attempts 递增并重派同票；第 3 次失败自动 REPLAN", () => {
  let r = step(initialState(), { type: "PLAN_DONE", planHandoff: PLAN, baseSha: BASE });
  r = step(r.state, { type: "TESTS_FROZEN", testHandoff: { commit: "fa2a00cbaceb5a7", test_files: ["t"], red_summary: "r", green_baseline: "g", manifest_sha256: "m" } });
  for (let i = 1; i < MAX_ATTEMPTS_PER_TICKET; i++) {
    r = step(r.state, { type: "TICKET_FAILED", ticketId: "T1", reason: "tests red" });
    assert.strictEqual(r.state.stage, "EXECUTE");
    assert.strictEqual(r.state.attempts["T1"], i);
    assert.match(r.dispatch!.taskPrompt, new RegExp(`最多 ${MAX_ATTEMPTS_PER_TICKET - i} 次尝试`));
  }
  const before = r.state.replanRound;
  r = step(r.state, { type: "TICKET_FAILED", ticketId: "T1", reason: "tests red again" });
  assert.strictEqual(r.state.stage, "PLAN"); // 强制 REPLAN
  assert.strictEqual(r.state.replanRound, before + 1);
});

test("FIX_EXECUTE：回 EXECUTE 同票、不耗 replan_round", () => {
  let r = step(initialState(), { type: "PLAN_DONE", planHandoff: PLAN, baseSha: BASE });
  r = step(r.state, { type: "TESTS_FROZEN", testHandoff: { commit: "fa2a00cbaceb5a7", test_files: ["t"], red_summary: "r", green_baseline: "g", manifest_sha256: "m" } });
  r = step(r.state, { type: "TICKET_DONE", executeHandoff: { ticket: "T1", commit: "a0810238f9d761e", test_output_summary: "green", attempts: 0, open_issues: [] } });
  r = step(r.state, { type: "TICKET_DONE", executeHandoff: { ticket: "T2", commit: "2b3c521fcf7e63c", test_output_summary: "green", attempts: 0, open_issues: [] } });
  r = step(r.state, { type: "GATE_PASS", gateEvidence: GATE_EVIDENCE });
  const rr = r.state.replanRound;
  r = step(r.state, { type: "CONF_VERDICT", verdict: { verdict: "FIX_EXECUTE", reasons: ["impl bug"], findings: [] } });
  assert.strictEqual(r.state.stage, "EXECUTE");
  assert.strictEqual(r.state.replanRound, rr);
  assert.match(r.dispatch!.taskPrompt, /ticket T2：/); // cursor 停在最后完成的票
});

test("非法转移被拒绝", () => {
  const r = step(initialState(), { type: "TICKET_DONE", executeHandoff: { ticket: "T1", commit: "a0810238f9d761e", test_output_summary: "g", attempts: 0, open_issues: [] } });
  assert.match(r.error!, /不接受该事件/);
  const s = happyToGate(initialState());
  const r2 = step(s, { type: "REPLAN_REQUEST", reason: "x" }); // GATE 阶段 GATE_FAIL 归一化为 REPLAN 是合法的；直接 REPLAN_REQUEST 也合法
  assert.strictEqual(r2.error, undefined);
});

test("GATE_PASS 内容校验：exit≠0 / 越权 / BASE 不符均拒绝", () => {
  const s = happyToGate(initialState());
  const bad1 = step(s, { type: "GATE_PASS", gateEvidence: { ...GATE_EVIDENCE, test_exit_code: 1 } });
  assert.match(bad1.error!, /失败标记/);
  const bad2 = step(s, { type: "GATE_PASS", gateEvidence: { ...GATE_EVIDENCE, allowed_paths_violation: true } });
  assert.match(bad2.error!, /失败标记/);
  const bad3 = step(s, { type: "GATE_PASS", gateEvidence: { ...GATE_EVIDENCE, BASE_SHA: "deadbeefdeadbee" } });
  assert.match(bad3.error!, /不一致/);
});

test("TICKET_DONE 乱序（机器期望 T1 却收到 T2）被拒绝", () => {
  let r = step(initialState(), { type: "PLAN_DONE", planHandoff: PLAN, baseSha: BASE });
  r = step(r.state, { type: "TESTS_FROZEN", testHandoff: { commit: "fa2a00cbaceb5a7", test_files: ["t"], red_summary: "r", green_baseline: "g", manifest_sha256: "m" } });
  const r2 = step(r.state, { type: "TICKET_DONE", executeHandoff: { ticket: "T2", commit: "2b3c521fcf7e63c", test_output_summary: "g", attempts: 0, open_issues: [] } });
  assert.match(r2.error!, /DAG 顺序强制/);
});

test("deployment config：每 role 完整、gate/merge 为父会话、模型 id 带 provider", () => {
  for (const [role, cfg] of Object.entries(DEPLOYMENT)) {
    if (role === "gate" || role === "merge") {
      assert.strictEqual(cfg, null, `${role} 应为父会话执行`);
    } else {
      assert.ok(cfg && cfg.agent && cfg.model && cfg.context === "fresh", `${role} 配置不完整`);
      assert.match(cfg.model, /^trendmicro\//, `${role} 模型须全限定`);
    }
  }
  assert.strictEqual(deploymentFor("gate"), null);
});

test("prompt 生成器：关键契约必须出现在生成结果中", () => {
  const plan = genPlanTask("brief.md");
  assert.match(plan, /contact_supervisor 必须同时携带 message/); // 模型硬门槛
  assert.match(plan, /grill-me/);
  assert.match(plan, /to-spec/);
  assert.match(plan, /to-tickets/);

  const ta = genTestAuthorTask(PLAN, "npm test");
  assert.match(ta, /T1 acceptance a1/);
  assert.match(ta, /brief\.md/); // protected
  assert.match(ta, /npm test/);
  assert.match(ta, /red-first/);

  const ex = genExecuteTask(PLAN, PLAN.tickets.find((t) => t.id === "T2")!, 3, "npm test");
  assert.match(ex, /ticket T2：/);
  assert.match(ex, /T2 acceptance a1/);
  assert.match(ex, /只允许写/);
  assert.doesNotMatch(ex, /T1 acceptance/); // 单票隔离：其他票验收不得泄漏

  // 测试冻结：ticket.files 含测试文件时，Execute 的 allowed 必须剔除
  const tWithTests = { id: "TX", title: "x", acceptance: ["a"], depends_on: [], files: ["bin/cli.js", "test/cli.test.js"] };
  const exTx = genExecuteTask(PLAN, tWithTests, 3, "npm test");
  assert.match(exTx, /你只允许写：bin\/cli.js/);
  assert.doesNotMatch(exTx, /你只允许写：bin\/cli.js, test/);

  const conf = genConformanceTask(PLAN, BASE);
  assert.match(conf, /硬编码\/空壳/);
  assert.match(conf, /"PASS" \| "FIX_EXECUTE" \| "REPLAN"/);

  const gate = genGateChecklist(PLAN, BASE);
  assert.ok(gate.some((l) => l.includes("git rev-parse")));
  assert.ok(gate.some((l) => l.includes("anti-gaming")));
});
