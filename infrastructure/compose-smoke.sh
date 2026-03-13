#!/usr/bin/env bash

set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost}"
HOST_HEADER="${HOST_HEADER:-geti.localhost}"
SMOKE_PATHS="${SMOKE_PATHS:-/,/dex,/api/v1/healthz,/api/v1/onboarding/user,/api/v1/admin/onboarding/tokens,/api/v1/users/reset_password,/api/v1/organizations/test/workspaces/test/jobs,/api/v1/organizations/test/workspaces/test/projects/000000000000000000000000/pipelines/active/status}"
SMOKE_CHECKS="${SMOKE_CHECKS:-}"

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

run_smoke_check() {
	local path="$1"
	local expected="$2"

	case "${expected}" in
	not_404)
		curl_check_not_404 "${path}"
		;;
	2xx)
		local code
		code=$(curl -sS -o /dev/null -w "%{http_code}" -H "Host: ${HOST_HEADER}" "${BASE_URL}${path}")
		if [[ "${code}" != 2* ]]; then
			printf 'Smoke check failed: %s expected 2xx got %s\n' "${path}" "${code}" >&2
			return 1
		fi
		printf 'Smoke check passed: %s -> %s (2xx)\n' "${path}" "${code}"
		;;
	*)
		curl_check "${path}" "${expected}"
		;;
	esac
}

echo "Running Traefik smoke checks against ${BASE_URL} (Host: ${HOST_HEADER})"

if [[ -n "${SMOKE_CHECKS}" ]]; then
	IFS=',' read -r -a checks <<<"${SMOKE_CHECKS}"
	for check in "${checks[@]}"; do
		path="${check%%|*}"
		expected="${check##*|}"
		if [[ "${check}" != *"|"* ]]; then
			expected="not_404"
		fi
		run_smoke_check "${path}" "${expected}"
	done
else
	IFS=',' read -r -a paths <<<"${SMOKE_PATHS}"
	for path in "${paths[@]}"; do
		curl_check_not_404 "${path}"
	done
fi

echo "Traefik smoke checks completed successfully."
