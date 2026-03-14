#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[compose-parity] Running jobs policy acceptance checks"
(
	cd "${ROOT_DIR}/interactive_ai/services/jobs"
	PYTHONPATH=tests:app uv run pytest tests/unit/policy/test_main.py -q
)

echo "[compose-parity] Running user_directory acceptance checks"
(
	cd "${ROOT_DIR}/platform/services/user_directory"
	PYTHONPATH=tests:app .venv/bin/pytest \
		tests/unit/service_connection/k8s_client/test_apis.py \
		tests/unit/service_connection/k8s_client/test_config_maps.py \
		tests/unit/service_connection/k8s_client/test_secrets.py \
		tests/unit/service_connection/test_smtp_client.py \
		tests/unit/test_endpoints/test_invite_user.py \
		tests/unit/test_endpoints/test_password_reset.py -q
)

echo "[compose-parity] Running observability acceptance checks"
(
	cd "${ROOT_DIR}/platform/services/observability"
	PYTHONPATH=tests:app uv run pytest \
		tests/unit/common/test_platform.py \
		tests/unit/test_endpoints/test_logs.py \
		tests/unit/service_connection/k8s_client/test_apis.py \
		tests/unit/service_connection/k8s_client/test_cluster_info.py -q
)

echo "[compose-parity] All acceptance checks passed."
