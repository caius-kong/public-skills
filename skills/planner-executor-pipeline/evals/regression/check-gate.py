#!/usr/bin/env python3
"""Exercise scripts/gate.py against fixture repositories.

Each fixture is a tiny git repo plus handoffs/. One must PASS, and each bad one
must fail on exactly the check it targets: a gate that passes everything and a
gate that fails everything are equally useless, and this gate has already failed
for the wrong reason three times.

Run: python3 evals/regression/check-gate.py
"""
import json, shutil, subprocess, sys, tempfile, pathlib

SKILL = pathlib.Path(__file__).resolve().parents[2]
GATE = SKILL / "scripts/gate.py"
TEST_CMD = "PYTHONPATH=src python3 -m pytest -q tests"   # carries "-m", which check 4 once misread
TEST_SRC = 'from m import f\n\n\ndef test_ac1_basic():\n    assert f() == 1\n'
IMPL = "def f():\n    return 1\n"


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True).stdout.strip()


def commit(repo, message):
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "-c", "user.email=e@x", "-c", "user.name=e", "commit", "-qm", message],
                   cwd=repo, check=True, capture_output=True)
    return git(repo, "rev-parse", "HEAD")


def build(root, name="good", *, acceptance=("AC1: f() returns 1.",), allowed=None,
          test_files=("tests/test_m.py",)):
    """A repo whose BASE is green, whose TEST_AUTHOR commit adds a red test, and
    whose EXECUTE commit makes it green. BASE greening matters: check 4 compares
    collected counts, so a red baseline would make its own arithmetic meaningless."""
    repo = root / name
    (repo / "src").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "src/m.py").write_text("def f():\n    return 0\n")
    # Independent of the value f() returns, so a green baseline stays green after
    # EXECUTE changes it -- otherwise the fixture itself fails check 1.
    (repo / "tests/test_base.py").write_text("from m import f\n\n\ndef test_base():\n    assert callable(f)\n")
    (repo / ".gitignore").write_text("handoffs/\n.gate-tmp/\n__pycache__/\n")   # before BASE: not part of the delivery
    git(repo, "init", "-q")
    base = commit(repo, "base")
    (repo / "tests/test_m.py").write_text(TEST_SRC)          # red: f() returns 0
    ta = commit(repo, "T1: freeze tests")
    (repo / "src/m.py").write_text(IMPL)                     # green
    execute = commit(repo, "T1: implement")
    plan = {
        "spec": {"title": "fixture"},
        "seams": [{"id": "S1", "modules": ["m"]}],
        "tickets": [{"id": "T1", "acceptance": list(acceptance), "depends_on": [], "seam": "S1"}],
        "allowed_paths": allowed if allowed is not None else ["src/m.py", "tests/test_m.py"],
        "protected_paths": [],
        "test_command": TEST_CMD,
    }
    h = repo / "handoffs"
    h.mkdir()
    (h / "plan-handoff.json").write_text(json.dumps(plan))
    (h / "test-handoff.json").write_text(json.dumps({"commit": ta, "test_files": list(test_files)}))
    (h / "execute-handoff.json").write_text(json.dumps({"commit": execute, "base_commit": ta}))
    (h / "pipeline-state.json").write_text(json.dumps({"base_sha": base, "orchestrator_commits": []}))
    return repo, h, base, execute


def add_archive(repo, h):
    """An archive commit lands on top of the execute commit; check 5 must allow it."""
    (repo / "docs/specs").mkdir(parents=True)
    (repo / "docs/specs/x.md").write_text("# record\n")
    sha = commit(repo, "docs(spec): record")
    state = json.loads((h / "pipeline-state.json").read_text())
    state["orchestrator_commits"] = [{"commit": sha, "files": ["docs/specs/x.md"], "reason": "archive"}]
    (h / "pipeline-state.json").write_text(json.dumps(state))
    return sha


def run(repo, review=""):
    cmd = [sys.executable, str(GATE), str(repo)] + (["--review-acs", review] if review else [])
    out = subprocess.run(cmd, capture_output=True, text=True)
    return out.returncode, out.stdout


CASES = []


def case(name, expect_rc, expect_failed=None, review=""):
    def register(fn):
        CASES.append((name, fn, expect_rc, expect_failed, review))
        return fn
    return register


@case("good", 0)
def _good(root):
    repo, h, _, _ = build(root)
    add_archive(repo, h)
    return repo


