---
name: "report-exporter"
description: "Export workspace usage reports to CSV on a schedule."
---
## Export Procedure
1. Run `scripts/export.py --format csv --out reports/` to produce the report.
2. Invoke the export agent with `timeoutMs: 900000` (15m). The export may be slow on large workspaces — the 2026-05-12 export run exhausted the 600s default, so the budget should be generous.
3. On timeout, do not retry; report the timeout to the user and stop.
