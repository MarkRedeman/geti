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

The script also normalizes permissions to world-readable (`0644`) because the
distroless `platform_auth_proxy` container runs as non-root and must be able to
read the mounted key/cert files.

### 2c. Bootstrap infrastructure, migrations, and pretrained weights

This command wires together four steps in order:

1. Prepares the auth proxy certificates (safe to re-run).
2. Starts the infrastructure prerequisites — MongoDB, Kafka, and S3 — detached.
3. Builds and runs the `migration_job` container, which creates the MongoDB service user, runs data migrations, and initialises the S3 bucket.
4. Runs pretrained weights upload (`platform/services/weights_uploader`) into S3 bucket `pretrainedweights`.

`compose-bootstrap` now waits for SeaweedFS S3 readiness before launching
`migration_job`, to avoid intermittent `Connection refused` failures on fresh
resets.

After `platform_initial_user` runs, bootstrap also synchronizes the LDAP user
password to `INITIAL_USER_PASSWORD` from `.env` to ensure Dex LDAP login works
immediately after a clean reset.

Bootstrap also ensures Dex-compatible LDAP groups exist (`ou=Groups` and
`cn=regular_users`) and adds the initial user UID as `memberUid`.

```bash
make compose-bootstrap
```

Weights uploader notes:

- `make compose-bootstrap` seeds weights by default.
- Requires `uv` installed on the host (bootstrap fails if `uv` is missing and seeding is enabled).
- Uses local S3 endpoint `127.0.0.1:8333` and `.env` credentials (`S3_ACCESS_KEY` / `S3_SECRET_KEY`).
- Optional overrides:
  - `WEIGHTS_URL` (defaults to `https://storage.geti.intel.com/weights`)
  - `COMPOSE_BOOTSTRAP_WEIGHTS_DIR` (defaults to `/tmp/geti-pretrained-weights`)
  - `COMPOSE_BOOTSTRAP_WEIGHTS_CONFIG_DIR` (defaults to `app/pretrained_models`)
  - `COMPOSE_BOOTSTRAP_DISABLE_WEIGHT_UPLOADING=1` (upload only metadata, skip downloading weight binaries)

To skip weight seeding (for quick bring-up):

```bash
bash infrastructure/compose-bootstrap.sh --no-seed-weights
```

To re-run bootstrap with weight seeding explicitly enabled:

```bash
make compose-bootstrap-seed-weights
```

(`make compose-bootstrap-seed-weights` maps to `bash infrastructure/compose-bootstrap.sh --seed-weights`.)

Wait for the migration job to exit with code `0` before proceeding.

`make compose-bootstrap` now also runs the initial user/org/workspace seed step
(`platform_initial_user`) by default.

> `Aborting on container exit...` after `migration_job` finishes is expected in
> this flow, because bootstrap runs compose with `--abort-on-container-exit`.
> Treat the bootstrap as successful when you see:
>
> - `migration_job-1 exited with code 0`
> - `Compose bootstrap completed.`

> If bootstrap fails with `S3_CREDENTIALS_PROVIDER` or a host lookup for
> `impt-seaweed-fs`, update to the latest `docker-compose.yaml` from this
> branch and re-run `make compose-bootstrap`.

For a full clean re-bootstrap (drop compose volumes + reset Dex DB + re-migrate
+ re-seed), run:

```bash
make compose-bootstrap-reset
```

### 2d. Build service images

Build all application images locally. This step can take a while on first run.

```bash
docker compose build
```

Add `--parallel` to build multiple services concurrently if your machine has spare CPU/memory headroom.

### 2e. Optional: reduce Kafka memory footprint for local/dev

Compose now supports explicit Kafka heap tuning via `.env`:

```bash
KAFKA_HEAP_OPTS=-Xms256m -Xmx512m
```

Recommended starting values:

- default local/dev: `-Xms256m -Xmx512m`
- constrained laptop: `-Xms128m -Xmx384m`
- heavier local throughput: `-Xms512m -Xmx1g`

Apply changes by recreating Kafka:

```bash
docker compose up -d --force-recreate kafka init-kafka-topics
```

---

## 3. Common Startup Examples

Recommended progression for first bring-up (service-by-service):

1. `reverse-proxy + web + dex + platform_account + platform_auth_proxy`
2. Add user and onboarding APIs:
   - `platform_user_directory`, `platform_onboarding`, `platform_initial_user`
