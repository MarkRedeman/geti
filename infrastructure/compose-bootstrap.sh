#!/usr/bin/env bash

set -euo pipefail

echo "Starting compose infra prerequisites..."
docker compose up -d mongodb kafka s3

echo "Running migration bootstrap job..."
docker compose up --build --abort-on-container-exit --exit-code-from migration_job migration_job

echo "Compose bootstrap completed."
