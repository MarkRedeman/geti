# Geti Compose Docs

This directory is intentionally small and contains focused compose references:

- `docs/compose/README.md` (this file): what changed and current compose architecture.
- `docs/compose/getting-started-with-compose.md`: practical setup, bootstrap, and verification steps.
- `docs/compose/troubleshooting.md`: common compose failure modes and fixes.
- `docs/compose/refactor-platform-services.md`: compose-first platform service reduction plan and implementation status.

## What changed

Compose has been simplified around a unified local runtime path:

- One-time bootstrap is handled by `geti_init` (Kafka topics, Mongo service user, migrations, S3 buckets, initial user, LDAP reconciliation, cert prep).
- API consolidation moved multiple Interactive AI HTTP services into `interactive_ai_api`.
- Jobs run through compose-native scheduler + Celery worker flow (no local Flyte requirement).
- Model registration/inference is wired for compose with OVMS-backed serving.
- Visual prompt uses SAM artifacts from the `pretrainedweights` bucket.

## Current service model (high level)

- `interactive_ai_api`: unified HTTP API surface (director/resource/jobs REST/import-export).
- `interactive_ai_jobs_scheduler` + `interactive_ai_jobs_worker`: orchestration and job execution.
- `interactive_ai_inference_gateway` + `ovms`: inference path.
- `interactive_ai_visual_prompt`: visual prompt endpoint (`...:prompt`) using SAM models.
- `geti_init`: bootstrap job; run before full stack startup.

## Platform service surface (compose)

- Runtime platform services are reduced to `platform_account` only.
- Forward-auth (`/api/v1/auth`) and cookie/JWKS endpoints (`/api/v1/set_cookie`, `/api/v1/keys/`) now run inside `platform_account`.
- User lifecycle endpoints previously served by `platform_user_directory` now run inside `platform_account`.
- Bootstrap-only responsibilities (initial user setup and pretrained weight seeding) are handled by `geti_init`.

## Weights and model artifacts

There are two related artifact categories:

1. Pretrained training weights (used by train/optimize pipelines).
2. Visual prompt SAM encoder/decoder artifacts (`sam_vit_b_zsl_*`).

Both are expected in S3 bucket `pretrainedweights` and are seeded by bootstrap by default.

## Local auth mode

- Default/preferred compose path uses real Dex/LDAP auth flow.
- `AUTH_MODE=mock` is optional and should be used only for local troubleshooting or shortcut flows.

## Operational guidance

- Start with `make compose-bootstrap` on clean or updated environments.
- Use `make compose-smoke` after startup to validate key routes.
- Use `docker compose logs -f <service>` for first-failure diagnosis.

## Scope of these docs

Historic migration notes, investigations, and one-off reports were removed to reduce maintenance cost.
If deeper architectural records are needed later, they should be reintroduced in a dedicated architecture/history location rather than under compose getting-started docs.
