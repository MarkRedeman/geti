#!/usr/bin/env bash

set -euo pipefail

CERT_DIR="${CERT_DIR:-infrastructure/data/auth_proxy/certs}"
KEY_FILE="${CERT_DIR}/tls.key"
CERT_FILE="${CERT_DIR}/tls.crt"

mkdir -p "${CERT_DIR}"

if [[ -f "${KEY_FILE}" && -f "${CERT_FILE}" ]]; then
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
