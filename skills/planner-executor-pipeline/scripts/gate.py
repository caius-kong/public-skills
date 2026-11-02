#!/usr/bin/env python3
"""The seven GATE checks, as the single implementation of what references/artifacts.md describes.

Usage: gate.py <repo> [--review-acs AC7,AC8]

Everything is read from <repo>/handoffs/ (plan-handoff.json, test-handoff.json,
execute-handoff.json, state.json). Exit 0 = PASS, 1 = FIX_EXECUTE (a check
failed), 2 = cannot judge (malformed input). A crash must never read as PASS.

Each check exists because a delivery failed that way. Three of them once failed
for the WRONG reason -- comparing a noisy surface instead of a semantic quantity
-- which is why evals/regression/check-gate.py exercises this script against
fixture trees rather than trusting it.
"""
import ast, json, re, subprocess, sys, pathlib

REPO = pathlib.Path(sys.argv[1]).resolve()  # the repository under delivery
HANDOFFS = REPO / "handoffs"
for required in ("plan-handoff.json", "test-handoff.json", "execute-handoff.json", "state.json"):
    if not (HANDOFFS / required).exists():
        print(f"UNKNOWN: missing handoffs/{required}")
        sys.exit(2)
EVIDENCE = HANDOFFS / "gate-evidence.json"
if EVIDENCE.exists():
    EVIDENCE.unlink()          # a crashed run must not leave an old verdict looking current
REVIEW_ACS = set()
for i, a in enumerate(sys.argv):
    if a == "--review-acs":
        REVIEW_ACS = {x.strip() for x in sys.argv[i + 1].split(",") if x.strip()}

def git(*a):
    return subprocess.run(["git", *a], cwd=REPO, capture_output=True, text=True).stdout.strip()

plan = json.loads((REPO / "handoffs/plan-handoff.json").read_text())
test_h = json.loads((REPO / "handoffs/test-handoff.json").read_text())
exec_h = json.loads((REPO / "handoffs/execute-handoff.json").read_text())
state = json.loads((REPO / "handoffs/state.json").read_text())
BASE = git("rev-parse", state["base"])
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
record("1 test_command", all(r.returncode == 0 for r in runs) and counts_run[0] == counts_run[1],
       f"exit={[r.returncode for r in runs]}, counts={counts_run}, last: {last[-1][:60]}")

# 2 diff within allowed_paths
diff = [l for l in git("diff", "--name-only", f"{BASE}..{HEAD}").splitlines() if l]
allowed = set(plan["allowed_paths"]) | set(state.get("verified_protected") or [])
orchestrator = {c for o in state.get("orchestrator_commits", []) for c in o.get("files", [])}
outside = [f for f in diff if f not in allowed and f not in orchestrator]
record("2 diff within allowed_paths", not outside,
       f"diff={diff}; outside={outside or 'none'}; orchestrator={sorted(orchestrator) or 'none'}")

# 3 test freeze: no test change after the TA commit
ta = exec_h.get("base_commit") or test_h["commit"]
frozen = test_h.get("test_files") or []
changed_after = [l for l in git("diff", "--name-only", f"{ta}..{HEAD}", "--", *frozen).splitlines() if l] if frozen else []
record("3 test freeze", not changed_after, f"diff {ta[:7]}..{HEAD[:7]} over {frozen} = {changed_after or 'empty'}")

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
record("4 freeze strength", counts["head"] and counts["base"] and counts["head"] > counts["base"] and not skips and not flags,
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
test_files = sorted(set(frozen) | {f for f in diff if re.search(r"(^tests/|test_[^/]*\.py$)", f)})
mock_hits = [f"{f}:{m}" for f in test_files for m in ("unittest.mock", "mock.patch", "MagicMock", "mocker.")
             if m in (REPO / f).read_text()]
ac_ids = [re.match(r"^\s*([A-Za-z]+\d+)", a).group(1) for a in plan["tickets"][0]["acceptance"]]
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
for f in test_files:
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
record("7 seam match", not violations, f"imports={imports}; declared seams={sorted(seam_modules)}; violations={violations or 'none'}")

failed = [r["check"] for r in results if not r["ok"]]
verdict = "PASS" if not failed else "FIX_EXECUTE"
EVIDENCE.write_text(json.dumps({"base": BASE, "head": HEAD, "verdict": verdict, "violations": failed,
                                "checks": results, "diff_files": diff, "test_files": test_files,
                                "review_acs": sorted(REVIEW_ACS)}, ensure_ascii=False, indent=2))
subprocess.run(f"rm -rf {REPO / '.gate-tmp'}", shell=True)
print(f"\nGATE verdict: {verdict}" + (f" (failed: {failed})" if failed else ""))
sys.exit(0 if verdict == "PASS" else 1)