3. Add interactive AI control plane:
   - `interactive_ai_jobs_scheduler`, `interactive_ai_jobs_worker`,
     `interactive_ai_jobs_policy`, `interactive_ai_model_registration`, `ovms`
4. Add remaining interactive AI APIs/workers:
   - `interactive_ai_api`, `interactive_ai_inference_gateway`,
     `interactive_ai_visual_prompt`, `interactive_ai_media`, `interactive_ai_auto_train`
5. Add workflow and trainer images/services only when needed:
   - `interactive_ai_workflows_*`, `interactive_ai_workflows_otx_v2_*`, `otx`

Use this for each step:

```bash
# start selected services detached
docker compose up -d <service...>

# inspect current service health/status
docker compose ps

# inspect logs for failing service(s)
docker compose logs --tail=200 <service>
```

If a service fails, fix that service before moving to the next step.

### Minimal UI + auth stack

Brings up just enough to reach the web UI through the Traefik reverse proxy, including the auth proxy, account service, and Dex.

```bash
docker compose up -d reverse-proxy web dex platform_account platform_auth_proxy
```

Access the UI at: `http://geti.localhost` (add `geti.localhost` → `127.0.0.1` to `/etc/hosts` if needed).

### Full stack

Start everything (infra + platform + interactive AI services):

```bash
docker compose up reverse-proxy web dex platform_account platform_auth_proxy interactive_ai_director interactive_ai_resource interactive_ai_jobs interactive_ai_media interactive_ai_auto_train interactive_ai_dataset_import_export interactive_ai_project_import_export interactive_ai_model_registration interactive_ai_inference_gateway ovms interactive_ai_jobs_policy interactive_ai_jobs_worker interactive_ai_jobs_scheduler
```

Recommended unified API variant:

```bash
docker compose up reverse-proxy web dex platform_account platform_auth_proxy interactive_ai_api interactive_ai_media interactive_ai_auto_train interactive_ai_model_registration interactive_ai_inference_gateway ovms interactive_ai_jobs_policy interactive_ai_jobs_worker interactive_ai_jobs_scheduler
```



```bash
docker compose up -d
```

To follow startup logs as services come up:

```bash
docker compose logs -f
```

---

## 4. Known Gotchas / Troubleshooting

### Selecting trainer accelerator (NVIDIA GPU vs Intel XPU)

Compose training now supports selecting the trainer runtime image via env vars used by `interactive_ai_jobs_worker`.

Relevant vars:

- `TRAINER_RUNTIME_ACCELERATOR` — `gpu` (default) or `xpu`
- `TRAINER_RUNTIME_IMAGE` — NVIDIA trainer image (`otx_v2_gpu`)
- `TRAINER_RUNTIME_XPU_IMAGE` — Intel XPU trainer image (`otx_v2_xpu`)
- `TRAINER_RUNTIME_XPU_DEVICES` — device mounts for XPU mode (default: `/dev/dri`)

Example (`.env`) for Intel XPU mode:

```bash
TRAINER_RUNTIME_ACCELERATOR=xpu
TRAINER_RUNTIME_XPU_DEVICES=/dev/dri
```

Then recreate the jobs worker:

```bash
docker compose up -d --force-recreate interactive_ai_jobs_worker
```

Notes:

- In `gpu` mode, trainer containers are launched with `--gpus`.
- In `xpu` mode, trainer containers are launched with `--device` mappings from `TRAINER_RUNTIME_XPU_DEVICES`.
- This choice is currently environment-based (global for the worker). Per-job accelerator selection can be added later.

### Jobs scheduler timeouts in compose (recommended: long timeouts)

In compose mode, `interactive_ai_jobs_scheduler` waits for Celery task completion
using a timeout. If this timeout is too short, jobs can be marked failed while
they are still queued behind long-running tasks (for example, training).

Current compose defaults are intentionally long:

- `LOCAL_EXECUTOR_DEFAULT_TIMEOUT_SEC=7200` (2 hours)
- `LOCAL_EXECUTOR_TRAIN_TIMEOUT_SEC=7200` (2 hours)
- `LOCAL_EXECUTOR_OPTIMIZE_TIMEOUT_SEC=3600` (1 hour)

You can override these in `.env`:

