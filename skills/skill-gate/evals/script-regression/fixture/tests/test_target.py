import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from choose_target import choose_target
assert choose_target({"alert_target":"self"}, ["wrong"]) == "self"
try:
    choose_target({}, ["wrong"])
except ValueError:
    pass
else:
    raise AssertionError("missing destination must fail, not select wrong chat")
print("PASS: configured destination and unsafe default rejection")
