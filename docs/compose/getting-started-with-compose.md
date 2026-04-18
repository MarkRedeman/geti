# Getting Started with Geti on Docker Compose

This is the practical setup guide for local compose usage.

## 1) Prerequisites

- Docker Engine + Docker Compose v2
- OpenSSL
- Enough disk space for images and runtime data (20-30 GB recommended minimum)

Quick checks:

```bash
docker version
docker compose version
openssl version
```

## 2) Configure environment

From repo root, ensure your `.env` exists and has local compose values.

At minimum, keep these aligned for bootstrap:

- `DEPLOYMENT_MODE=compose`
- `INITIAL_USER_EMAIL=admin@geti.local`
- `INITIAL_USER_PASSWORD=<your-password>`

Auth mode guidance:

- Prefer real auth flow (Dex/LDAP): leave `AUTH_MODE` unset.
- Use `AUTH_MODE=mock` only for local troubleshooting/dev shortcuts.
- `MOCK_*` variables are only used when `AUTH_MODE=mock`.

If using Intel XPU trainer runtime:

```bash
TRAINER_RUNTIME_ACCELERATOR=xpu
TRAINER_RUNTIME_XPU_DEVICES=/dev/dri
```

## 3) Validate compose config

```bash
make compose-config
```

This catches missing env vars and compose wiring errors early.

## 4) Bootstrap the platform

Run the unified init flow:

```bash
make compose-bootstrap
```

What bootstrap does (`geti_init`):

- prepares auth proxy certs and Dex sqlite path
- creates Kafka topics
- creates Mongo service user and runs migrations
- initializes required S3 buckets
- seeds initial user/org/workspace and LDAP group/password state
- seeds pretrained artifacts into `pretrainedweights` (enabled by default)

For a full clean re-bootstrap:

```bash
make compose-bootstrap-reset
```

To disable seeding for faster iteration:

```bash
bash infrastructure/compose-bootstrap.sh --no-seed-weights
```

## 5) Build and start services

Build:

```bash
docker compose build
```

Start full stack:

```bash
docker compose up -d
```

Follow logs when needed:

```bash
docker compose logs -f
```

## 6) Access and verify

- UI: `https://geti.localhost` (HTTP redirects to HTTPS)
- If needed, map `geti.localhost` to `127.0.0.1` in `/etc/hosts`

Run smoke checks through Traefik:

```bash
make compose-smoke
```

Optional parity/unit acceptance suite:

```bash
make compose-parity
```

## 7) Model and weights notes

### Training/optimization weights

Training first checks bucket `pretrainedweights` and then optional external fallback URL.
If your network cannot reach external weight URLs, keep bucket seeding enabled.

### Visual prompt (SAM)

`interactive_ai_visual_prompt` requires these keys in bucket `pretrainedweights`:

- `sam_vit_b_zsl_encoder.xml`
- `sam_vit_b_zsl_encoder.bin`
- `sam_vit_b_zsl_decoder.xml`
- `sam_vit_b_zsl_decoder.bin`

If these are missing or invalid, prompt endpoint requests fail.

## 8) Troubleshooting quick paths

Check service state:

```bash
docker compose ps
```

Inspect logs for one service:

```bash
docker compose logs --tail=200 <service>
```

Common first checks:

- bootstrap completed successfully (`geti_init` exited with code 0)
- `interactive_ai_api`, `interactive_ai_jobs_scheduler`, `interactive_ai_jobs_worker`, `interactive_ai_inference_gateway`, `ovms` are running
- `interactive_ai_visual_prompt` is running when using `...:prompt`

If storage or certificate files were created by root on host bind mounts, fix ownership and rerun bootstrap.
