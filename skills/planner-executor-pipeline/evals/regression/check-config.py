#!/usr/bin/env python3
"""T1 机械校验：config 声明的 model/thinking 是否在宿主目录中可用。

pi 专用（读 ~/.pi/agent/models.json）。其它 harness 需替换本脚本的目录读取部分。
退出码 0 = 全部通过；1 = 有节点不可用。
"""
import json
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2]
CONFIG = SKILL / "config.json"
TEMPLATE = SKILL / "config.template.json"
MODELS = Path.home() / ".pi/agent/models.json"


def load(path):
    return json.loads(path.read_text())


def catalog():
    data = load(MODELS)
    out = {}
    for provider, body in data.get("providers", {}).items():
        for model in body.get("models", []):
            if isinstance(model, dict) and "id" in model:
                out[f"{provider}/{model['id']}"] = model
    return out


def resolve(nodes, template_nodes):
    """节点级整条覆盖：本地有该节点则整条用本地，否则用模板。"""
    effective = {}
    for node in template_nodes:
        effective[node] = nodes.get(node) or template_nodes[node]
    return effective


def main():
    cat = catalog()
    local, template = load(CONFIG), load(TEMPLATE)
    effective = resolve(local["nodes"], template["nodes"])
    failures = []

    for node, spec in effective.items():
        full = spec["model"]
        entry = cat.get(full)
        if entry is None:
            failures.append(f"{node}: model '{full}' 不在宿主目录中")
            continue
        level = spec["thinking"]
        mapping = entry.get("thinkingLevelMap") or {}
        if level not in mapping:
            failures.append(f"{node}: '{full}' 无 thinking 档 '{level}'")
        elif mapping[level] is None:
            failures.append(f"{node}: '{full}' 的档 '{level}' 映射为 null（该档不可用）")
        source = "config.json" if node in local["nodes"] else "config.template.json"
        print(f"{node:<12} {full}:{level:<8} ok  ({source})")

    if failures:
        print("\nFAIL:")
        for line in failures:
            print(" -", line)
        return 1
    print("\nT1 PASS（仅证明启动一致性）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
