#!/usr/bin/env python3
"""Assert that a dispatched child started on the model the pipeline declared.

The core contract says "check the child's model against the declared one; on a
mismatch, HALT". On pi the checkable record is the child session header: every
child session opens with `session`, `model_change` (provider + modelId) and
`thinking_level_change` rows, written before the first turn.

What this proves: the host accepted the declared dispatch parameters and
started the child with them. What it does not prove: the provider served that
model, or that the child kept it for later turns. Global rules, never a lookup
table of extension internals.

Usage:
  verify-models.py --expect EXECUTE                  # newest-started child
  verify-models.py --expect EXECUTE --session PATH   # one exact child
  verify-models.py --expect EXECUTE --run <prefix>   # exact child by run id
  verify-models.py --list 5                          # diagnostic, no assertion

Exit: 0 assertion holds, 1 positive mismatch, 2 cannot determine (never a pass).
"""

import argparse
import glob
import json
import os
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent


def load_nodes():
    """Local binding overrides the template, per node, whole-node replacement."""
    nodes = {}
    for name in ("config.template.json", "config.json"):
        path = SKILL_DIR / name
        if not path.exists():
            continue
        for node, spec in json.loads(path.read_text()).get("nodes", {}).items():
            nodes[node.upper()] = (spec.get("model"), spec.get("thinking"))
    return nodes


def read_header(session_file):
    """provider / modelId / thinkingLevel from the rows written before turn one."""
    provider = model = thinking = None
    with open(session_file, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                break
            kind = row.get("type")
            if kind == "model_change":
                provider, model = row.get("provider"), row.get("modelId")
            elif kind == "thinking_level_change":
                thinking = row.get("thinkingLevel")
            elif kind != "session":
                break  # header rows come first; stop at the first real turn
    return provider, model, thinking


def child_root():
    parent = os.environ.get("PI_SESSION_FILE")
    if not parent:
        return None
    return parent[: -len(".jsonl")] if parent.endswith(".jsonl") else parent


def all_children():
    """Every child session of this session, oldest start first."""
    root = child_root()
    if not root:
        return []
    found = []
    for path in glob.glob(os.path.join(root, "*", "run-*", "session.jsonl")):
        try:
            with open(path, encoding="utf-8") as fh:
                started = json.loads(fh.readline()).get("timestamp") or ""
        except (OSError, json.JSONDecodeError):
            started = ""
        found.append((started, Path(path).parent.parent.name, path))
    found.sort()  # by start timestamp: a slow old run cannot outrank a new one
    return found


def same_model(expected, provider, model, thinking):
    """Template models carry no provider (portable); local bindings do. Compare
    the provider only when the expected side names one."""
    exp_model, exp_thinking = expected
    exp_provider, _, exp_id = (exp_model or "").rpartition("/")
    exp_provider = exp_provider or None  # bare id: provider-agnostic
    return exp_id == model and exp_provider in (None, provider) and exp_thinking == thinking


def describe(provider, model, thinking):
    return f"{provider + '/' if provider else ''}{model}:{thinking}" if model else ""


def report(run, path, provider, model, thinking, nodes, expected):
    if not model or not provider or not thinking:
        missing = "/".join(k for k, v in (("provider", provider), ("model", model), ("thinking", thinking)) if not v)
        print(f"{run}  UNDETERMINED  header lacks {missing} ({path})", file=sys.stderr)
        return 2
    matches = sorted(n for n, v in nodes.items() if same_model(v, provider, model, thinking))
    if expected:
        bad = [] if same_model(nodes[expected], provider, model, thinking) else [expected]
        if bad:
            exp = nodes[expected]
            print(f"{run}  MISMATCH  actual={describe(provider, model, thinking)}  expected: {expected}={exp[0]}:{exp[1]}")
            return 1
        print(f"{run}  OK  {describe(provider, model, thinking)}")
        return 0
    print(f"{run}  {describe(provider, model, thinking)}  matches: {','.join(matches) or 'NOT-IN-CONFIG'}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--expect", default="", help="one node name")
    ap.add_argument("--session", action="append", default=[])
    ap.add_argument("--run", action="append", default=[], help="child run id prefix")
    ap.add_argument("--list", type=int, default=0, help="diagnostic listing, no assertion")
    args = ap.parse_args()

    nodes = load_nodes()
    children = all_children()

    if args.list:
        if not children:
            print("no child session found for this session", file=sys.stderr)
            return 2
        for started, run, path in children[-args.list:]:
            provider, model, thinking = read_header(path)
            print(f"{run}  {started}  {describe(provider, model, thinking) or 'UNDETERMINED'}")
        return 0

    expected = args.expect.strip().upper()
    if not expected:
        print("--expect <node> is required (or --list for diagnostics)", file=sys.stderr)
        return 2
    if expected not in nodes:
        print(f"unknown node: {expected}", file=sys.stderr)
        return 2

    if args.session:
        chosen = [(Path(p).parent.parent.name if Path(p).parent.name.startswith("run-") else Path(p).name, p)
                  for p in args.session]
    elif args.run:
        chosen = []
        for prefix in args.run:
            hits = [(run, path) for _, run, path in children if run.startswith(prefix)]
            if len(hits) != 1:
                print(f"run prefix {prefix!r} matched {len(hits)} children", file=sys.stderr)
                return 2
            chosen.extend(hits)
    elif children:
        chosen = [children[-1][1:]]  # newest STARTED child
    else:
        print("no child session found for this session", file=sys.stderr)
        return 2

    worst = 0
    for run, path in chosen:
        try:
            provider, model, thinking = read_header(path)
        except OSError:
            print(f"{run}  UNDETERMINED  unreadable {path}", file=sys.stderr)
            worst = max(worst, 2)
            continue
        worst = max(worst, report(run, path, provider, model, thinking, nodes, expected))
    return worst


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # a crash must never read as "positive mismatch" (exit 1)
        print(f"cannot determine: {exc}", file=sys.stderr)
        sys.exit(2)
