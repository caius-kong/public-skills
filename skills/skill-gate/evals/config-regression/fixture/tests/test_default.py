import json
from pathlib import Path
p=Path(__file__).resolve().parents[1]/"config.example.json"
assert json.loads(p.read_text())["auto_send"] is False, "shipped default must require approval"
print("PASS: approval default")
