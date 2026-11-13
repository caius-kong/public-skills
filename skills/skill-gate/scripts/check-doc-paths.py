#!/usr/bin/env python3
"""Resolve recognized resource and external skill paths in explicit skill inputs.

Scan SKILL.md and agents/**/*.md; references may quote non-operative paths, so
review their execution paths separately. Relative resources use the skill root.
Exit 0 = recognized paths resolve, 1 = missing paths, 2 = invalid input.
"""
import argparse
import re
from pathlib import Path
OWNED = ("scripts/", "references/", "agents/", "evals/", "skills/")
SKIP = ("handoffs/", "docs/specs/", ".git/")
EXTERNAL = ("~/.agents/skills/", "~/.pi/agent/skills/")

# `path/like/this.ext` inside a backtick span, or in a bare markdown link target.
SPAN = re.compile(r"`([^`\s]+)`")
LINK = re.compile(r"\]\(([^)\s]+)\)")
SKILL_PATH = re.compile(r"((?:~|/)[^\s`<>\"']*/SKILL[.]md)")

def candidates(text):
    seen = set()
    for pattern in (SPAN, LINK, SKILL_PATH):
        for match in pattern.finditer(text):
            path = match.group(1)
            if path not in seen:
                seen.add(path)
                yield path



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skills", nargs="+", type=Path, help="skill directories to validate")
    args = parser.parse_args()
    skills = [p.expanduser().resolve() for p in args.skills]
    for skill in skills:
        if not (skill / "SKILL.md").is_file():
            parser.error(f"not a skill directory: {skill}")
    problems = []
    checked = 0
    docs = [(skill, doc) for skill in skills
            for doc in [skill / "SKILL.md", *sorted((skill / "agents").rglob("*.md"))]]
    for skill_dir, doc in docs:
        text = doc.read_text(errors="replace")
        for raw in candidates(text):
            path = raw.split("#")[0].strip()
            if not path or path.startswith(SKIP) or "/" not in path:
                continue
            if "*" in path or "<" in path:   # globs and <placeholder> names are not paths
                continue
            if path.startswith(EXTERNAL) or (path.startswith(("/", "~/")) and path.endswith("/SKILL.md")):
                checked += 1
                resolved = Path(path).expanduser()
                if not resolved.exists() or (path.endswith("/SKILL.md") and not resolved.is_file()):
                    problems.append(f"{doc} -> {path} (external dependency missing)")
                continue
            if not path.startswith(OWNED):
                continue
            checked += 1
            if not (skill_dir / path).exists():
                problems.append(f"{doc} -> {path} (resolved: {skill_dir / path})")

    for line in problems:
        print(f"MISSING  {line}")
    print(f"{checked} skill-internal path reference(s) checked, {len(problems)} missing")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
