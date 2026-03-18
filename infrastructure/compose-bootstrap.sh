#!/usr/bin/env bash

set -euo pipefail

RESET=0
SEED_WEIGHTS=0

usage() {
	cat <<'EOF'
Usage: infrastructure/compose-bootstrap.sh [--reset] [--seed-weights] [--no-seed-weights]

Options:
  --reset            Stop stack and remove compose volumes before bootstrap.
  --seed-weights     Enable pretrained weights seeding in unified init service.
  --no-seed-weights  Disable pretrained weights seeding (default).
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

echo "Running unified init service (INIT_SEED_WEIGHTS=${SEED_WEIGHTS})..."
INIT_SEED_WEIGHTS="${SEED_WEIGHTS}" docker compose up --build --abort-on-container-exit --exit-code-from geti_init geti_init

echo "Compose bootstrap completed."
