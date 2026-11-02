---
name: "db-migrator"
description: "Run schema migrations against staging and production databases."
---
## Migration Procedure
1. Run `scripts/migrate.sh --env <target>` and capture the full output.
2. Verify the applied migration list matches the plan before declaring success.
3. On failure, stop and report the failing migration and its output to the user.
