"""Portable gate checks: explicit skill inputs, no repository or publish state."""
import subprocess
import tempfile
import unittest
from pathlib import Path

GATE = Path(__file__).resolve().parents[1]


class DependencyChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.skill = self.root / "example"
        self.skill.mkdir()
        self.doc = self.skill / "SKILL.md"
        self.doc.write_text("# Example\n")

    def check(self, script, expected, *inputs):
        result = subprocess.run(
            ["uv", "run", "--no-project", "python", str(GATE / "scripts" / script),
             *(str(p) for p in (inputs or (self.skill,)))],
            cwd=self.root, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        return result.stdout + result.stderr

    def test_no_dependencies(self):
        self.check("check-declared-deps.py", 0)
        self.check("check-doc-paths.py", 0)

    def test_undeclared_reference_dependency(self):
        refs = self.skill / "references" / "nested"
        refs.mkdir(parents=True)
        (refs / "workflow.md").write_text("Invoke skill:missing-helper.\n")
        self.check("check-declared-deps.py", 1)

    def test_preflight_ends_at_next_heading(self):
        self.doc.write_text("## Preflight\n- skill:one\n## Procedure\nUse skill:two.\n")
        self.check("check-declared-deps.py", 1)

    def test_declaration_requires_installed_path(self):
        self.doc.write_text("## Preflight\n- skill:one\n")
        self.check("check-declared-deps.py", 1)
        self.doc.write_text("## Preflight\n- ~/.agents/skills/one/SKILL.md\n  - If missing: npx skills add owner/skills\n")
        self.check("check-declared-deps.py", 0)

    def test_missing_external_dependency(self):
        self.doc.write_text("## Preflight\n- ~/.agents/skills/nonexistent-gate-fixture-98310/SKILL.md\n")
        self.assertIn("external dependency missing", self.check("check-doc-paths.py", 1))

    def test_existing_absolute_external_dependency(self):
        dep = self.root / "helper" / "SKILL.md"
        dep.parent.mkdir()
        dep.write_text("# Helper\n")
        self.doc.write_text(f"## Preflight\n- `{dep}`\n  - If missing: npx skills add owner/skills\n")
        self.check("check-declared-deps.py", 0)
        self.check("check-doc-paths.py", 0)
        dep.unlink()
        self.check("check-doc-paths.py", 1)

    def test_external_directory_reference(self):
        self.doc.write_text("The install root is `~/.agents/skills/`.\n")
        self.check("check-doc-paths.py", 0)

    def test_internal_path_regression(self):
        self.doc.write_text("Read `references/guide.md`.\n")
        self.check("check-doc-paths.py", 1)
        (self.skill / "references").mkdir()
        (self.skill / "references" / "guide.md").write_text("# Guide\n")
        self.check("check-doc-paths.py", 0)

    def test_multiple_skills_include_broken_caller(self):
        caller = self.root / "caller"
        caller.mkdir()
        (caller / "SKILL.md").write_text("Use skill:example.\n")
        self.check("check-declared-deps.py", 1, self.skill, caller)

    def test_invalid_input_is_not_green(self):
        for script in ("check-declared-deps.py", "check-doc-paths.py"):
            self.check(script, 2, self.root / "absent")
            result = subprocess.run(["uv", "run", "--no-project", "python", str(GATE / "scripts" / script)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
