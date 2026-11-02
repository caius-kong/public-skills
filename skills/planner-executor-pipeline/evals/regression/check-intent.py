#!/usr/bin/env python3
"""Run every intent fixture: the real ones must pass, each canary must fail.

A canary that starts passing means the check it targets has stopped working --
which is the whole reason these files exist. A fixture may name its own plan with
"_plan" when it belongs to a different contract than the default one.
"""
import json, subprocess, sys, tempfile, pathlib

HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_PLAN = HERE / "t2/intent-plan.json"
CHECK = HERE.parents[1] / "scripts/intent-check.py"
PASSING = {"intent-real.json", "intent-canary-path-stem.json", "intent-canary-nocolon.json"}
bad = []
for f in sorted((HERE / "t2").glob("intent-*.json")):
    if f.name.startswith("intent-plan"):
        continue
    try:
        intent = json.loads(f.read_text())
    except Exception as e:
        bad.append(f"{f.name}: 读不了: {e}")
        continue
    plan = DEFAULT_PLAN
    if "_plan" in intent:                      # a fixture that needs its own contract
        plan = HERE / "t2" / intent.pop("_plan")
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tmp:
            json.dump(intent, tmp, ensure_ascii=False)
            intent_path = tmp.name
    else:
        intent_path = str(f)
    out = subprocess.run([sys.executable, str(CHECK), str(plan), "--intent-file", intent_path,
                          "--require-accepted"], capture_output=True, text=True)
    want = 0 if f.name in PASSING else 1
    ok = out.returncode == want
    if not ok:
        bad.append(f"{f.name}: exit {out.returncode} != {want} :: {(out.stdout or out.stderr).strip()[:160]}")
    print(f"{'PASS' if ok else 'FAIL'}  {f.name:<32} exit={out.returncode} (want {want}) plan={pathlib.Path(plan).name}")
print(f"\n{len(bad)} fixture(s) misbehaved")
for b in bad:
    print("  -", b)
sys.exit(1 if bad else 0)
