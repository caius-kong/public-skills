// Node-scoped write guard for the planner-executor pipeline.
//
// The stage contracts used to say "read only", "only test assets", "only
// allowed_paths" in prose. Prose did not hold: a test author worked around a
// protected path twice, and a planner put the test author's own deliverable
// into protected_paths. This extension makes the primary mutation surface hard:
// it blocks write/edit calls that fall outside the node's boundary, and blocks
// the bash forms that write files behind the tools' backs.
//
// What it does NOT do: sandbox bash. EXECUTE has to run tests and commit, and
// there is no path information in an arbitrary shell command. Bash coverage is
// therefore a denylist of file-writing forms, not a boundary. The remaining
// check for EXECUTE is GATE's diff-versus-allowed_paths comparison after the
// fact. Do not read this guard as proof that a node stayed inside its paths.
import * as fs from "node:fs";
import * as path from "node:path";

const WRITE_TOOLS = new Set(["write", "edit"]);

// Read-only bash allowlist, derived from plan-mode's isSafeCommand
// (~/.pi/agent/extensions/plan-mode/utils.ts). Copied rather than imported:
// that file is a sibling extension's TypeScript source, not a module any
// package exports, and a transitive .ts import is a fragile thing to depend on
// inside a child session's extension host. Same patterns, no cross-extension
// import to break.
const DESTRUCTIVE = [
  /\brm\s+-rf?\b/,
  /\bgit\s+(push|reset\s+--hard|clean\s+-[a-z]*f)/,
  /\b(sudo|su)\b/,
  /(^|[^0-9&>])>{1,2}(?!&)/,
  /\bsed\s+-i/,
  /\btee\b/,
];
const SAFE_FORMS = [
  /^\s*(cat|head|tail|less|more|wc|sort|uniq|cut|nl|diff|cmp)\b/,
  /^\s*(ls|pwd|tree|stat|file|du|df|realpath|dirname|basename)\b/,
  /^\s*(grep|rg|ag|ack|fd|find|locate|which|type)\b/,
  /^\s*git\s+(status|log|diff|show|blame|rev-parse|describe|ls-files|branch\s*$|branch\s+-[av])\b/,
  /^\s*(node|python3?|deno|bun)\s+.*--version\b/,
  /^\s*(echo|printf|true|false)\b(?!.*>)/,
  /^\s*(awk|sed\s+-n|jq|yq|xargs)\b/,
];

function isSafeCommand(command) {
  if (DESTRUCTIVE.some((p) => p.test(command))) return false;
  return SAFE_FORMS.some((p) => p.test(command));
}

// Shell forms that write files without going through the write/edit tools.
const SHELL_WRITE = [
  /(^|[^0-9&>])>{1,2}(?!&)/, // redirections, excluding 2>&1 style
  /\btee\b/,
  /\bsed\s+-i/,
  /\b(rm|mv|cp|dd|truncate|install|ln)\b/,
  // `git commit` is how a node delivers its work, so it is allowed -- but not
  // its all-or-nothing forms: `-a`/`--all` stage files the node never declared,
  // which is the one thing the path boundary exists to prevent.
  /\bgit\s+commit\b[^|;&]*(\s-[a-z]*a[a-z]*\b|--all\b)/,
  /\bgit\s+(checkout|reset|clean|rm|mv|stash|apply|am|merge|rebase|cherry-pick)\b/,
  /\b(python3?|node|perl|ruby)\s+-e\b/,
  /\btouch\b/,
  /\bmkdir\b/,
];

const ALWAYS_PROTECTED = ["handoffs/plan-handoff.json"];
const TESTISH = /(^|\/)(tests?|__tests__|spec)(\/|$)|(^|\/)test_[^/]*$|\.test\.|\.spec\./;

