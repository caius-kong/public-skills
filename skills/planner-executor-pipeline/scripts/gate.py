#!/usr/bin/env python3
"""The seven GATE checks, as the single implementation of what references/artifacts.md describes.

Usage: gate.py <repo> [--review-acs AC7,AC8]

Everything is read from <repo>/handoffs/ (plan-handoff.json, test-handoff.json,
execute-handoff.json, pipeline-state.json). Exit 0 = PASS, 1 = FIX_EXECUTE (a check
failed), 2 = cannot judge (malformed input, environment flake), 3 = REPLAN (test or
contract defect: #4-#7, which EXECUTE may not fix). A crash must never read as PASS.

Each check exists because a delivery failed that way. Three of them once failed
for the WRONG reason -- comparing a noisy surface instead of a semantic quantity
-- which is why evals/regression/check-gate.py exercises this script against
fixture trees rather than trusting it.
"""
import ast, json, re, subprocess, sys, pathlib


# A crash is not a verdict: exit 1 means FIX_EXECUTE, so an uncaught exception
# must not be read as a substantive judgement. Installed before the first line
# that can raise, including argv handling.
def _cannot_judge(exc_type, exc, tb):
    print(f"CANNOT JUDGE: {exc_type.__name__}: {exc}")
    raise SystemExit(2)


sys.excepthook = _cannot_judge

if len(sys.argv) < 2:
    print("CANNOT JUDGE: usage: gate.py <repo> [--review-acs ACn,...]")
    raise SystemExit(2)

REPO = pathlib.Path(sys.argv[1]).resolve()  # the repository under delivery
HANDOFFS = REPO / "handoffs"
EVIDENCE = HANDOFFS / "gate-evidence.json"
if EVIDENCE.exists():
    EVIDENCE.unlink()          # a crashed run must not leave an old verdict looking current
STATE_NAMES = ("pipeline-state.json", "state.json")   # contract name first, legacy second
STATE_FILE = next((REPO / "handoffs" / n for n in STATE_NAMES if (REPO / "handoffs" / n).exists()), None)
for required in ("plan-handoff.json", "test-handoff.json", "execute-handoff.json"):
    if not (HANDOFFS / required).exists():
        print(f"CANNOT JUDGE: missing handoffs/{required}")
        sys.exit(2)
REVIEW_ACS = set()
for i, a in enumerate(sys.argv):
    if a == "--review-acs":
        REVIEW_ACS = {x.strip() for x in sys.argv[i + 1].split(",") if x.strip()}

def git(*a):
    return subprocess.run(["git", *a], cwd=REPO, capture_output=True, text=True).stdout.strip()

# A crash is not a verdict: exit 1 means FIX_EXECUTE, so an uncaught exception
# must not be read as a substantive judgement about the delivery.


plan = json.loads((REPO / "handoffs/plan-handoff.json").read_text())
test_h = json.loads((REPO / "handoffs/test-handoff.json").read_text())
exec_h = json.loads((REPO / "handoffs/execute-handoff.json").read_text())
if STATE_FILE is None:
    print("CANNOT JUDGE: no handoffs/pipeline-state.json (or legacy state.json)")
    raise SystemExit(2)
state = json.loads(STATE_FILE.read_text())
# The contract calls this field base_sha; an older name is still accepted so a
# state file written before the rename does not crash the gate.
BASE_SHA = state.get("base_sha") or state.get("base")
if not BASE_SHA:
    print(f"CANNOT JUDGE: {STATE_FILE.name} has no base_sha")
    raise SystemExit(2)
BASE = git("rev-parse", BASE_SHA)
if not BASE:
    print(f"CANNOT JUDGE: base_sha {BASE_SHA!r} does not resolve to a commit")
    raise SystemExit(2)
HEAD = git("rev-parse", "HEAD")
results = []
def record(name, ok, detail):
    results.append({"check": name, "ok": bool(ok), "detail": detail})
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}")

# 1 test command
cmd = plan.get("test_command") or state.get("test_command")
runs = [subprocess.run(cmd, shell=True, cwd=REPO, capture_output=True, text=True) for _ in range(2)]
def tally(r):
    m = re.search(r"(\d+) passed", r.stdout)
    f_ = re.search(r"(\d+) (?:failed|error)", r.stdout)
    return (int(m.group(1)) if m else 0, int(f_.group(1)) if f_ else 0)
