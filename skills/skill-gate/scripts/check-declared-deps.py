#!/usr/bin/env python3
"""Check explicit skill directories for undeclared external skill references.

Recognizes skill:name and absolute SKILL.md paths, not arbitrary prose invocations.
Exit 0 = recognized references declared, 1 = problems, 2 = invalid input.
"""
import argparse
import re
from pathlib import Path

REF = re.compile(r"`?skill:([a-z0-9-]+)`?")
# The path form the rule asks for: an installed absolute path names the skill too.
PATH_REF = re.compile(r"(?:~|/)[^\s`<>\"']*/([a-z0-9-]+)/SKILL[.]md")
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
            texts += [f.read_text(errors="replace") for f in sorted(directory.rglob("*.md"))]
    for text in texts:
        used |= set(REF.findall(text)) | set(PATH_REF.findall(text))
    return used - {own}


def dependency_problems(skills):
    problems = []
    for skill in skills:
        doc = skill / "SKILL.md"
        used = named_dependencies(doc)
        if not used:
            continue
        text = doc.read_text(errors="replace")
        heading = HEADING.search(text)
        if heading is None:
            problems.append(f"{doc} names {sorted(used)} but has no "
                            f"{PREFLIGHT!r} section")
            continue
        body = re.split(r"^#{1,2}\s+", text[heading.end():], maxsplit=1, flags=re.M)[0]
        declared = set(PATH_REF.findall(body))
        missing = sorted(used - declared)
        if missing:
            problems.append(f"{doc} names {missing} without an installed absolute path in "
                            f"{PREFLIGHT!r}")
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skills", nargs="+", type=Path, help="skill directories to validate")
    args = parser.parse_args()
    skills = [p.expanduser().resolve() for p in args.skills]
    for skill in skills:
        if not (skill / "SKILL.md").is_file():
            parser.error(f"not a skill directory: {skill}")
    problems = dependency_problems(skills)
    for line in problems:
        print(f"UNDECLARED  {line}")
    print(f"{len(problems)} undeclared dependency problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
