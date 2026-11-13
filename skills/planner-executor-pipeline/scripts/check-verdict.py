#!/usr/bin/env python3
"""Validate a CONFORMANCE Verdict's answer key against the delivered diff.

An auditor that did not look can still write "no hardcoded values found" and
be rewarded with PASS. The answer key forces one citation per acceptance, and
this script checks the citations mechanically: the file must exist, the line
must exist, and the file must be one the diff touched -- an unchanged line
is legitimate evidence, since proving "existing behaviour is unchanged"
can only cite a line nobody edited. It cannot tell
whether the reasoning is honest -- only that the auditor opened the file it
claims to have judged.

Usage:
  check-verdict.py --verdict handoffs/verdict.json --repo . --diff handoffs/impl.diff \
                   --acceptances "<json array of acceptance strings>"

Exit codes: 0 = valid, 1 = invalid (missing/foreign citations), 2 = cannot judge
(no verdict, no diff, or no acceptances supplied).
"""
import argparse
import json
import re
import sys
from pathlib import Path

HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def touched_lines(diff_text):
    """{path: set(line numbers)} for added/context lines on the new side."""
    touched, path, cur = {}, None, None
    for raw in diff_text.splitlines():
        if raw.startswith("+++ "):
            path = raw[4:].strip()
            path = path[2:] if path.startswith("b/") else path
            touched.setdefault(path, set())
            continue
        m = HUNK.match(raw)
        if m and path:
            cur = int(m.group(1))
            continue
        if cur is None or path is None:
            continue
        if raw.startswith("-"):
            continue
        if raw.startswith("+") or raw.startswith(" "):
            touched[path].add(cur)
            cur += 1
    return touched


def acceptance_id(text):
    """The short id an acceptance string may be cited by, e.g. "AC7：..." -> "AC7"."""
    m = re.match(r"^\s*([A-Za-z]+[-_ ]?\d+)\s*[：:]", text or "")
    return m.group(1).strip() if m else None


def parse_location(evidence):
    m = re.match(r"^(.+?):(\d+)(?:-\d+)?$", (evidence or "").strip())
    if not m:
        return None
    return m.group(1).strip(), int(m.group(2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verdict", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--diff", required=True)
    ap.add_argument("--acceptances", required=True, help="JSON array of acceptance strings")
    args = ap.parse_args()

    for p in (args.verdict, args.diff):
        if not Path(p).exists():
            print(f"CANNOT JUDGE: missing {p}")
            return 2
    try:
        acceptances = json.loads(args.acceptances)
    except json.JSONDecodeError:
        print("CANNOT JUDGE: --acceptances is not JSON")
        return 2
    if not isinstance(acceptances, list) or not acceptances:
        print("CANNOT JUDGE: no acceptance criteria supplied")
        return 2

    verdict = json.loads(Path(args.verdict).read_text())
    allowed = {"PASS", "FIX_EXECUTE", "REPLAN"}
    actual = verdict.get("verdict")
    if actual not in allowed:
        # An auditor inventing its own verdict word has broken the routing
        # contract: whatever it meant, the pipeline cannot route it.
        print(f"FAIL: verdict must be one of {sorted(allowed)}, got {actual!r}")
        return 1
    key = verdict.get("answer_key")
    if not isinstance(key, list) or not key:
        print("FAIL: verdict has no answer_key; 'no findings' is not an audit")
        return 1

    touched = touched_lines(Path(args.diff).read_text())
    repo = Path(args.repo)
    problems = []

    covered = {item.get("acceptance", "").strip() for item in key if isinstance(item, dict)}
    # An auditor may cite the full acceptance text or the id it starts with
    # ("AC7"). Requiring the exact text made every honest audit fail, which is
    # the same defect as letting a dishonest one pass.
    ids = {}
    for acc in acceptances:
        aid = acceptance_id(acc)
        if aid:
            ids.setdefault(aid, []).append(acc)
    for acc in acceptances:
        if acc.strip() in covered:
            continue
        aid = acceptance_id(acc)
        if aid and len(ids.get(aid, [])) == 1 and aid in covered:
            continue
        problems.append(f"no answer for acceptance: {acc[:60]}")

    for item in key:
        if not isinstance(item, dict):
            problems.append(f"malformed answer_key entry: {item!r}")
            continue
        loc = parse_location(item.get("evidence"))
        if not loc:
            problems.append(f"evidence is not path:line -> {item.get('evidence')!r}")
            continue
        path, line = loc
        if not (repo / path).exists():
            problems.append(f"evidence cites a file that does not exist: {path}")
            continue
        lines = (repo / path).read_text().splitlines()
        if line > len(lines):
            problems.append(f"evidence line {line} beyond end of {path} ({len(lines)} lines)")
            continue
        # diff paths are repo-relative; tolerate a leading ./
        norm = path[2:] if path.startswith("./") else path
        if norm not in touched:
            problems.append(f"evidence cites a file the diff never touched: {path}")
        # No hunk requirement. "the existing behaviour is unchanged" is a real
        # acceptance, and proving it means citing the lines that were NOT
        # modified; demanding every citation sit inside a hunk rejected exactly
        # that evidence.
        if not str(item.get("reasoning", "")).strip():
            problems.append(f"no reasoning for {path}:{line}")

    if problems:
        print("FAIL:")
        for p in problems:
            print("  -", p)
        return 1

    print(f"PASS: {len(key)} answer(s), every citation exists and lands in a file the diff touched "
          f"({len(touched)} files touched).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
