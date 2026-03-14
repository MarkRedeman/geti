# Getting Started with Geti on Docker Compose

A concise, command-first guide for bringing up the Geti platform locally using Docker Compose.

---

## 1. Prerequisites

**Docker + Docker Compose**

Docker Engine and the Compose plugin (v2) must be installed and running.

```bash
docker version
docker compose version
```

**OpenSSL**

Used to generate local TLS certificates for the auth proxy.

```bash
openssl version
```

**Disk space**

Building all images from source requires significant disk space. Expect at least **20–30 GB** of free space for a full stack build, including image layers, named volumes, and runtime data. Run `df -h` and check `docker system df` before starting.

---

## 2. First-Time Setup

Work from the repository root for all commands below.

### 2a. Validate the Compose config

Check that the compose file and your current environment produce a valid resolved config before touching anything else.

```bash
make compose-config
```

This runs `docker compose config --quiet`. Any unset required variables or YAML errors surface here.

### 2b. Prepare auth proxy certificates

The auth proxy service requires a self-signed TLS certificate pair mounted at `infrastructure/data/auth_proxy/certs/`.

```bash
make compose-prepare-certs
```

This generates `tls.key` and `tls.crt` under `infrastructure/data/auth_proxy/certs/` using OpenSSL (skipped silently if the files already exist).

### 2c. Bootstrap infrastructure and run migrations

This single command wires together three steps in order:

1. Prepares the auth proxy certificates (safe to re-run).
2. Starts the infrastructure prerequisites — MongoDB, Kafka, and S3 — detached.
3. Builds and runs the `migration_job` container, which creates the MongoDB service user, runs data migrations, and initialises the S3 bucket.

```bash
make compose-bootstrap
```

Wait for the migration job to exit with code `0` before proceeding.

### 2d. Build service images

Build all application images locally. This step can take a while on first run.

```bash
docker compose build
```

Add `--parallel` to build multiple services concurrently if your machine has spare CPU/memory headroom.

---

## 3. Common Startup Examples

### Minimal UI + auth stack

Brings up just enough to reach the web UI through the Traefik reverse proxy, including the auth proxy, account service, and Dex.

```bash
docker compose up -d reverse-proxy web dex platform_account platform_auth_proxy
```

Access the UI at: `http://geti.localhost` (add `geti.localhost` → `127.0.0.1` to `/etc/hosts` if needed).

### Full stack

Start everything (infra + platform + interactive AI services):

```bash
docker compose up -d
```

To follow startup logs as services come up:

```bash
docker compose logs -f
```

---

## 4. Known Gotchas / Troubleshooting

### Auth proxy error: missing `/etc/geti-jwt-secret/tls.crt`

**Symptom:** `platform_auth_proxy` fails to start with a message like:

```
error: cannot read /etc/geti-jwt-secret/tls.crt: no such file or directory
```

**Cause:** The cert directory `infrastructure/data/auth_proxy/` was created by a previous Docker or root process and is owned by `root`, so the cert generation script cannot write into it.

**Fix:**

```bash
sudo chown -R "$USER:$USER" infrastructure/data/auth_proxy
make compose-prepare-certs
```

Then restart the auth proxy:

```bash
docker compose up -d platform_auth_proxy
```

---

### Stale cache / ENOSPC errors

If `docker compose build` fails with `no space left on device` or you see unexpected stale layers:

```bash
# Remove stopped containers and dangling images (safe)
docker container prune -f
docker image prune -f

# More aggressive: also remove unused volumes
docker volume prune -f

# Show overall disk usage before/after
docker system df
```

Avoid `docker system prune -a` unless you are happy to re-pull/rebuild all base images.

---

### Inspecting logs for a single service

```bash
# Tail logs for one service
docker compose logs -f platform_auth_proxy

# Last 100 lines, no follow
docker compose logs --tail=100 interactive_ai_jobs
```

---

## 5. Optional Checks

### Compose smoke check

Sends HTTP requests through Traefik and verifies that key routes respond (non-404):

```bash
make compose-smoke
```

The smoke script checks paths including `/`, `/dex`, `/api/v1/healthz`, and several API routes. Requires the stack to be running with Traefik on port 80.

### Compose parity acceptance

Runs the unit-test acceptance suite that enforces compose-mode behavioral contracts across the jobs service, user directory, and observability service:

```bash
make compose-parity
```

Run this after any compose-related code changes to verify that parity contracts still hold before opening a PR.

---

## 6. Notes

### Auth mode in compose

Compose runs with `AUTH_MODE=mock`. In this mode:

- Missing or invalid access tokens are replaced with a deterministic local identity (`local-admin`).
- SpiceDB permission checks return allow-all.
- Token validation in onboarding and user-directory flows is bypassed.

This is intentional for local developer velocity. **Do not run `AUTH_MODE=mock` in any environment that is network-accessible or carries real data.**

For the full parity policy, including in-scope service behavior, unsupported-behavior contracts, and CI enforcement details, see:

```
docs/compose-parity-policy.md
```
