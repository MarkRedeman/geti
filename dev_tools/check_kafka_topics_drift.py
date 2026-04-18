#!/usr/bin/env python3

from __future__ import annotations

import ast
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INIT_FILE = ROOT / "infrastructure" / "geti_init" / "main.py"


def load_init_topics() -> set[str]:
    source = INIT_FILE.read_text(encoding="utf-8")
    module = ast.parse(source)
    for node in module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "KAFKA_TOPICS":
                    if not isinstance(node.value, ast.List):
                        raise RuntimeError("KAFKA_TOPICS must be a list literal")
                    values: set[str] = set()
                    for elt in node.value.elts:
                        if not isinstance(elt, ast.Constant) or not isinstance(
                            elt.value, str
                        ):
                            raise RuntimeError(
                                "KAFKA_TOPICS entries must be string literals"
                            )
                        values.add(elt.value)
                    return values
    raise RuntimeError("KAFKA_TOPICS not found in infrastructure/geti_init/main.py")


def discover_runtime_topic_usage() -> set[str]:
    topic_pattern = re.compile(r'topic\s*=\s*"([a-zA-Z0-9_]+)"')

    runtime_roots = [ROOT / "interactive_ai"]
    ignored_parts = {"tests", "test", ".venv", "venv", "site-packages", "__pycache__"}

    topics: set[str] = set()
    for runtime_root in runtime_roots:
        for py_file in runtime_root.rglob("*.py"):
            if any(part in ignored_parts for part in py_file.parts):
                continue
            text = py_file.read_text(encoding="utf-8")
            for match in topic_pattern.finditer(text):
                topics.add(match.group(1))

    return topics


def main() -> int:
    init_topics = load_init_topics()
    runtime_topics = discover_runtime_topic_usage()

    missing_in_init = sorted(runtime_topics - init_topics)
    stale_in_init = sorted(init_topics - runtime_topics)

    print(f"KAFKA_TOPICS count: {len(init_topics)}")
    print(f"Runtime topic usage count: {len(runtime_topics)}")

    if missing_in_init:
        print("\nTopics used at runtime but missing in KAFKA_TOPICS:")
        for topic in missing_in_init:
            print(f"  - {topic}")

    if stale_in_init:
        print("\nTopics present in KAFKA_TOPICS but not found in runtime usage:")
        for topic in stale_in_init:
            print(f"  - {topic}")

    if missing_in_init:
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