```bash
LOCAL_EXECUTOR_DEFAULT_TIMEOUT_SEC=14400
LOCAL_EXECUTOR_TRAIN_TIMEOUT_SEC=14400
LOCAL_EXECUTOR_OPTIMIZE_TIMEOUT_SEC=7200
```

Apply timeout changes by recreating scheduler (and usually worker):

```bash
docker compose up -d --build interactive_ai_jobs_scheduler interactive_ai_jobs_worker
```

### Training fails because pretrained weights cannot be downloaded

On fresh systems, training can fail if pretrained weights are not available in the `pretrainedweights` bucket and the trainer cannot reach the weights URL.

Typical symptom in trainer logs:

```text
Failed to download ... from https://storage.geti.intel.com/weights/...
```

How it works in compose:

1. The bootstrap weights uploader populates S3 bucket `pretrainedweights`.
2. During training, the trainer first tries that S3 bucket.
3. If missing, it falls back to `WEIGHTS_URL`.

> Important: current compose jobs worker code passes `WEIGHTS_URL=https://storage.geti.intel.com/weights` to trainer runtime by default. On restricted networks, this fallback will fail unless you provide internet/proxy access or pre-populate the bucket.

Recommended checks/fixes:

```bash
# 1) Make sure bootstrap/migration+weights completed successfully
make compose-bootstrap

# 2) Check jobs worker logs for weights/download errors
docker compose logs --tail=300 interactive_ai_jobs_worker

# 3) Check trainer/workflow logs while a train job runs
docker compose logs --tail=300 interactive_ai_workflows_train
```

If your environment is restricted:

- Prefer pre-populating `pretrainedweights` (internal mirror / offline seed), so training does not need external fallback.
- If you use proxies, ensure compose services have the required proxy environment (`HTTPS_PROXY`/`NO_PROXY`, etc.) and that weight hosts are reachable.
- If you maintain an internal mirror, use a mirror URL as your weights source and keep expected filenames identical to upstream basenames.

#### Pre-populating `pretrainedweights` bucket (compose)

Preferred path (simplest): run bootstrap with default weight seeding enabled.

```bash
make compose-bootstrap
```

If you skipped seeding during bootstrap or want to re-seed later:

```bash
make compose-bootstrap-seed-weights
```

If you want to run only the uploader itself (without re-running full bootstrap), use the direct uploader command below.

Equivalent direct command:

```bash
S3_HOST=127.0.0.1:8333 \
S3_ACCESS_KEY=dummy \
S3_SECRET_KEY=dummy \
WEIGHTS_DIR=/tmp/geti-pretrained-weights \
WEIGHTS_URL=https://storage.geti.intel.com/weights \
CONFIG_DIR=app/pretrained_models \
uv run --directory "platform/services/weights_uploader" python app/weights_uploader.py
```

If internet access to `WEIGHTS_URL` is blocked, seed metadata only:

```bash
COMPOSE_BOOTSTRAP_DISABLE_WEIGHT_UPLOADING=1 make compose-bootstrap-seed-weights
```

### Which startup path should I use?

- **Normal training/optimization path:** run `make compose-bootstrap` and keep weight seeding enabled (default). This ensures trainer fallback artifacts are available in `pretrainedweights`.
- **Visual prompt path:** also requires weight seeding, because `interactive_ai_visual_prompt` loads SAM files from `pretrainedweights` at startup (`sam_vit_b_zsl_encoder/decoder` xml+bin). If these objects are missing, the service fails to start and prompt API requests return `502`.

Verify metadata exists in S3:

```bash
python - <<'PY'
import boto3
s3 = boto3.client(
    "s3",
    endpoint_url="http://127.0.0.1:8333",
    aws_access_key_id="dummy",
    aws_secret_access_key="dummy",
)
print(s3.head_object(Bucket="pretrainedweights", Key="pretrained_models_v2.json")["ContentLength"])
PY
```

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

### Migration job fails with S3 credential/provider or host resolution errors

**Symptoms during `make compose-bootstrap`:**

- `Environment variable S3_CREDENTIALS_PROVIDER should be set to either 'local' or 'aws'`
- `HTTPConnectionPool(host='impt-seaweed-fs', port=8333) ... Failed to resolve`

**Cause:** `migration_job` did not receive compose-local S3 settings.

**Expected compose env for `migration_job`:**

```yaml
S3_CREDENTIALS_PROVIDER: local
S3_HOST: s3:8333
```

**Fix:** ensure your `docker-compose.yaml` includes those variables under
`migration_job.environment`, then rerun:

