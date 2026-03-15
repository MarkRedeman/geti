#!/usr/bin/env bash

set -euo pipefail

RESET=0
SEED=1
SEED_WEIGHTS=0
DEX_DB_PATH="infrastructure/data/dex/dex.db"
S3_READY_URL="http://127.0.0.1:8333"

ensure_dex_db_file() {
	mkdir -p "$(dirname "${DEX_DB_PATH}")"

	# If the bind-mount target is missing, Docker can create a directory at this
	# path. Dex expects a file, so normalize it here.
	if [[ -d "${DEX_DB_PATH}" ]]; then
		rm -rf "${DEX_DB_PATH}"
	fi

	if [[ ! -f "${DEX_DB_PATH}" ]]; then
		touch "${DEX_DB_PATH}"
	fi

	# Dex may run as non-root in container; ensure sqlite file is writable.
	chmod 666 "${DEX_DB_PATH}"
}

wait_for_s3() {
	local max_attempts=60
	local sleep_seconds=2
	local attempt=1

	echo "Waiting for S3 to accept connections at ${S3_READY_URL}..."
	while ((attempt <= max_attempts)); do
		if curl -fsS "${S3_READY_URL}" >/dev/null 2>&1; then
			echo "S3 is ready."
			return 0
		fi

		echo "S3 not ready yet (attempt ${attempt}/${max_attempts}), retrying in ${sleep_seconds}s..."
		sleep "${sleep_seconds}"
		((attempt++))
	done

	echo "Timed out waiting for S3 readiness."
	return 1
}

