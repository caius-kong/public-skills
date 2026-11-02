#!/usr/bin/env node
// Unit-level fixtures for the node guards: drive the tool_call handler directly.
//
// A guard that only ever lets calls through looks exactly like a working guard,
// so every policy needs at least one case that must be blocked. Nothing here
// dispatches a model, so this is cheap enough to run on every change.
//
// Exit codes: 0 = all cases as expected, 1 = a case disagreed, 2 = cannot judge.
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";

const DIR = path.dirname(new URL(import.meta.url).pathname);
const EXT = path.resolve(DIR, "../../extensions");

const PLAN_HANDOFF = {
  allowed_paths: ["src/calc.py", "tests/test_calc.py", "handoffs/test-handoff.json"],
  protected_paths: ["tests/test_calc.py", "handoffs/plan-handoff.json"],
};

function tempRepo(planJson) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "guard-"));
  if (planJson) {
    fs.mkdirSync(path.join(dir, "handoffs"), { recursive: true });
    fs.writeFileSync(path.join(dir, "handoffs/plan-handoff.json"), JSON.stringify(planJson));
  }
  return dir;
}

// Call the extension with a fake pi, return the handler's result for one call.
async function drive(extension, event, cwd) {
  const handlers = [];
  const pi = { on: (name, fn) => name === "tool_call" && handlers.push(fn) };
  const mod = await import(path.join(EXT, extension));
  mod.default(pi);
  if (handlers.length !== 1) throw new Error(`${extension} registered ${handlers.length} tool_call handlers`);
  const prev = process.cwd();
  process.chdir(cwd);
  try {
    return await handlers[0](event, {});
  } finally {
    process.chdir(prev);
  }
}

const write = (p) => ({ toolName: "write", input: { path: p, content: "x" } });
const bash = (command) => ({ toolName: "bash", input: { command } });
const read = (p) => ({ toolName: "read", input: { path: p } });

const cases = [
  // PLAN: read-only.
  ["guard-plan.js", read("src/calc.py"), "allow", "reading is the job"],
  ["guard-plan.js", bash("git log --oneline -5"), "allow", "read-only inspection"],
  ["guard-plan.js", bash("rg -n TODO src"), "allow", "read-only search"],
  ["guard-plan.js", write("notes.md"), "block", "PLAN must not write anything"],
  ["guard-plan.js", bash("echo hi > notes.md"), "block", "redirection writes a file"],
  ["guard-plan.js", bash("sed -i 's/a/b/' src/calc.py"), "block", "in-place edit"],
  ["guard-plan.js", bash("git commit -am wip"), "block", "commits mutate the repo"],

  // EVIDENCE: evidence files only.
  ["guard-evidence.js", write("handoffs/research/csv.md"), "allow", "evidence pack"],
  ["guard-evidence.js", write("src/calc.py"), "block", "not an evidence path"],
  ["guard-evidence.js", write("handoffs/plan-handoff.json"), "block", "contract file is never writable"],

  // TEST_AUTHOR: test assets only, from the contract.
  ["guard-test-author.js", write("tests/test_calc.py"), "allow", "declared test path"],
  ["guard-test-author.js", write("handoffs/test-handoff.json"), "allow", "own handoff"],
  ["guard-test-author.js", write("src/calc.py"), "block", "implementation is not the test author's"],
  ["guard-test-author.js", write("handoffs/plan-handoff.json"), "block", "contract file is never writable"],

  ["guard-test-author.js", bash("git commit -m test"), "allow", "a node delivers work by committing"],

  // EXECUTE: allowed minus protected.
  ["guard-execute.js", write("src/calc.py"), "allow", "declared implementation path"],
  ["guard-execute.js", write("handoffs/execute-handoff.json"), "allow", "own handoff"],
  ["guard-execute.js", bash("git commit -m 'feat(T1): x'"), "allow", "a node delivers work by committing"],
  ["guard-execute.js", bash("git commit -am wip"), "block", "staging everything defeats the path boundary"],
  ["guard-execute.js", bash("git commit --all -m wip"), "block", "staging everything defeats the path boundary"],
  ["guard-execute.js", write("tests/test_calc.py"), "block", "tests are frozen for EXECUTE"],
  ["guard-execute.js", write("handoffs/plan-handoff.json"), "block", "contract file is never writable"],
  ["guard-execute.js", write("src/other.py"), "block", "outside allowed_paths"],
];

let failures = 0;
const repo = tempRepo(PLAN_HANDOFF);
const bare = tempRepo(null); // no contract on disk

for (const [ext, event, expected, why] of cases) {
  const result = await drive(ext, event, repo);
  const got = result?.block ? "block" : "allow";
  const ok = got === expected;
  if (!ok) failures += 1;
  console.log(`${ok ? "ok  " : "FAIL"} ${ext.padEnd(22)} ${got.padEnd(5)} (want ${expected.padEnd(5)}) ${why}`);
  if (ok && got === "block") console.log(`     reason: ${String(result.reason).slice(0, 110)}`);
}

// Fail closed: with no contract on disk, a contract-driven guard must not allow writes.
for (const ext of ["guard-test-author.js", "guard-execute.js"]) {
  const result = await drive(ext, write("src/calc.py"), bare);
  const ok = Boolean(result?.block);
  if (!ok) failures += 1;
  console.log(`${ok ? "ok  " : "FAIL"} ${ext.padEnd(22)} ${ok ? "block" : "allow"} (want block) no contract on disk -> fail closed`);
}

fs.rmSync(repo, { recursive: true, force: true });
fs.rmSync(bare, { recursive: true, force: true });

if (failures) {
  console.log(`\nFAIL: ${failures} case(s) disagreed.`);
  process.exit(1);
}
console.log(`\nPASS: ${cases.length + 2} cases, every policy blocks what it must and allows what it must.`);