counts_run = [tally(r) for r in runs]
last = [r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "" for r in runs]
# Compare pass/fail counts, not the whole line: the line carries a duration, so
# comparing it reported "unstable" on every pair of identical passing runs.
# Environment red is not a delivery defect: the contract says a flaky or
# collection-phase failure is re-run in a clean environment, not sent back to
# EXECUTE. It is also not a pass -- the suite has not been observed green -- so it
# exits as CANNOT JUDGE and the parent re-runs.
COLLECTION_MARKERS = ("ModuleNotFoundError", "ImportError", "ERROR ... in collection", "error during collection")
flaked = (any(r.returncode != 0 for r in runs)
          and (counts_run[0] != counts_run[1]
               or any(m in "".join(r.stdout + r.stderr for r in runs) for m in COLLECTION_MARKERS)))
if flaked:
    print("CANNOT JUDGE: env_flake -- the suite did not behave the same way twice, or failed during "
          "collection/import; re-run in a clean environment")
    raise SystemExit(2)

record("1 test_command", all(r.returncode == 0 for r in runs) and counts_run[0] == counts_run[1],
       f"exit={[r.returncode for r in runs]}, counts={counts_run}, last: {last[-1][:60]}")

# 2 diff within allowed_paths
diff = [l for l in git("diff", "--name-only", f"{BASE}..{HEAD}").splitlines() if l]
allowed = set(plan["allowed_paths"])
orchestrator = {c for o in state.get("orchestrator_commits", []) for c in o.get("files", [])}
outside = [f for f in diff if f not in allowed and f not in orchestrator]
# Which round introduced an out-of-bounds file decides where it goes back: a stage
# can undo its own write, but not one that predates it.
ta = test_h["commit"]
def predates_stage(file):
    return not git("log", "--diff-filter=A", "--format=%H", f"{ta}..{HEAD}", "--", file).split()

older = [f for f in outside if predates_stage(f)]
record("2 diff within allowed_paths", not outside,
       f"diff={diff}; outside={outside or 'none'}"
       + (f"; predates this stage (-> REPLAN)={older}" if older else "")
       + f"; orchestrator={sorted(orchestrator) or 'none'}")

# 3 test freeze: no test change after the TA commit
frozen = test_h.get("test_files") or []
changed_after = [l for l in git("diff", "--name-only", f"{ta}..{HEAD}", "--", *frozen).splitlines() if l] if frozen else []
authorized = {e.get("file") for e in (state.get("authorized_test_edits") or [])}
unauthorized = [f for f in changed_after if f not in authorized]
record("3 test freeze", not unauthorized,
       f"diff {ta[:7]}..{HEAD[:7]} over {frozen} = {changed_after or 'empty'}"
       + (f"; authorized={sorted(set(changed_after) & authorized)}" if authorized else ""))

# 4 freeze strength
counts = {}
for label, sha in (("base", BASE), ("head", HEAD)):
    tree = REPO / ".gate-tmp" / label
    subprocess.run(f"rm -rf {tree} && mkdir -p {tree} && git archive {sha} | tar -x -C {tree}",
                   shell=True, cwd=REPO, capture_output=True)
    out = subprocess.run(cmd, shell=True, cwd=tree, capture_output=True, text=True).stdout
    m = re.search(r"(\d+) passed", out)
    counts[label] = int(m.group(1)) if m else None
blob = "\n".join((REPO / f).read_text() for f in frozen if (REPO / f).exists())
skips = [w for w in ("skip", "xfail", "pytest.mark.skip") if w in blob]
# Only look for pytest's own flags: "python3 -m pytest" is the interpreter's -m,
# and matching it made this check fail on every run of a perfectly normal command.
pytest_argv = cmd[cmd.index("pytest"):] if "pytest" in cmd else ""
flags = re.findall(r"(?:\s-k\s|\s-m\s+\w+|--deselect)", pytest_argv)
if counts["head"] is None or counts["base"] is None:
    print("CANNOT JUDGE: freeze strength -- the test count could not be collected on one side "
          f"(BASE={counts['base']} HEAD={counts['head']})")
    raise SystemExit(2)
record("4 freeze strength", counts["head"] >= counts["base"] and not skips and not flags,
       f"collected BASE={counts['base']} HEAD={counts['head']}; skip markers={skips or 'none'}; selection flags={flags or 'none'}")

