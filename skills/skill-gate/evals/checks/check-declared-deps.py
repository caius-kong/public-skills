#!/usr/bin/env python3
"""A skill that invokes another skill must declare it under `## Preflight`.

skill-gate states that rule; this is its mechanical half. A per-skill preflight
resolves what a skill declared, so it cannot see the other failure: a dependency
named in prose (or in `references/`, `agents/`) and never declared at all. That
dependency breaks at run time with no warning, which is what this check reports.

Exit 0 = every dependency is declared, 1 = at least one is not.
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]   # <repo>/skills/skill-gate/evals/checks

# The sweep only means anything in the private repo: a published copy carries a
# subset of the skills, so it would scan three of them and exit 0 -- a green that
# says nothing. Refuse instead of lying.
MARKER = REPO / "publish-skill.sh"
if not MARKER.exists():
    print(f"NOT THE DEV REPO: {REPO} has no publish-skill.sh; "
          "this sweep only covers the private repo's skills", file=sys.stderr)
    sys.exit(2)
REF = re.compile(r"`?skill:([a-z0-9-]+)`?")
# The path form the rule asks for: an installed absolute path names the skill too.
PATH_REF = re.compile(r"~/[.]agents/skills/([a-z0-9-]+)/SKILL[.]md")
PREFLIGHT = "## Preflight"
# A real heading, not the phrase: skill-gate quotes "## Preflight" in its own
# rule text, which made it look compliant while it had no such section.
HEADING = re.compile(r"^##\s+Preflight\s*$", re.M)


def named_dependencies(doc):
    """Every other skill this one names, in either form, anywhere it can name one."""
    own = doc.parent.name
    used = set()
    texts = [doc.read_text(errors="replace")]
    for sub in ("references", "agents"):
        directory = doc.parent / sub
        if directory.exists():
            texts += [f.read_text(errors="replace") for f in sorted(directory.glob("*.md"))]
    for text in texts:
        used |= set(REF.findall(text)) | set(PATH_REF.findall(text))
    return used - {own}


def dependency_problems():
    """A skill that invokes another skill must declare it, under `## Preflight`.

    Two failures, both reported: naming a dependency and never declaring it (so
    nothing resolves it at run time), and naming one outside the Preflight block
    while declaring something else. A per-skill preflight cannot see either -- it
    only ever looks at what was declared, and most skills have no preflight at all.
    """
    problems = []
    for doc in sorted(REPO.glob("skills/**/SKILL.md")):
        parts = doc.relative_to(REPO).parts
        if any(part.endswith("-workspace") or part.startswith("iteration-") for part in parts):
            continue
        used = named_dependencies(doc)
        if not used:
            continue
        text = doc.read_text(errors="replace")
        heading = HEADING.search(text)
        if heading is None:
            problems.append(f"{doc.relative_to(REPO)} names {sorted(used)} but has no "
                            f"{PREFLIGHT!r} section")
            continue
        body = text[heading.end():]
        declared = set(PATH_REF.findall(body)) | set(REF.findall(body))
        missing = sorted(used - declared)
        if missing:
            problems.append(f"{doc.relative_to(REPO)} names {missing} outside its "
                            f"{PREFLIGHT!r} block")
    return problems


def main():
    problems = dependency_problems()
    for line in problems:
        print(f"UNDECLARED  {line}")
    print(f"{len(problems)} undeclared dependency problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
