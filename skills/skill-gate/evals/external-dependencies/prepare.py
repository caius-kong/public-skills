"""Prepare isolated case-10 inputs: uv run --no-project python prepare.py <run-dir>."""
import argparse
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("run_dir", type=Path)
root = parser.parse_args().run_dir.resolve() / "inputs"
for name in ("undeclared", "missing", "valid", "helper"):
    (root / name).mkdir(parents=True, exist_ok=True)
(root / "undeclared/references").mkdir(exist_ok=True)
(root / "undeclared/SKILL.md").write_text(
    "# Undeclared\nRead `references/workflow.md` for execution.\n")
(root / "undeclared/references/workflow.md").write_text(
    "Invoke skill:nonexistent-gate-fixture-helper to process the result.\n")
(root / "missing/SKILL.md").write_text(
    "# Missing\n## Preflight\n"
    "- `~/.agents/skills/nonexistent-gate-fixture-helper/SKILL.md`\n"
    "  - If missing: `npx skills add example/helpers`\n"
    "## Procedure\nRead the helper and execute its workflow.\n")
(root / "helper/SKILL.md").write_text("# Helper\nReturn a local summary.\n")
(root / "valid/references").mkdir(exist_ok=True)
(root / "valid/references/guide.md").write_text("Return a local summary.\n")
(root / "valid/SKILL.md").write_text(
    f"# Valid\n## Preflight\n- `{root}/helper/SKILL.md`\n"
    "  - If missing: `npx skills add example/helpers`\n"
    "## Procedure\nRead the installed helper and `references/guide.md`.\n")