function norm(p) {
  return path.posix.normalize(String(p).replace(/^\.\//, ""));
}

function under(file, prefix) {
  const f = norm(file);
  const p = norm(prefix).replace(/\/$/, "");
  return f === p || f.startsWith(`${p}/`);
}

function withinAny(file, prefixes) {
  return prefixes.some((p) => under(file, p));
}

// Paths a node may write, resolved once per call so a handoff rewritten
// mid-run takes effect on the next tool call.
function policyFor(policy) {
  if (policy.mode === "read-only") {
    return { allow: [], readOnly: true };
  }
  if (policy.mode === "fixed-paths") {
    return { allow: policy.allow || [], readOnly: false };
  }
  // "handoff-paths" / "test-only": the boundaries come from the plan contract
  // in the repo, so a contract rewrite mid-run takes effect immediately.
  const file = path.resolve(policy.cwd || process.cwd(), "handoffs/plan-handoff.json");
  let plan;
  try {
    plan = JSON.parse(fs.readFileSync(file, "utf8"));
  } catch {
    return { allow: [], readOnly: true, reason: `cannot read ${file}` };
  }
  const allowed = (plan.allowed_paths || []).map(norm);
  const protectedPaths = (plan.protected_paths || []).map(norm);
  const open = allowed.filter((p) => !withinAny(p, protectedPaths));
  if (policy.mode === "test-only") {
    // TEST_AUTHOR owns test assets only: the test paths the contract opens,
    // plus its own handoff. Implementation paths stay closed to it.
    //
    // Deliberately computed from `allowed`, not `open`: contracts routinely
    // list the test directory under protected_paths for EXECUTE's sake, and
    // subtracting it here is exactly the contradiction that made two test
    // authors work around their own instructions. `plan-handoff.json` stays
    // closed through ALWAYS_PROTECTED.
    const testish = allowed.filter((p) => TESTISH.test(p));
    return { allow: [...testish, "handoffs/test-handoff.json"], readOnly: false };
  }
  // EXECUTE's own receipt. Same reasoning as the test author's: the contract
  // lists implementation paths, not the node's handoff, and a node that cannot
  // write its receipt hands the parent an extra manual step for no gain.
  return { allow: [...open, "handoffs/execute-handoff.json"], readOnly: false };
}

function blockReason(node, file, policy, detail) {
  const allowed = policy.allow.length ? policy.allow.join(", ") : "nothing (this node is read-only)";
  return [
    `[${node} guard] write blocked: ${file}`,
    detail,
    `This node may write: ${allowed}.`,
    "Do not work around it: record the need in the handoff's `ambiguities` so the parent can route a REPLAN.",
  ]
    .filter(Boolean)
    .join(" ");
}

export function createGuard(node, policy) {
  return function nodeGuard(pi) {
    pi.on("tool_call", async (event) => {
      const current = policyFor(policy);

      if (WRITE_TOOLS.has(event.toolName)) {
        const file = event.input?.path ?? event.input?.file_path ?? "";
        if (!file) return { block: true, reason: blockReason(node, "(unspecified path)", current, "No path was given.") };
        if (current.readOnly) {
          return { block: true, reason: blockReason(node, file, current, current.reason || "This node is read-only.") };
        }
        if (withinAny(file, ALWAYS_PROTECTED)) {
          return { block: true, reason: blockReason(node, file, current, "The plan contract file is never writable.") };
        }
        if (!withinAny(file, current.allow)) {
          return { block: true, reason: blockReason(node, file, current, "Path is outside this node's boundary.") };
        }
        return undefined;
      }

      if (event.toolName === "bash") {
        const command = String(event.input?.command ?? "");
        if (current.readOnly && !isSafeCommand(command)) {
          return {
            block: true,
            reason:
              `[${node} guard] bash blocked: this node is read-only and the command is not a read-only form. ` +
              "Inspect with read/grep/find/ls or a read-only command instead.",
          };
        }
        const hit = SHELL_WRITE.find((p) => p.test(command));
        if (hit) {
          return {
            block: true,
            reason:
              `[${node} guard] bash blocked: the command writes files (matched ${hit}). ` +
              "File writes must go through write/edit inside this node's boundary, so they can be checked.",
          };
        }
      }
      return undefined;
    });
  };
}
