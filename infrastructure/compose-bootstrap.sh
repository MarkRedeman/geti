#!/usr/bin/env bash

set -euo pipefail

RESET=0
SEED_WEIGHTS=1

sync_dex_password_connector() {
	local dex_config="infrastructure/data/dex/config.yml"
	if [[ ! -f "${dex_config}" ]]; then
		echo "Skipping Dex config sync: ${dex_config} not found"
		return
	fi

	# Load INITIAL_USER_PASSWORD from .env if present.
	local initial_user_password="${INITIAL_USER_PASSWORD:-}"
	if [[ -z "${initial_user_password}" && -f ".env" ]]; then
		initial_user_password=$(grep -E '^INITIAL_USER_PASSWORD=' .env | tail -n 1 | cut -d '=' -f2-)
	fi

	if [[ -z "${initial_user_password}" ]]; then
		echo "Skipping Dex password hash sync: INITIAL_USER_PASSWORD is not set"
		return
	fi

	local bcrypt_hash
	bcrypt_hash=$(docker run --rm -e PASS="${initial_user_password}" httpd:2.4-alpine sh -lc '/usr/local/apache2/bin/htpasswd -bnBC 10 "" "$PASS" | tr -d ":\n"')
	if [[ -z "${bcrypt_hash}" || "${bcrypt_hash}" != \$2* ]]; then
		echo "Failed to generate Dex bcrypt hash"
		exit 1
	fi

	python - "$dex_config" "$bcrypt_hash" <<'PY'
import re
import sys
from pathlib import Path

config_path = Path(sys.argv[1])
password_hash = sys.argv[2]
content = config_path.read_text()

updated = re.sub(r'(?m)^(\s*passwordConnector:\s*).+$', r'\1local', content)
updated = re.sub(r'(?m)^(\s*hash:\s*").*("\s*)$', rf'\1{password_hash}\2', updated, count=1)

if updated != content:
    config_path.write_text(updated)
PY

	echo "Synced Dex local password connector and static password hash"
}

usage() {
	cat <<'EOF'
Usage: infrastructure/compose-bootstrap.sh [--reset] [--seed-weights] [--no-seed-weights]

Options:
  --reset            Stop stack and remove compose volumes before bootstrap.
  --seed-weights     Enable pretrained weights seeding in unified init service (default).
  --no-seed-weights  Disable pretrained weights seeding.
  -h, --help         Show this help message.
EOF
}

while [[ $# -gt 0 ]]; do
	case "$1" in
	--reset)
		RESET=1
		shift
		;;
	--seed-weights)
		SEED_WEIGHTS=1
		shift
		;;
	--no-seed-weights)
		SEED_WEIGHTS=0
		shift
		;;
	-h | --help)
		usage
		exit 0
		;;
	*)
		echo "Unknown option: $1"
		usage
		exit 1
		;;
	esac
done

if [[ "${RESET}" -eq 1 ]]; then
	echo "Reset requested: stopping stack and removing compose volumes..."
	docker compose down -v --remove-orphans
fi

sync_dex_password_connector

echo "Running unified init service (INIT_SEED_WEIGHTS=${SEED_WEIGHTS})..."
INIT_SEED_WEIGHTS="${SEED_WEIGHTS}" docker compose up --build --abort-on-container-exit --exit-code-from geti_init geti_init

echo "Compose bootstrap completed."