@case("bad-diff", 1, "2 diff within allowed_paths")
def _bad_diff(root):
    repo, h, _, _ = build(root, "bad-diff")
    (repo / "src/extra.py").write_text("x = 1\n")
    commit(repo, "sneak in a file outside allowed_paths")
    return repo


@case("bad-freeze", 1, "3 test freeze")
def _bad_freeze(root):
    repo, h, _, _ = build(root, "bad-freeze")
    (repo / "tests/test_m.py").write_text(TEST_SRC + "\ndef test_ac1_extra():\n    assert True\n")
    commit(repo, "edit the frozen test")
    return repo


@case("bad-antigaming", 3, "6 anti-gaming")
def _bad_antigaming(root):
    repo, h, _, _ = build(root, "bad-antigaming")
    plan = json.loads((h / "plan-handoff.json").read_text())
    plan["tickets"][0]["acceptance"] = ["AC1: f() returns 1.", "AC9: nothing tests this."]
    (h / "plan-handoff.json").write_text(json.dumps(plan))
    return repo


@case("bad-testcmd", 1, "1 test_command")
def _bad_testcmd(root):
    repo, h, _, _ = build(root, "bad-testcmd")
    (repo / "src/m.py").write_text("def f():\n    raise SystemExit(3)\n")   # the suite now fails
    commit(repo, "break the suite")
    return repo


@case("bad-chain", 3, "5 handoff SHA")
def _bad_chain(root):
    repo, h, _, _ = build(root, "bad-chain")
    state = json.loads((h / "pipeline-state.json").read_text())
    state["base_sha"] = git(repo, "rev-parse", "HEAD")   # BASE == HEAD: no ancestry to speak of
    (h / "pipeline-state.json").write_text(json.dumps(state))
    return repo


@case("cannot-judge-no-base", 2, "CANNOT JUDGE")
def _no_base(root):
    repo, h, _, _ = build(root, "no-base")
    state = json.loads((h / "pipeline-state.json").read_text())
    for key in ("base_sha", "base"):
        state.pop(key, None)
    (h / "pipeline-state.json").write_text(json.dumps(state))
    return repo


@case("cannot-judge-broken-json", 2, "CANNOT JUDGE")
def _broken_json(root):
    repo, h, _, _ = build(root, "broken-json")
    (h / "plan-handoff.json").write_text("{ broken")
    return repo


@case("replan-second-ticket-ac", 3, "6 anti-gaming")
def _second_ticket(root):
    """Check 6 must look at every ticket, not just the first."""
    repo, h, _, _ = build(root, "second-ticket")
    plan = json.loads((h / "plan-handoff.json").read_text())
    plan["tickets"].append({"id": "T2", "title": "second", "acceptance": ["AC9: nothing tests this"],
                            "depends_on": [], "files": [], "seam": "s1"})
    (h / "plan-handoff.json").write_text(json.dumps(plan))
    return repo


@case("cannot-judge-env-flake", 2, "env_flake")
def _env_flake(root):
    """A suite that fails during import is an environment flake, not a delivery
    defect: it must not route back to EXECUTE."""
    repo, h, _, _ = build(root, "env-flake")
    (repo / "tests/test_flake.py").write_text("import not_a_real_package_xyz\n")
    return repo


@case("replan-file-predates-stage", 3, "2 diff within allowed_paths")
def _predates(root):
    """An out-of-bounds file that existed before TEST_AUTHOR cannot be undone by
    EXECUTE, so it routes to REPLAN rather than FIX_EXECUTE."""
    repo, h, _, _ = build(root, "predates")
    # Rewrite the sequence: add the stray file before the TA commit, then touch it
    # after, so it shows up in BASE..HEAD without having been created by EXECUTE.
    git(repo, "reset", "-q", "--hard", "HEAD~2")
    (repo / "src/stray.py").write_text("earlier round\n")
    commit(repo, "earlier round adds a stray file")
    (repo / "tests/test_m.py").write_text(TEST_SRC)
    ta = commit(repo, "T1: freeze tests")
    (repo / "src/m.py").write_text(IMPL)
    (repo / "src/stray.py").write_text("earlier round, touched now\n")
    execute = commit(repo, "T1: implement")
    plan = json.loads((h / "plan-handoff.json").read_text())
    plan["allowed_paths"] = ["src/m.py", "tests/test_m.py"]
    (h / "plan-handoff.json").write_text(json.dumps(plan))
    (h / "test-handoff.json").write_text(json.dumps({"commit": ta, "test_files": ["tests/test_m.py"]}))
    (h / "execute-handoff.json").write_text(json.dumps({"commit": execute}))
    state = json.loads((h / "pipeline-state.json").read_text())
    state["base_sha"] = git(repo, "rev-parse", "HEAD~3")
    (h / "pipeline-state.json").write_text(json.dumps(state))
    return repo


