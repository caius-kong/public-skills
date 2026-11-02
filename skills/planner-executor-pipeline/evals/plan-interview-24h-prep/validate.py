#!/usr/bin/env python3
"""Static checks for PLAN interview continuity and dedicated timeout wiring."""
from pathlib import Path
import re

repo = Path(__file__).resolve().parents[5]
pipeline = repo / "skills/pi/planner-executor-pipeline"
skill = (pipeline / "SKILL.md").read_text()
adapter = (pipeline / "references/platform-adapter.md").read_text()
artifacts = (pipeline / "references/artifacts.md").read_text()
extension = (pipeline / "extensions/plan-interview-channel-timeout.js").read_text()
agent = Path.home().joinpath(".pi/agent/agents/plan.md").read_text()
machine_driver = (pipeline / "evals/planner-executor-pipeline.machine-driver.md").read_text()
subagents = Path.home() / ".pi/agent/npm/node_modules/pi-subagents"
schemas = (subagents / "src/extension/schemas.js").read_text()
agent_loader = (subagents / "src/agents/agents.js").read_text()
channel = (subagents / "src/intercom/native-supervisor-channel.js").read_text()
channel_docs = (subagents / "docs/agents.md").read_text()
runner = (subagents / "src/runs/background/subagent-runner.js").read_text()
child_session = (subagents / "src/runs/shared/child-session.js").read_text()

assert "Explanation requests, partial answers, discussion, and other non-final replies" in agent
assert "Do not default or invent an answer" in agent
assert "same PLAN run" in agent
assert "An explanation request, partial answer, discussion, or brief absence is not final" in skill
assert "only the user's ruling settles that decision" in skill
assert '"interview_round": 0' not in skill
assert "Interview request" in adapter and "`message`" in adapter
assert "list only unresolved questions in `interview`" in adapter
assert "direct single-agent launch" in adapter
assert "composite workflow" in adapter
assert "PlanHandoff" in artifacts and "hard kill" in artifacts.lower()
assert 'subagentOnlyExtensions:' in agent
assert "extensions:" not in agent
assert 'timeoutMs: 86400000' in adapter
assert "context: \"fresh\"" in adapter
assert "timeoutMs: 86400000" in agent
assert "async: true" in agent
assert "24-hour total-lifetime deadline measured from launch" in agent
assert "direct async single-agent" in machine_driver
assert "timeoutMs: 86400000" in machine_driver
assert "inheritSkills: false" in agent
assert "child runner" in extension
assert "Loaded only by the direct async PLAN agent" in extension
assert "process.env.PI_INTERCOM_ASK_TIMEOUT_MS = String(PLAN_INTERVIEW_CHANNEL_TIMEOUT_MS)" in extension
assert "86_400_000" in extension
assert 'process.env[SUBAGENT_CHILD_ENV] = "1"' in runner
assert "applyProcessEnv(launch.processEnv)" in child_session
assert "timeoutMs: Type.Optional(Type.Integer({ minimum: 1," in schemas
assert "explicit `timeoutMs`/`maxRuntimeMs` and agent defaults win" in channel_docs
assert re.search(r"if \(frontmatter\.timeoutMs !== undefined\)[\s\S]{0,260}Number\.isInteger\(parsed\) \|\| parsed <= 0", agent_loader)
assert "const DEFAULT_ASK_TIMEOUT_MS = 10 * 60 * 1000" in channel
assert "process.env.PI_INTERCOM_ASK_TIMEOUT_MS" in channel
assert "const expiresAt = expectsReply ? replyDeadline : undefined" in channel
print("PASS: PLAN direct async dispatch, 24h run/channel deadlines, dedicated child extension, same-run interview contract, and expiry eval are aligned.")