```bash
make compose-bootstrap
```

---

### Inspecting logs for a single service

```bash
# Tail logs for one service
docker compose logs -f platform_auth_proxy

# Last 100 lines, no follow
docker compose logs --tail=100 interactive_ai_jobs
```

---

### Account startup log: `object definition 'user_directory' not found`

**Symptom while starting UI/auth stack:**

```text
unable to migrate user_directory: ... object definition `user_directory` not found
```

**Status:** expected, non-fatal in current compose flow.

`platform_account` writes the active SpiceDB schema at startup. The
`user_directory` migration check runs first and can log this warning on a fresh
or already-updated schema, then startup continues normally.

Treat this as healthy if `platform_account` still logs:

- `grpc server listening at [::]:5001`
- `grpc gateway server listening at :5002`

Quick check:

```bash
docker compose ps platform_account
docker compose logs --tail=100 platform_account
```

---

### Dex login works but `/api/v1/profile` returns `User not found`

If authentication succeeds but `/api/v1/profile` still returns a 404-like
`User not found`, ensure identity bootstrap values are aligned:

- `.env`:
  - `INITIAL_USER_EMAIL=admin@geti.local`
  - `DEX_STATIC_USER_ID=admin@geti.local`
- `infrastructure/data/dex/config.yml` static password entry:
  - `email: "admin@geti.local"`
  - `userID: "admin@geti.local"`

Then recreate Dex and rerun initial-user bootstrap:

```bash
docker compose up -d --force-recreate dex platform_initial_user
docker compose logs --tail=200 platform_initial_user
```

Ensure SpiceDB credentials use token mode in compose:

```bash
SPICEDB_CREDENTIALS=token
```

If `platform_initial_user` exits with `StatusCode.UNAVAILABLE` mentioning
`Endpoint is neither UDS or TCP loopback address`, verify
`SPICEDB_CREDENTIALS=token` for compose services.

> Note: if Dex is configured with `mockCallback`, it always authenticates as a
> fixed demo identity (`kilgore@kilgore.trout`) for `/auth/regular_users` and
> ignores `staticPasswords` for that browser flow. Use the LDAP connector if
> you need login identity to match seeded `INITIAL_USER_EMAIL`.

### Dex login error: `LDAP Result Code 32 "No Such Object"` while querying groups

This means Dex is searching groups under an LDAP base DN that does not exist.
In this compose setup, OpenLDAP does not create `ou=Groups,dc=example,dc=org`
by default.

Use this in `infrastructure/data/dex/config.yml`:

```yaml
connectors:
- id: regular_users
  type: ldap
  config:
    # ...
    groupSearch:
      baseDN: dc=example,dc=org
      filter: "(objectClass=posixGroup)"
      userMatchers:
        - userAttr: uid
          groupAttr: memberuid
      nameAttr: cn
```

Then recreate Dex:

```bash
docker compose up -d --force-recreate dex
```

If login still fails, clear browser cookies for `geti.localhost` and retry.

---

### Dex auth URL returns 404 + Traefik logs `unable to find the IP address for /geti-dex-1`

If Dex is crash-looping, Traefik cannot route `/dex/*` and you may see 404s.

Common root causes and fixes:

1) **Dex sqlite path in config is relative**

`infrastructure/data/dex/config.yml` must use an absolute in-container path:

```yaml
storage:
  type: sqlite3
  config:
    file: /var/dex/dex.db
```

2) **Host bind target became directory or is not writable**

Dex requires `infrastructure/data/dex/dex.db` to be a writable file.

```bash
rm -rf infrastructure/data/dex/dex.db
touch infrastructure/data/dex/dex.db
chmod 666 infrastructure/data/dex/dex.db
docker compose up -d --force-recreate dex reverse-proxy
```

3) **Use bootstrap helper (now normalizes Dex DB path automatically)**

```bash
make compose-bootstrap-reset
```

Health check commands:

```bash
docker compose ps dex reverse-proxy
docker compose logs --tail=100 dex reverse-proxy
curl -i -H "Host: geti.localhost" http://127.0.0.1/dex/.well-known/openid-configuration
```

Expected: Dex `Up`, OIDC config returns `HTTP/1.1 200`.

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

For the full parity policy, including in-scope service behavior, unsupported-behavior contracts, and CI enforcement details, see:

```
docs/compose-parity-policy.md
```
