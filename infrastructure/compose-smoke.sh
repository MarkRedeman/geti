#!/usr/bin/env bash

set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost}"
HOST_HEADER="${HOST_HEADER:-geti.localhost}"

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

# Web route via Traefik
curl_check_not_404 "/"

# Dex route should be routed by Traefik (code may vary by Dex state, route must not be 404)
curl_check_not_404 "/dex"

# Representative API paths that should route away from web catch-all
curl_check_not_404 "/api/v1/healthz"

curl_check_not_404 "/api/v1/organizations/test/workspaces/test/jobs"

echo "Traefik smoke checks completed successfully."
