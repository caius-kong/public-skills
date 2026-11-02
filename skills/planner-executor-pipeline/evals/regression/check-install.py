#!/usr/bin/env python3
"""Is this skill actually wired into the host?

Putting the node agents inside the skill keeps the assets together, at the price
of one line of global configuration: pi only finds `agents/` if the directory is
listed in `subagents.agentScanDirs`. A missing line fails loudly at dispatch
(unknown agent). A *stale copy* in the fixed agent directory does not: it
silently outranks the scan root and the skill's version never runs, which looks
exactly like a working install.

Usage: check-install.py [--skill-dir <dir>]

Exit codes: 0 = wired, 1 = not wired (or shadowed), 2 = cannot judge.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

PI_HOME = Path(os.environ.get("PI_HOME", Path.home() / ".pi" / "agent"))
FIXED_AGENTS = PI_HOME / "agents"
DEFAULT_SKILL = Path(__file__).resolve().parents[2]

NODES = {"plan.md": "plan", "test-author.md": "test-author", "executor.md": "executor"}


def frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    return m.group(1) if m else ""


def scalar(fm, key):
    # [ \t] rather than \s: \s would swallow the newline and capture the
    # first block-list item as if it were an inline value.
    m = re.search(rf"^{key}:[ \t]*(.+)$", fm, re.M)
    return m.group(1).strip() if m else None


def listed(fm, key):
    """A list field given either inline (a, b) or as a block list."""
    inline = scalar(fm, key)
    if inline:
        return [s.strip() for s in inline.split(",") if s.strip()]
    block = re.search(rf"^{key}:\s*\n((?:\s*-\s*.+\n)+)", fm, re.M)
    if not block:
        return []
    return [line.strip()[1:].strip() for line in block.group(1).splitlines() if line.strip().startswith("-")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill-dir", default=str(DEFAULT_SKILL))
    args = ap.parse_args()

    skill = Path(args.skill_dir).resolve()
    agents_dir = skill / "agents"
    problems = []

    if not agents_dir.is_dir():
        print(f"CANNOT JUDGE: no agents directory at {agents_dir}")
        return 2

    # 1. The scan root must name this directory.
    settings_path = PI_HOME / "settings.json"
    if not settings_path.exists():
        print(f"CANNOT JUDGE: no settings.json at {settings_path}")
        return 2
    settings = json.loads(settings_path.read_text())
    scan_dirs = [str(Path(p).resolve()) for p in settings.get("subagents", {}).get("agentScanDirs", [])]
    if str(agents_dir) not in scan_dirs:
        problems.append(
            f"subagents.agentScanDirs does not list {agents_dir} — pi will not discover these agents"
        )

    # 2. No stale copy may outrank the scan root.
    for filename in NODES:
        shadow = FIXED_AGENTS / filename
        if shadow.exists():
            problems.append(
                f"{shadow} shadows {agents_dir / filename}: the fixed agent directory outranks scan roots, "
                "so the skill's version never runs"
            )

    # 3. Every declared path must resolve, relative to the agent file.
    for filename in NODES:
        path = agents_dir / filename
        if not path.exists():
            problems.append(f"missing node agent definition: {path}")
            continue
        fm = frontmatter(path.read_text())
        if not fm:
            problems.append(f"{filename}: no frontmatter")
            continue
        name = scalar(fm, "name")
        if name != NODES[filename]:
            problems.append(f"{filename}: name is {name!r}, expected {NODES[filename]!r}")
        skill_path = scalar(fm, "skillPath")
        if skill_path:
            target = (path.parent / skill_path).resolve()
            if not (target / "SKILL.md").exists():
                problems.append(f"{filename}: skillPath {skill_path!r} -> {target}, which has no SKILL.md")
        for guard in listed(fm, "subagentOnlyExtensions"):
            target = (path.parent / guard).resolve()
            if not target.exists():
                problems.append(f"{filename}: extension {guard!r} -> {target} does not exist")

    if problems:
        print("FAIL: this skill is not wired into the host.")
        for p in problems:
            print("  -", p)
        return 1

    print(f"PASS: {len(NODES)} node agents under {agents_dir} are discoverable, unshadowed, and their extensions resolve.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
