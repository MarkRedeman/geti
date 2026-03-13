#!/usr/bin/env bash

set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost}"
HOST_HEADER="${HOST_HEADER:-geti.localhost}"
SMOKE_PATHS="${SMOKE_PATHS:-/,/dex,/api/v1/healthz,/api/v1/onboarding/user,/api/v1/admin/onboarding/tokens,/api/v1/users/reset_password,/api/v1/organizations/test/workspaces/test/jobs}"

curl_check() {
	local path="$1"
	local expected="$2"

	local code
	code=$(curl -sS -o /dev/null -w "%{http_code}" -H "Host: ${HOST_HEADER}" "${BASE_URL}${path}")

	if [[ "${code}" != "${expected}" ]]; then
		printf 'Smoke check failed: %s expected %s got %s\n' "${path}" "${expected}" "${code}" >&2
		return 1
	fi

	printf 'Smoke check passed: %s -> %s\n' "${path}" "${code}"
}

curl_check_not_404() {
	local path="$1"

	local code
	code=$(curl -sS -o /dev/null -w "%{http_code}" -H "Host: ${HOST_HEADER}" "${BASE_URL}${path}")

	if [[ "${code}" == "404" ]]; then
		printf 'Smoke check failed: %s returned 404\n' "${path}" >&2
		return 1
	fi

	printf 'Smoke check passed: %s routed -> %s\n' "${path}" "${code}"
}

echo "Running Traefik smoke checks against ${BASE_URL} (Host: ${HOST_HEADER})"

IFS=',' read -r -a paths <<<"${SMOKE_PATHS}"
for path in "${paths[@]}"; do
	curl_check_not_404 "${path}"
done

echo "Traefik smoke checks completed successfully."
