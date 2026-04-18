#!/usr/bin/env bash

set -euo pipefail

CERT_DIR="${CERT_DIR:-infrastructure/data/auth_proxy/certs}"
KEY_FILE="${CERT_DIR}/tls.key"
CERT_FILE="${CERT_DIR}/tls.crt"

ensure_permissions() {
	# Distroless auth_proxy runs as non-root, so mounted cert files must be world-readable
	# for local compose use.
	chmod 644 "${KEY_FILE}" "${CERT_FILE}"
}

mkdir -p "${CERT_DIR}"

if [[ -f "${KEY_FILE}" && -f "${CERT_FILE}" ]]; then
	ensure_permissions
	echo "Auth proxy TLS certs already exist at ${CERT_DIR}."
	exit 0
fi

echo "Generating self-signed auth proxy TLS certs in ${CERT_DIR}..."
openssl req -x509 -nodes -newkey rsa:2048 \
	-keyout "${KEY_FILE}" \
	-out "${CERT_FILE}" \
	-days 365 \
	-subj "/CN=geti.localhost"

echo "Generated ${CERT_FILE} and ${KEY_FILE}."
ensure_permissions