# 5 handoff sha chain: BASE -> TA -> EXECUTE -> HEAD by ancestry, not equality.
# After archiving, HEAD is the archive commit, so equality with the execute
# commit reported a failure on a delivery that had gone exactly to plan.
def is_ancestor(a, b):
    return subprocess.run(["git", "merge-base", "--is-ancestor", a, b], cwd=REPO).returncode == 0
chain_ok = is_ancestor(BASE, ta) and is_ancestor(ta, exec_h["commit"]) and is_ancestor(exec_h["commit"], HEAD)
record("5 handoff SHA", chain_ok,
       f"BASE={BASE[:7]} TA={ta[:7]} EXECUTE={exec_h['commit'][:7]} HEAD={HEAD[:7]} (ancestry holds={chain_ok})")

# 6 anti-gaming: black box only, and every acceptance is hit by a test named after it
test_files = sorted(set(frozen) | {f for f in diff
                                  if re.search(r"(^tests/|test_[^/]*\.py$|\.test\.[a-z]+$|\.spec\.[a-z]+$)", f)})
mock_hits = [f"{f}:{m}" for f in test_files for m in ("unittest.mock", "mock.patch", "MagicMock", "mocker.")
             if m in (REPO / f).read_text()]
ac_ids = [re.match(r"^\s*([A-Za-z]+\d+)", a).group(1)
          for ticket in plan["tickets"] for a in ticket["acceptance"]]
by_ac = {}
for f in test_files:
    for n in re.findall(r"^def (test_\w+)", (REPO / f).read_text(), re.M):
        for ac in ac_ids:
            if re.search(rf"_{ac.lower()}_|_{ac.lower()}$", n.lower()):
                by_ac.setdefault(ac, []).append(n)
no_test = [ac for ac in ac_ids if ac not in by_ac and ac not in REVIEW_ACS]
record("6 anti-gaming", not mock_hits and not no_test,
       f"mock usages={mock_hits or 'none'}; AC without a test named after it={no_test or 'none'}; "
       f"AC->tests={ {k: len(v) for k, v in by_ac.items()} }; review-declared={sorted(REVIEW_ACS) or 'none'}")

# 7 seam match
seam_modules = {m for s in plan["seams"] for m in s["modules"]}
stdlib = set(sys.stdlib_module_names)
framework = {"pytest", "_pytest"}
violations = []
imports = {}
unparsed = []
for f in test_files:
    # Only Python test files can be import-parsed; a .spec.ts would crash the gate,
    # and a crash is not a verdict. Record it as not covered instead.
    if not f.endswith(".py"):
        unparsed.append(f)
        continue
    tree = ast.parse((REPO / f).read_text())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    imports[f] = sorted(names)
    for name in names:
        top = name.split(".")[0]
        if top in stdlib or top in framework or name in seam_modules:
            continue
        violations.append(f"{f}: {name}")
record("7 seam match", not violations,
       f"imports={imports}; declared seams={sorted(seam_modules)}; violations={violations or 'none'}"
       + (f"; not import-parsed={unparsed}" if unparsed else ""))

# Which stage a failure routes to is contract, not judgement: #1/#2/#3 go back to
# EXECUTE, #4/#5/#6/#7 are test or contract defects that EXECUTE may not touch.
REPLAN_CHECKS = ("4 ", "5 ", "6 ", "7 ")
failed = [r["check"] for r in results if not r["ok"]]
if not failed:
    verdict = "PASS"
elif any(c.startswith(REPLAN_CHECKS) for c in failed) or older:
    verdict = "REPLAN"
else:
    verdict = "FIX_EXECUTE"
EVIDENCE.write_text(json.dumps({"base": BASE, "head": HEAD, "verdict": verdict, "violations": failed,
                                "checks": results, "diff_files": diff, "test_files": test_files,
                                "review_acs": sorted(REVIEW_ACS)}, ensure_ascii=False, indent=2))
subprocess.run(f"rm -rf {REPO / '.gate-tmp'}", shell=True)
print(f"\nGATE verdict: {verdict}" + (f" (failed: {failed})" if failed else ""))
sys.exit({"PASS": 0, "FIX_EXECUTE": 1, "CANNOT JUDGE": 2, "REPLAN": 3}[verdict])
