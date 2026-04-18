#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[compose-parity] Running jobs policy acceptance checks"
(
	cd "${ROOT_DIR}/interactive_ai/services/jobs"
	PYTHONPATH=tests:app uv run pytest tests/unit/policy/test_main.py -q
)

echo "[compose-parity] All acceptance checks passed."
