#!/usr/bin/env python3
"""Every skill-internal path a SKILL.md or agents/*.md mentions must exist.

A skill that points at `scripts/foo.py` or `references/bar.md` breaks silently
when the file moves: the model reads a missing path, improvises, and the failure
looks like bad judgement rather than a broken pointer. That already happened once
here -- a prompt template pointed at an absolute script path that moved when the
script joined its skill.

Only paths under a directory a skill owns are checked. Runtime artefacts
(`handoffs/`, `docs/specs/`, `.git/`) are produced during a run, not shipped, and
are skipped by prefix. Eval workspaces (`*-workspace/`) are skipped wholesale:
they hold deliberately broken skills and recorded transcripts, where a dangling
path is the point.

Only the instruction surface is scanned -- `SKILL.md` and `agents/*.md`. Notes
under `references/` are evidence: research logs and e2e snapshots quote paths from
other repositories and from earlier states, where a missing file is the content,
not a defect.

Exit 0 = every named path resolves, 1 = at least one does not.
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
OWNED = ("scripts/", "references/", "agents/", "evals/", "skills/")
SKIP = ("handoffs/", "docs/specs/", ".git/")
# Absolute paths are checked too when they name another installed skill: a skill
# that depends on one must point at where it actually lives.
EXTERNAL = ("~/.agents/skills/", "~/.pi/agent/skills/")

# `path/like/this.ext` inside a backtick span, or in a bare markdown link target.
SPAN = re.compile(r"`([^`\s]+)`")
LINK = re.compile(r"\]\(([^)\s]+)\)")

def candidates(text):
    for pattern in (SPAN, LINK):
        for match in pattern.finditer(text):
            yield match.group(1)



def main():
    problems = []
    checked = 0
    docs = [*REPO.glob("skills/**/SKILL.md"), *REPO.glob("skills/**/agents/*.md")]
    for doc in sorted(docs):
        parts = doc.relative_to(REPO).parts
        if any(part.endswith("-workspace") or part.startswith("iteration-") for part in parts):
            continue
        skill_dir = next((p for p in doc.parents if (p / "SKILL.md").exists()), None)
        if skill_dir is None:
            continue
        text = doc.read_text(errors="replace")
        for raw in candidates(text):
            path = raw.split("#")[0].strip()
            if not path or path.startswith(SKIP) or "/" not in path:
                continue
            if "*" in path or "<" in path:   # globs and <placeholder> names are not paths
                continue
            if path.startswith(EXTERNAL):
                checked += 1
                resolved = Path(path.replace("~", str(Path.home()), 1))
                if not resolved.exists():
                    problems.append(f"{doc.relative_to(REPO)} -> {path} (external dependency missing)")
                continue
            if not path.startswith(OWNED):
                continue
            checked += 1
            if not (skill_dir / path).exists():
                problems.append(f"{doc.relative_to(REPO)} -> {path} (resolved: {skill_dir / path})")

    for line in problems:
        print(f"MISSING  {line}")
    print(f"{checked} skill-internal path reference(s) checked, {len(problems)} missing")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
