#!/usr/bin/env python3
"""Resolve every external skill this pipeline declares, before a run starts.

The pipeline reads each dependency from its installed path. If one is missing,
PLAN discovers it halfway through its own procedure -- after the interview, when
the first read fails. This resolves all of them up front and prints the command
that installs whatever is absent.

Exit 0 = every dependency present; 1 = at least one missing (commands printed).
"""
import re
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
PREFLIGHT = "## Preflight"
# `- \`name\`: \`~/path/SKILL.md\`` followed by `  - If missing: \`command\``
ENTRY = re.compile(r"- `([a-z0-9-]+)`: `(~/\S+?/SKILL\.md)`\s*\n\s*- If missing: `([^`]+)`")


def dependencies():
    text = (SKILL / "SKILL.md").read_text()
    _, _, body = text.partition(PREFLIGHT)
    return ENTRY.findall(body)


def main():
    deps = dependencies()
    if not deps:
        print(f"CANNOT JUDGE: no dependency entries found under {PREFLIGHT!r}")
        return 2

    missing = []
    for name, raw, install in deps:
        path = Path(raw.replace("~", str(Path.home()), 1))
        if path.exists():
            print(f"ok       {name:16} {path}")
        else:
            print(f"MISSING  {name:16} {path}")
            missing.append((name, install))

    if missing:
        print("\nInstall before running:")
        for name, install in missing:
            print(f"  {name}: {install}")
        return 1

    print(f"\n{len(deps)} dependenc(ies) present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
