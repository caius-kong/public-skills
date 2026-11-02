#!/usr/bin/env python3
"""Regenerate the skill mirrors PLAN dispatches, from the upstream originals.

PLAN must *run* `grilling` / `to-spec` / `to-tickets` as skills, not skim them as
reference files. Upstream marks two of the three `disable-model-invocation: true`,
and pi-subagents drops hidden skills from every child prompt, so a subagent can
never see them however they are named. The mirror keeps the upstream body
byte-for-byte and drops only that one frontmatter line, which makes the skill
visible again to agents whose `skillPath` includes this directory -- and to
nobody else, because a directory holding a SKILL.md is not scanned further.

Body drift is the failure this script exists to prevent: a mirror silently
becoming a paraphrase of a skill someone else maintains.

Usage:
  sync-skill-mirrors.py            # rewrite mirrors from upstream
  sync-skill-mirrors.py --check    # exit 1 if any mirror has drifted

Exit codes: 0 = in sync, 1 = drifted or broken, 2 = cannot judge.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
MIRROR_DIR = SKILL_DIR / "skills"
UPSTREAM_ROOT = Path.home() / ".agents" / "skills"
# The chain PLAN runs, in order. `grilling` needs no mirror: upstream leaves it
# visible, so naming it resolves to the real file and updates flow through.
CHAIN = ["grilling", "to-spec", "to-tickets"]
MIRRORS = ["to-spec", "to-tickets"]

HIDDEN_FLAG = "disable-model-invocation"


def split_frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        return None, None
    return m.group(1), m.group(2)


def body_hash(body):
    return hashlib.sha256(body.encode()).hexdigest()


def build_mirror(upstream_text):
    fm, body = split_frontmatter(upstream_text)
    if fm is None:
        raise SystemExit(f"CANNOT JUDGE: no frontmatter in upstream")
    kept = [line for line in fm.splitlines() if not line.strip().startswith(HIDDEN_FLAG)]
    return "---\n" + "\n".join(kept) + "\n---\n" + body, body


def visible_to_plan(name):
    """Resolve a skill name the way a PLAN subagent would: local mirror, then upstream."""
    candidates = [MIRROR_DIR / name / "SKILL.md", UPSTREAM_ROOT / name / "SKILL.md"]
    for path in candidates:
        if path.exists():
            fm, _ = split_frontmatter(path.read_text())
            return path, (fm is not None and HIDDEN_FLAG in fm)
    return None, None


def check_chain():
    """The point of the mirrors: every skill in the chain must reach PLAN."""
    problems = []
    for name in CHAIN:
        path, hidden = visible_to_plan(name)
        if path is None:
            problems.append(f"chain: {name} resolves nowhere -- PLAN cannot run it")
        elif hidden:
            problems.append(f"chain: {name} resolves to {path} which is hidden -- PLAN cannot see it")
    plan = SKILL_DIR / "agents" / "plan.md"
    if plan.exists():
        text = plan.read_text()
        for name in CHAIN:
            if name not in text:
                problems.append(f"chain: agents/plan.md does not name {name}")
    else:
        problems.append(f"chain: no agent definition at {plan}")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    if not UPSTREAM_ROOT.is_dir():
        print(f"CANNOT JUDGE: no upstream skills at {UPSTREAM_ROOT}")
        return 2

    problems, written = [], []
    for name in MIRRORS:
        upstream = UPSTREAM_ROOT / name / "SKILL.md"
        mirror_file = MIRROR_DIR / name / "SKILL.md"
        meta_file = MIRROR_DIR / name / "MIRROR.json"

        if not upstream.exists():
            problems.append(f"{name}: upstream missing at {upstream}")
            continue

        text = upstream.read_text()
        if HIDDEN_FLAG not in text:
            problems.append(
                f"{name}: upstream no longer sets {HIDDEN_FLAG}; the mirror has no reason to exist"
            )
            continue

        try:
            mirror_text, upstream_body = build_mirror(text)
        except SystemExit as exc:
            problems.append(f"{name}: {exc}")
            continue

        if args.check:
            if not mirror_file.exists():
                problems.append(f"{name}: no mirror at {mirror_file}")
                continue
            fm, body = split_frontmatter(mirror_file.read_text())
            if fm is None:
                problems.append(f"{name}: mirror has no frontmatter")
                continue
            if HIDDEN_FLAG in fm:
                problems.append(f"{name}: mirror still sets {HIDDEN_FLAG}, so no subagent can see it")
            if body != upstream_body:
                problems.append(
                    f"{name}: mirror body drifted from upstream "
                    f"({body_hash(body)[:12]} != {body_hash(upstream_body)[:12]}) -- rerun without --check"
                )
            if not meta_file.exists():
                problems.append(f"{name}: no MIRROR.json")
            continue

        mirror_file.parent.mkdir(parents=True, exist_ok=True)
        mirror_file.write_text(mirror_text)
        meta_file.write_text(
            json.dumps(
                {
                    "mirror_of": "~/" + str(upstream.relative_to(Path.home()))
                    if str(upstream).startswith(str(Path.home()))
                    else str(upstream),
                    "upstream_sha256": hashlib.sha256(text.encode()).hexdigest(),
                    "body_sha256": body_hash(upstream_body),
                    "note": f"body byte-identical to upstream; only {HIDDEN_FLAG} was dropped",
                },
                indent=2,
            )
            + "\n"
        )
        written.append(name)

    if args.check:
        problems.extend(check_chain())

    if problems:
        print("FAIL: mirrors are not in sync with upstream.")
        for p in problems:
            print("  -", p)
        return 1

    if args.check:
        print(f"PASS: {len(MIRRORS)} skill mirrors match upstream bodies byte for byte.")
    else:
        print(f"PASS: rewrote {len(written)} mirrors: {', '.join(written)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