@case("bad-seam", 3, "7 seam match")
def _bad_seam(root):
    repo, h, _, _ = build(root, "bad-seam")
    (repo / "tests/test_m.py").write_text(
        "import json\n\n" + TEST_SRC)  # json is stdlib and allowed; use an undeclared local module
    (repo / "tests/test_m.py").write_text("import helpers\n\n" + TEST_SRC)
    (repo / "tests/helpers.py").write_text("X = 1\n")
    commit(repo, "reach into a module the contract never declared as a seam")
    return repo


VERDICT_CASES = []


def verdict_case(name, expect_rc, mutate):
    def register(fn):
        VERDICT_CASES.append((name, fn, expect_rc, mutate))
        return fn
    return register


def _verdict(repo, acceptance=("AC1: f() returns 1.",), evidence="src/m.py:1", items=None):
    return {"verdict": "PASS", "reasons": ["fixture"],
            "answer_key": items if items is not None else
            [{"acceptance": acceptance[0], "evidence": evidence, "reasoning": "fixture"}]}


def run_verdict(repo, verdict):
    tmp = repo / "verdict.json"
    tmp.write_text(json.dumps(verdict))
    diff = subprocess.run(["git", "diff", "HEAD~1..HEAD"], cwd=repo, capture_output=True, text=True).stdout
    (repo / "impl.diff").write_text(diff)
    out = subprocess.run([sys.executable, str(SKILL / "scripts/check-verdict.py"),
                          "--verdict", str(tmp), "--repo", str(repo), "--diff", str(repo / "impl.diff"),
                          "--acceptances", json.dumps(["AC1: f() returns 1."])],
                         capture_output=True, text=True)
    return out.returncode, out.stdout


@verdict_case("verdict-unchanged-line", 0, None)
def _v_ok(root):
    """Citing a line the diff did NOT change is legitimate: proving 'unchanged' needs it.

    The citation is deliberately outside every hunk, so a regression to the old
    line-level rule fails here instead of passing quietly.
    """
    repo, h, _, _ = build(root, "verdict-ok")
    # The cited line must be outside every hunk of the file the diff touches, or a
    # regression to the old line-level rule would pass this fixture too.
    (repo / "src/m.py").write_text("def f():\n    return 1\n" + "\n" * 10)
    commit(repo, "pad the file so the citation sits outside the hunk")
    return repo, _verdict(repo, evidence="src/m.py:10")


@verdict_case("verdict-untouched-file", 1, None)
def _v_untouched(root):
    repo, h, _, _ = build(root, "verdict-untouched")
    return repo, _verdict(repo, evidence="tests/test_base.py:1")   # never in the diff


@verdict_case("verdict-missing-answer", 1, None)
def _v_missing(root):
    repo, h, _, _ = build(root, "verdict-missing")
    return repo, _verdict(repo, items=[])                          # no answer for AC1


def main():
    root = pathlib.Path(tempfile.mkdtemp(prefix="gate-fixtures-"))
    bad = []
    try:
        for name, build_fn, expect_rc, expect_failed, review in CASES:
            repo = build_fn(root)
            rc, out = run(repo, review)
            failing = [l.split(":")[0].replace("FAIL  ", "") for l in out.splitlines() if l.startswith("FAIL")]
            ok = rc == expect_rc and (expect_failed is None or expect_failed in failing or expect_failed in out)
            print(f"{'PASS' if ok else 'FAIL'}  {name:<16} exit={rc} want={expect_rc} failing={failing or 'none'}")
            if not ok:
                bad.append(f"{name}: exit={rc} want={expect_rc} failing={failing} :: {out.strip()[:200]}")
        for name, build_fn, expect_rc, _m in VERDICT_CASES:
            repo, verdict = build_fn(root)
            rc, out = run_verdict(repo, verdict)
            ok = rc == expect_rc
            print(f"{'PASS' if ok else 'FAIL'}  {name:<24} exit={rc} want={expect_rc}")
            if not ok:
                bad.append(f"{name}: exit={rc} want={expect_rc} :: {(out or '').strip()[:200]}")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    print(f"\n{len(bad)} fixture(s) misbehaved")
    for b in bad:
        print("  -", b)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
