import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { test } from "node:test";
import { pathToFileURL } from "node:url";
import planInterviewChannelTimeout from "../../../extensions/plan-interview-channel-timeout.js";

const nativeChannelPath = process.env.PI_SUBAGENTS_NATIVE_CHANNEL
  ?? path.join(os.homedir(), ".pi/agent/npm/node_modules/pi-subagents/src/intercom/native-supervisor-channel.js");
const { registerNativeSupervisorClient } = await import(pathToFileURL(nativeChannelPath).href);

const ASK_TIMEOUT_ENV = "PI_INTERCOM_ASK_TIMEOUT_MS";
const CHILD_RUNNER_ENV = "PI_SUBAGENT_CHILD";

function restoreEnv(name, value) {
  if (value === undefined) delete process.env[name];
  else process.env[name] = value;
}

async function waitForRequest(requestDir) {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    const files = readdirSync(requestDir);
    if (files.length > 0) return path.join(requestDir, files[0]);
    await new Promise((resolve) => setTimeout(resolve, 10));
  }
  throw new Error("Native supervisor request was not written.");
}

test("dedicated PLAN extension configures the actual native request for one day before the first ask", async (t) => {
  const oldChild = process.env[CHILD_RUNNER_ENV];
  const oldTimeout = process.env[ASK_TIMEOUT_ENV];
  const channelDir = mkdtempSync(path.join(os.tmpdir(), "plan-interview-channel-"));
  const requestsDir = path.join(channelDir, "requests");
  const repliesDir = path.join(channelDir, "replies");
  mkdirSync(requestsDir);
  mkdirSync(repliesDir);
  t.after(() => {
    restoreEnv(CHILD_RUNNER_ENV, oldChild);
    restoreEnv(ASK_TIMEOUT_ENV, oldTimeout);
    rmSync(channelDir, { recursive: true, force: true });
  });

  process.env[CHILD_RUNNER_ENV] = "1";
  process.env[ASK_TIMEOUT_ENV] = "600000";
  planInterviewChannelTimeout({});

  let tool;
  registerNativeSupervisorClient({
    getAllTools: () => [],
    registerTool: (definition) => { tool = definition; },
  }, {
    channelDir,
    runId: "plan-run",
    agent: "plan",
    childIndex: 0,
    orchestratorSessionId: "parent-session",
  });
  assert.ok(tool, "native child-side contact_supervisor tool is registered");

  const waiting = tool.execute("tool-call-1", {
    reason: "interview_request",
    message: "Please settle the unresolved choice.",
    interview: { round: 1, questions: ["Which option should the plan use?"] },
  });
  const requestPath = await waitForRequest(requestsDir);
  const request = JSON.parse(readFileSync(requestPath, "utf8"));
  assert.equal(request.expiresAt - request.createdAt, 86_400_000);

  writeFileSync(path.join(repliesDir, `${request.id}.json`), JSON.stringify({
    type: "subagent.supervisor.reply",
    requestId: request.id,
    createdAt: Date.now(),
    message: "Keep the current option.",
  }));
  const result = await waiting;
  assert.match(result.content[0].text, /Keep the current option\./);
});

test("the extension guard throws before changing a foreground/parent environment", () => {
  const oldChild = process.env[CHILD_RUNNER_ENV];
  const oldTimeout = process.env[ASK_TIMEOUT_ENV];
  delete process.env[CHILD_RUNNER_ENV];
  process.env[ASK_TIMEOUT_ENV] = "600000";
  try {
    assert.throws(() => planInterviewChannelTimeout({}), /requires a detached async child runner/);
    assert.equal(process.env[ASK_TIMEOUT_ENV], "600000");
  } finally {
    restoreEnv(CHILD_RUNNER_ENV, oldChild);
    restoreEnv(ASK_TIMEOUT_ENV, oldTimeout);
  }
});

test("a child that does not load the PLAN extension keeps the native 10-minute default", async (t) => {
  const oldChild = process.env[CHILD_RUNNER_ENV];
  const oldTimeout = process.env[ASK_TIMEOUT_ENV];
  const channelDir = mkdtempSync(path.join(os.tmpdir(), "non-plan-channel-"));
  const requestsDir = path.join(channelDir, "requests");
  const repliesDir = path.join(channelDir, "replies");
  mkdirSync(requestsDir);
  mkdirSync(repliesDir);
  t.after(() => {
    restoreEnv(CHILD_RUNNER_ENV, oldChild);
    restoreEnv(ASK_TIMEOUT_ENV, oldTimeout);
    rmSync(channelDir, { recursive: true, force: true });
  });

  process.env[CHILD_RUNNER_ENV] = "1";
  delete process.env[ASK_TIMEOUT_ENV];
  let tool;
  registerNativeSupervisorClient({
    getAllTools: () => [],
    registerTool: (definition) => { tool = definition; },
  }, {
    channelDir,
    runId: "research-run",
    agent: "researcher",
    childIndex: 0,
    orchestratorSessionId: "parent-session",
  });
  const waiting = tool.execute("tool-call-2", { reason: "interview_request", message: "Need a ruling." });
  const requestPath = await waitForRequest(requestsDir);
  const request = JSON.parse(readFileSync(requestPath, "utf8"));
  assert.equal(request.expiresAt - request.createdAt, 600_000);
  writeFileSync(path.join(repliesDir, `${request.id}.json`), JSON.stringify({
    type: "subagent.supervisor.reply",
    requestId: request.id,
    createdAt: Date.now(),
    message: "Resolved.",
  }));
  await waiting;
});
