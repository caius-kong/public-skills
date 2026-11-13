#!/usr/bin/env python3
"""The GATE routing table in references/artifacts.md must match scripts/gate.py.

Three review rounds found the table saying something gate.py did not do (#4-#7
were documented as REPLAN while the script returned FIX_EXECUTE for every
failure). The table is prose, the mapping is code; comparing them is the only
mechanical guard against the two drifting apart again.

Exit 0 = table and script agree, 1 = they disagree (or one side is unreadable).
"""
import re
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2]   # .../planner-executor-pipeline
def gate_routing_drift():
    """The GATE routing table in artifacts.md must match the script's own mapping.

    Three of the review rounds found this table saying something gate.py did not
    do (#4-#7 were documented as REPLAN while the script returned FIX_EXECUTE for
    every failure). The table is prose; the mapping is code; comparing them is the
    only mechanical guard against the two drifting apart again.
    """
    gate = SKILL / "scripts/gate.py"
    table = SKILL / "references/artifacts.md"
    if not gate.exists() or not table.exists():
        return [f"gate routing: missing {gate if not gate.exists() else table}"]

    code = gate.read_text()
    match = re.search(r"REPLAN_CHECKS = \(([^)]*)\)", code)
    if not match:
        return ["gate routing: gate.py has no REPLAN_CHECKS tuple to compare against"]
    scripted = {re.sub(r"[^0-9]", "", n) for n in match.group(1).split(",") if n.strip()}

    documented = {}
    for line in table.read_text().splitlines():
        row = re.match(r"^\| #(\d) ", line)
        if not row:
            continue
        # Rows carrying a conditional branch (#2 "早于本阶段", #3 "若修复需改测试")
        # need prose to decide; only the unconditional rows can be compared.
        if "若" in line or "否则" in line or line.count("→") > 1:
            continue
        documented[row.group(1)] = "REPLAN" if "REPLAN" in line else "FIX_EXECUTE"
    if not documented:
        return ["gate routing: artifacts.md has no '| #n ...' routing rows to compare"]

    problems = []
    for number, destination in sorted(documented.items()):
        in_script = number in scripted
        if (destination == "REPLAN") != in_script:
            problems.append(f"gate routing: artifacts.md says #{number} -> {destination}, "
                            f"gate.py says {'REPLAN' if in_script else 'FIX_EXECUTE'}")
    return problems



def main():
    problems = gate_routing_drift()
    for line in problems:
        print(f"DRIFT  {line}")
    print(f"{len(problems)} gate routing drift(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
