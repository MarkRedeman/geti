# Combine Interactive AI API Services (Compose Plan)

Inventory + migration todo list for consolidating Python services that currently run from the shared image:

- Image: `${REGISTRY-ghcr.io/geti}/interactive_ai/api:${TAG-main}`
- Dockerfile: `interactive_ai/services/Dockerfile.api`

Proposed direction:

- Add a new service entrypoint at `interactive_ai/services/main.py`
- Add compose service `interactive_ai_api`
- Move each existing HTTP API service `main.py` into the unified API process one-by-one

---

## 1) Current inventory (services using shared API image)

## HTTP API services (primary consolidation candidates)

1. `interactive_ai_resource`
   - Working dir: `/interactive_ai/services/resource/app/communication`
   - Command: `python main.py`
   - Port/route: Traefik -> service port `5000`

2. `interactive_ai_director`
   - Working dir: `/interactive_ai/services/director/app/communication`
   - Command: `python main.py`
   - Port/route: Traefik -> service port `4999`

3. `interactive_ai_dataset_import_export`
   - Working dir: `/interactive_ai/services/dataset_ie/communication/endpoints`
   - Command: `python main.py`
   - Port/route: Traefik -> service port `8000`

4. `interactive_ai_project_import_export`
   - Working dir: `/interactive_ai/services/project_ie/communication/endpoints`
   - Command: `python main.py`
   - Port/route: Traefik -> service port `8000`

5. `interactive_ai_jobs` (REST)
   - Working dir: `/interactive_ai/services/jobs`
   - Command: `python microservice/rest/main.py`
   - Port/route: Traefik -> service port `8000`

6. `interactive_ai_visual_prompt` (**deferred**)
   - Working dir: `/interactive_ai/services/visual_prompt/services`
   - Command: `python main.py`
   - Port/route: Traefik -> service port `8000`

## Non-HTTP/shared-image services (likely keep separate)

7. `interactive_ai_auto_train`
   - Kafka/background process (`python main.py`), no Traefik route

8. `interactive_ai_jobs_scheduler`
   - Scheduler loop (`python scheduler/main.py`), no Traefik route

9. `interactive_ai_jobs_worker`
   - Celery worker (`python -m celery ...`), no Traefik route

10. `interactive_ai_jobs_policy`
    - Policy loop (`python policies/main.py`), no Traefik route

11. `interactive_ai_model_registration` (**migrated into `interactive_ai_api`**)
    - Internal gRPC service now started by unified API lifespan

> Recommendation: first consolidate **HTTP APIs only**, but defer `visual_prompt` initially due to its heavyweight model-loading/inference lifecycle. Keep worker/scheduler/policy/background services split unless we intentionally redesign process supervision.

---

## 2) Files/directories relevant to consolidation

- Shared image build: `interactive_ai/services/Dockerfile.api`
- Service roots:
  - `interactive_ai/services/resource/`
  - `interactive_ai/services/director/`
  - `interactive_ai/services/dataset_ie/`
  - `interactive_ai/services/project_ie/`
  - `interactive_ai/services/jobs/`
  - `interactive_ai/services/visual_prompt/`
- Compose wiring: `docker-compose.yaml`

Current `Dockerfile.api` already copies all required app code for these services into the same image.

---

## 3) Target architecture (phased)

Goal: one runtime service `interactive_ai_api` hosts multiple route groups previously served by multiple containers.

Candidate approach:

- `interactive_ai/services/main.py` becomes a router/composition entrypoint.
- It imports and mounts/adapts each service app in phases.
- Traefik routes currently pointing to per-service containers are redirected to `interactive_ai_api`.

---

## 4) Migration todo checklist

## Phase 0 — Preparation

- [x] Create `interactive_ai/services/main.py` scaffold.
- [ ] Decide composition mechanism:
  - [x] Single ASGI app mounting sub-apps
  - [ ] Reverse-proxy-internal style forwarding in-process
  - [ ] Hybrid (preferred only if needed for compatibility)
- [x] Define unified runtime port for `interactive_ai_api` (e.g. `8000`).
- [x] Add new compose service `interactive_ai_api` with shared env baseline (`*iai-runtime-env`).
- [x] Add smoke route `/api/v1/healthz` on unified service.

## Phase 1 — Migrate dataset import/export

- [x] Migrate `dataset_import_export` routes to `interactive_ai_api`.
- [x] Update Traefik labels to target `interactive-ai-api` backend.
- [x] Verify service startup and endpoint registration in unified API.
- [ ] Verify dataset upload/resumable/import/export flows.

## Phase 2 — Migrate project import/export

- [x] Migrate `project_import_export` routes to `interactive_ai_api`.
- [x] Update Traefik labels to target `interactive-ai-api` backend.
- [x] Verify service startup and endpoint registration in unified API.
- [ ] Verify project upload/resumable/import/export flows.

## Phase 3 — Migrate jobs REST API

- [x] Move `interactive_ai_jobs` REST endpoints into unified API process.
- [x] Keep `jobs_worker`, `jobs_scheduler`, `jobs_policy` as separate services.
- [x] Verify service startup and endpoint registration in unified API.
- [ ] Verify job create/list/get/cancel flows.

## Phase 4 — Migrate director (higher risk)

- [x] Move director routes.
- [x] Validate service startup and endpoint registration in unified API.
- [ ] Validate training/optimize trigger + prediction flows.
- [x] Validate inter-service addresses/envs that previously used container DNS names.

## Phase 5 — Migrate resource (higher risk)

- [x] Move resource routes.
- [x] Validate service startup and endpoint registration in unified API.
- [ ] Validate project lifecycle + resource/media/test-results flows.
- [x] Validate inter-service addresses/envs that previously used container DNS names.

## Phase 6 — Cleanup

- [x] Remove deprecated per-API compose services after parity verification.
- [x] Remove obsolete env vars / `PYTHONPATH` entries tied to removed services.
- [x] Update `docs/compose/getting-started-with-compose.md` startup commands.
- [x] Update smoke checks for unified service topology (no path changes required; checks already route through unified API).

## Deferred phase — Visual prompt

- [ ] Mount `visual_prompt` endpoints in unified API.
- [ ] Ensure startup deps still work (SAM models in `pretrainedweights`).
- [ ] Verify `pipelines/*:prompt` end-to-end.
- [ ] Validate unified API startup latency and memory impact with VP enabled.

---

## 5) Validation checklist per migrated service

- [ ] Route parity: old path regexes still reachable.
- [ ] Auth parity: `geti-auth@docker` middleware unchanged.
- [ ] Health checks: service starts cleanly and remains healthy.
- [ ] Logs/telemetry: request tracing and error reporting still present.
- [ ] Performance: no major startup regressions or timeout regressions.

---

## 6) Risks to track

- Different services currently bind to different internal ports (`4999`, `5000`, `8000`).
- Startup side effects (Kafka consumers/background threads) may trigger unintentionally when importing old `main.py` modules.
- Environment collisions (same var names, different assumptions across services).
- Large blast radius when combining high-traffic APIs (resource + director + jobs REST).

Mitigation: migrate in small phases and keep rollback by retaining old compose services until each phase is validated.