get_bootstrap_env() {
	local key="$1"
	local default_value="$2"
	local value="${!key:-}"

	if [[ -n "${value}" ]]; then
		echo "${value}"
		return 0
	fi

	if [[ -f ".env" ]]; then
		while IFS= read -r line; do
			[[ -z "${line}" || "${line}" =~ ^[[:space:]]*# ]] && continue
			if [[ "${line}" == "${key}="* ]]; then
				echo "${line#*=}"
				return 0
			fi
		done <.env
	fi

	echo "${default_value}"
}

sync_initial_user_ldap_password() {
	local initial_user_email
	local initial_user_password
	local ldap_admin_password
	local max_attempts=20
	local sleep_seconds=3
	local attempt=1
	local search_output
	local user_dn=""

	initial_user_email="$(get_bootstrap_env INITIAL_USER_EMAIL "admin@geti.local")"
	initial_user_password="$(get_bootstrap_env INITIAL_USER_PASSWORD "AdminPassword123!")"
	ldap_admin_password="$(get_bootstrap_env LDAP_ADMIN_PASSWORD "admin")"

	if [[ -z "${initial_user_email}" || -z "${initial_user_password}" ]]; then
		echo "Skipping LDAP password sync: INITIAL_USER_EMAIL or INITIAL_USER_PASSWORD is empty."
		return 0
	fi

	echo "Synchronizing LDAP password for ${initial_user_email}..."
	while ((attempt <= max_attempts)); do
		if search_output="$(docker compose exec -T openldap ldapsearch -x -H ldap://localhost:389 -D "cn=admin,dc=example,dc=org" -w "${ldap_admin_password}" -b "dc=example,dc=org" "(mail=${initial_user_email})" dn 2>/dev/null)"; then
			user_dn=""
			while IFS= read -r line; do
				if [[ "${line}" == dn:\ * ]]; then
					user_dn="${line#dn: }"
					break
				fi
			done <<<"${search_output}"

			if [[ -n "${user_dn}" ]]; then
				docker compose exec -T openldap ldappasswd -x -H ldap://localhost:389 -D "cn=admin,dc=example,dc=org" -w "${ldap_admin_password}" -s "${initial_user_password}" "${user_dn}" >/dev/null
				echo "LDAP password synchronized for ${initial_user_email}."
				return 0
			fi
		fi

		echo "Could not find LDAP user '${initial_user_email}' yet (attempt ${attempt}/${max_attempts}), retrying in ${sleep_seconds}s..."
		sleep "${sleep_seconds}"
		((attempt++))
	done

	echo "Failed to synchronize LDAP password for '${initial_user_email}'."
	return 1
}

ensure_ldap_groups_for_dex() {
	local initial_user_email
	local ldap_admin_password
	local max_attempts=20
	local sleep_seconds=3
	local attempt=1
	local search_output
	local user_dn=""
	local found_uid=""

	initial_user_email="$(get_bootstrap_env INITIAL_USER_EMAIL "admin@geti.local")"
	ldap_admin_password="$(get_bootstrap_env LDAP_ADMIN_PASSWORD "admin")"

	if [[ -z "${initial_user_email}" ]]; then
		echo "Skipping LDAP group setup: INITIAL_USER_EMAIL is empty."
		return 0
	fi

	echo "Ensuring LDAP group structure exists for Dex group lookup..."
	while ((attempt <= max_attempts)); do
		if search_output="$(docker compose exec -T openldap ldapsearch -LLL -x -H ldap://localhost:389 -D "cn=admin,dc=example,dc=org" -w "${ldap_admin_password}" -b "dc=example,dc=org" "(mail=${initial_user_email})" uid dn 2>/dev/null)"; then
			user_dn=""
			found_uid=""
			while IFS= read -r line; do
				if [[ "${line}" == uid:\ * ]]; then
					found_uid="${line#uid: }"
				elif [[ "${line}" == dn:\ * ]]; then
					user_dn="${line#dn: }"
				fi
			done <<<"${search_output}"

			if [[ -n "${found_uid}" && -n "${user_dn}" ]]; then
				if ! docker compose exec -T openldap ldapsearch -LLL -x -H ldap://localhost:389 -D "cn=admin,dc=example,dc=org" -w "${ldap_admin_password}" -b "ou=Groups,dc=example,dc=org" "(objectClass=organizationalUnit)" dn 2>/dev/null | grep -q '^dn: '; then
					docker compose exec -T openldap ldapadd -x -H ldap://localhost:389 -D "cn=admin,dc=example,dc=org" -w "${ldap_admin_password}" <<'LDIF' >/dev/null
dn: ou=Groups,dc=example,dc=org
objectClass: organizationalUnit
ou: Groups
LDIF
				fi

				if ! docker compose exec -T openldap ldapsearch -LLL -x -H ldap://localhost:389 -D "cn=admin,dc=example,dc=org" -w "${ldap_admin_password}" -b "ou=Groups,dc=example,dc=org" "(cn=regular_users)" dn 2>/dev/null | grep -q '^dn: '; then
					docker compose exec -T openldap ldapadd -x -H ldap://localhost:389 -D "cn=admin,dc=example,dc=org" -w "${ldap_admin_password}" <<'LDIF' >/dev/null
dn: cn=regular_users,ou=Groups,dc=example,dc=org
objectClass: top
objectClass: posixGroup
cn: regular_users
gidNumber: 501
LDIF
				fi

				docker compose exec -T openldap ldapmodify -x -H ldap://localhost:389 -D "cn=admin,dc=example,dc=org" -w "${ldap_admin_password}" <<LDIF >/dev/null 2>&1 || true
dn: cn=regular_users,ou=Groups,dc=example,dc=org
changetype: modify
add: memberUid
memberUid: ${found_uid}
LDIF
				echo "LDAP groups prepared for Dex (regular_users includes uid ${found_uid})."
				return 0
			fi
		fi

		echo "Could not resolve LDAP uid for '${initial_user_email}' yet (attempt ${attempt}/${max_attempts}), retrying in ${sleep_seconds}s..."
		sleep "${sleep_seconds}"
		((attempt++))
	done

	echo "Failed to prepare LDAP groups for '${initial_user_email}'."
	return 1
}

usage() {
	cat <<'EOF'
Usage: infrastructure/compose-bootstrap.sh [--reset] [--no-seed] [--seed-weights]

Options:
  --reset     Stop stack, remove compose volumes, and delete Dex sqlite DB before bootstrap.
  --no-seed   Skip initial user/org/workspace seeding step.
  --seed-weights  Run pretrained weights uploader via uv after migration.
  -h, --help  Show this help message.

Examples:
  # Standard bootstrap (infra + migration + seed)
  bash infrastructure/compose-bootstrap.sh

  # Full clean re-bootstrap and re-seed
  bash infrastructure/compose-bootstrap.sh --reset

  # Bootstrap and pre-populate pretrainedweights bucket
  bash infrastructure/compose-bootstrap.sh --seed-weights
EOF
}

seed_pretrained_weights() {
	if ! command -v uv >/dev/null 2>&1; then
		echo "Skipping pretrained weights upload: 'uv' is not installed."
		echo "Install uv (https://docs.astral.sh/uv/) or run without --seed-weights."
		return 1
	fi

	local s3_access_key
	local s3_secret_key
	local weights_url
	local weights_dir
	local config_dir

	s3_access_key="$(get_bootstrap_env S3_ACCESS_KEY "${S3_ACCESS_KEY:-minio}")"
	s3_secret_key="$(get_bootstrap_env S3_SECRET_KEY "${S3_SECRET_KEY:-minio123}")"
	weights_url="$(get_bootstrap_env WEIGHTS_URL "https://storage.geti.intel.com/weights")"
	weights_dir="$(get_bootstrap_env COMPOSE_BOOTSTRAP_WEIGHTS_DIR "/tmp/geti-pretrained-weights")"
	config_dir="platform/services/weights_uploader/app/pretrained_models"

	mkdir -p "${weights_dir}"

	echo "Running pretrained weights uploader (this may take time on first run)..."
	S3_HOST="127.0.0.1:8333" \
		S3_ACCESS_KEY="${s3_access_key}" \
		S3_SECRET_KEY="${s3_secret_key}" \
		WEIGHTS_DIR="${weights_dir}" \
		WEIGHTS_URL="${weights_url}" \
		CONFIG_DIR="${config_dir}" \
		uv run --project platform/services/weights_uploader python app/weights_uploader.py

	echo "Pretrained weights uploader completed."
}

while [[ $# -gt 0 ]]; do
	case "$1" in
	--reset)
		RESET=1
		shift
		;;
	--no-seed)
		SEED=0
		shift
		;;
	--seed-weights)
		SEED_WEIGHTS=1
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

	echo "Reset requested: removing Dex sqlite DB..."
	rm -rf "${DEX_DB_PATH}"
fi

echo "Ensuring Dex sqlite path is a file..."
ensure_dex_db_file

echo "Preparing local auth proxy certificates..."
bash infrastructure/compose-prepare-certs.sh

echo "Starting compose infra prerequisites..."
docker compose up -d mongodb kafka s3

wait_for_s3

echo "Running migration bootstrap job..."
docker compose up --build --abort-on-container-exit --exit-code-from migration_job migration_job

if [[ "${SEED_WEIGHTS}" -eq 1 ]]; then
	seed_pretrained_weights
fi

if [[ "${SEED}" -eq 1 ]]; then
	echo "Starting seed prerequisites (db, spicedb, kafka, openldap, platform_account)..."
	docker compose up -d db spicedb kafka openldap platform_account

	echo "Running initial user/org/workspace seeding job..."
	docker compose up --build --abort-on-container-exit --exit-code-from platform_initial_user platform_initial_user

	echo "Ensuring LDAP password matches INITIAL_USER_PASSWORD..."
	sync_initial_user_ldap_password

	echo "Ensuring LDAP groups are compatible with Dex groupSearch..."
	ensure_ldap_groups_for_dex
fi

echo "Compose bootstrap completed."
