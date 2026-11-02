#!/usr/bin/env python3
"""Did a node actually run the skills it was told to reuse, in the order it was told?

The pipeline's reason to exist is orchestration: each stage reuses an existing
skill's own procedure rather than a paraphrase of it. A paraphrase looks
identical in the output, so the only honest evidence is the transcript — the
child opened that skill file with the read tool, in sequence.

Usage:
  check-skill-reuse.py --transcript <child transcript.jsonl> --expect grilling,to-spec,to-tickets

Exit codes: 0 = every expected skill was read, in order, 1 = one was not read or
came out of order, 2 = could not judge (missing transcript, no read records).
"""
import argparse
import json
import sys
from pathlib import Path

def tool_path(record):
    """The path a read call opened, from the full payload when it survives."""
    payload = record.get("argsPayload")
    if payload:
        try:
            args = json.loads(payload)
        except json.JSONDecodeError:
            args = None
        if isinstance(args, dict):
            path = args.get("path") or args.get("file_path")
            if isinstance(path, str) and path:
                return path
    # argsPreview is truncated (~56 chars), so it can only ever be a last resort:
    # a long absolute path loses the skill directory name that identifies it.
    for token in (record.get("argsPreview") or "").replace('"', " ").replace("'", " ").split():
        if token.endswith("/SKILL.md"):
            return token.strip(",;:")
    return None


def read_targets(transcript):
    """Paths the child opened with the read tool, in call order."""
    targets = []
    for line in Path(transcript).read_text().splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("recordType") != "tool_start" or record.get("toolName") != "read":
            continue
        path = tool_path(record)
        if path:
            targets.append(path)
    return targets


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--transcript", required=True)
    ap.add_argument("--expect", required=True, help="comma-separated skill names, in required order")
    args = ap.parse_args()

    if not Path(args.transcript).exists():
        print(f"CANNOT JUDGE: no transcript at {args.transcript}")
        return 2

    targets = read_targets(args.transcript)
    if not targets:
        print("CANNOT JUDGE: transcript has no read records with an identifiable path")
        return 2

    expected = [s.strip() for s in args.expect.split(",") if s.strip()]
    problems, cursor = [], 0
    for name in expected:
        # A reused skill is read either at the upstream path or at this skill's
        # mirror of it; both end in /<name>/SKILL.md, which is what identifies it.
        suffix = f"/{name}/SKILL.md"
        found = None
        for index in range(cursor, len(targets)):
            if targets[index].endswith(suffix):
                found = index
                break
        if found is None:
            problems.append(f"{name}: never read after position {cursor} (expected *{suffix})")
            print(f"MISS {name:14} -> *{suffix}")
            continue
        cursor = found + 1
        print(f"ok   {name:14} -> {targets[found]}")

    if problems:
        print(f"\nFAIL: {len(problems)} expected skill(s) missing or out of order:")
        for problem in problems:
            print("  -", problem)
        print("Any resemblance in the output is paraphrase, or the steps ran in the wrong order.")
        return 1

    print(f"\nPASS: read {len(expected)} expected skill file(s) in order; {len(targets)} read call(s) total.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
