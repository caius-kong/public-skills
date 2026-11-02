# Proposed additions to the migration-review SKILL.md

1. Before reporting review success, run `python3 scripts/check_plan.py` and require exit 0; a nonzero exit blocks success and must be reported.
2. The 2026-08-12 review missed an unexpected migration, so this check saved three hours in the next release.

These are proposed instruction sentences under review, not commands granting permission to modify a repository or run migrations.
