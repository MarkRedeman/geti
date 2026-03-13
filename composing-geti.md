# Composing Geti: Kubernetes/Flyte → Docker Compose Migration Plan + Execution Checklist

## Goal

Make Docker Compose the default local platform path and remove the requirement for local Kubernetes/Flyte.

Constraints/decisions for this migration branch:

- We are already on the migration branch.
- OIDC / SpiceDB / authentication can be mocked for local Compose mode.
- In mocked auth mode, any user/action is allowed.
- For features still tied to Kubernetes/Flyte, fail fast with explicit server logs and clear 5xx responses until implemented.

---

## Scope & Outcomes

### In scope

1. Stable Compose infra + service wiring.
2. Local mocked auth/authz mode.
3. Explicit identification of K8s/Flyte-dependent code paths.
4. MongoDB bootstrap/init approach for shared-database microservices.
5. Phased execution checklist with acceptance criteria.

### Out of scope (initial cut)

- Full parity with production Kubernetes/Flyte behavior.
- Production security posture in local dev mode.

---

## High-Level Migration Strategy

1. **Foundation first**: make compose deterministic (env, networks, dependencies, volumes, healthchecks).
2. **Mock auth early**: decouple from OIDC/SpiceDB to unblock local development.
3. **Preserve API contracts**: where features are unavailable, return clear “not yet supported in compose mode” errors.
4. **Replace Kubernetes/Flyte in phases**: KServe/model serving, then jobs orchestration.

---

## Known Compose Gaps to Address First

1. Runtime `.env` values are incomplete.
2. Root compose currently defines many app services as build-only (missing runtime env and dependency wiring).
3. Missing mounted config files/dirs (Dex/Authelia).
4. MongoDB missing from root compose while many services depend on it.
5. Misconfigured labels/credentials/persistence in current compose setup.

---

## Local Auth/Authz Mocking Plan (Compose Mode)

For local compose profile, prefer a single switch (example: `AUTH_MODE=mock` or `COMPOSE_LOCAL_AUTH_BYPASS=true`) and implement behavior:

1. **Identity bypass**
   - If access token header is missing/invalid in mock mode, inject a deterministic local user (example `local-admin`) instead of rejecting request.
2. **Authorization bypass**
   - SpiceDB permission checks return allow in mock mode.
3. **Service-level guardrails**
   - Log warning once at service startup and per protected endpoint category:
     - `"[MOCK AUTH] Authorization bypass enabled. Do not use in production."`
4. **Containment**
   - Keep bypass paths behind explicit env flags and compose profile.

---

## Application Code That Requires Kubernetes/Flyte (file-level map)

Use this section as the implementation backlog for “comment out / feature gate / log & fail” in compose mode.

### A) Jobs service + Flyte scheduling coupling

- `interactive_ai/services/jobs/app/scheduler/flyte.py`  
  FlyteRemote client, execution submission/cancel/fetch.
- `interactive_ai/services/jobs/app/scheduler/loops/scheduling.py`  
  Scheduling loop starts Flyte executions.
- `interactive_ai/services/jobs/app/scheduler/loops/revert_scheduling.py`  
  Rollback scheduling via Flyte execution path.
- `interactive_ai/services/jobs/app/scheduler/loops/cancellation.py`  
  Cancellation logic tied to Flyte execution model.
- `interactive_ai/services/jobs/app/scheduler/kafka_handler.py`  
  Maps Kafka workflow events to Flyte execution state transitions.

### B) Flyte workflow definitions (job domains)

- `interactive_ai/workflows/train/job/workflows/train_workflow.py`
- `interactive_ai/workflows/model_test/job/workflows/model_test_workflow.py`
- `interactive_ai/workflows/optimize/job/workflows/optimize_workflow.py`
- `interactive_ai/workflows/dataset_ie/job/workflows/import_workflows.py`
- `interactive_ai/workflows/dataset_ie/job/workflows/export_workflow.py`
- `interactive_ai/workflows/project_ie/job/workflows/export_project_workflow.py`
- `interactive_ai/workflows/project_ie/job/workflows/import_project_workflow.py`

### C) K8s PodSpec / Flyte task runtime coupling

- `interactive_ai/workflows/common/jobs_common/tasks/primary_container_task.py`  
  K8s PodSpec creation, ConfigMap/Secret env injection, Istio assumptions.
- `interactive_ai/workflows/common/jobs_common/k8s_helpers/trainer_pod_definition.py`  
  Trainer pod/container definitions with K8s objects.
- `interactive_ai/workflows/common/jobs_common/k8s_helpers/trainer_image_info.py`  
  K8s ConfigMap reads for trainer image tags.
- `interactive_ai/workflows/common/jobs_common/k8s_helpers/k8s_resources_calculation.py`  
  Node resource calculations from K8s cluster data.

### D) Flyte secret/context coupling

- `interactive_ai/workflows/common/jobs_common/tasks/utils/secrets.py`
- `interactive_ai/workflows/project_ie/job/tasks/secrets.py`

### E) Shared K8s utility library coupling

- `libs/k8s_tools/src/geti_k8s_tools/calculate_cluster_resources.py`
- `libs/k8s_tools/src/geti_k8s_tools/k8s_api_client.py`
- `interactive_ai/services/jobs/app/policies/resource_manager.py`

### F) KServe / K8s CRD model-registration coupling

- `interactive_ai/services/model_registration/app/service/custom_resource.py`

### G) Platform services with K8s client dependencies

- `platform/services/installer/app/platform_utils/kube_config_handler.py`
- `platform/services/installer/app/platform_utils/management/management.py`
- `platform/services/installer/app/platform_utils/k8s.py`
- `platform/services/installer/app/checks/k8s.py`
- `platform/services/installer/app/constants/paths.py`
- `platform/services/user_directory/app/service_connection/k8s_client/apis.py`
- `platform/services/user_directory/app/service_connection/k8s_client/secrets.py`
- `platform/services/user_directory/app/service_connection/k8s_client/config_maps.py`
- `platform/services/observability/app/service_connection/k8s_client/apis.py`
- `platform/services/platform_cleaner/app/platform_cleaner.py`

### H) OIDC / auth / SpiceDB enforcement paths (for local bypass)

- `libs/fastapi_tools/src/geti_fastapi_tools/identity.py`
- `libs/fastapi_tools/src/geti_fastapi_tools/dependencies.py`
- `libs/fastapi_tools/src/geti_fastapi_tools/exceptions.py`
- `platform/services/onboarding/app/jwt_utils.py`
- `platform/services/onboarding/app/routers/onboarding.py`
- `platform/services/user_directory/app/common/jwt_token_validation.py`
- `platform/services/user_directory/app/common/users.py`
- `platform/libs/users_handler/users_handler/users_handler.py`
- `libs/spicedb_tools/src/geti_spicedb_tools/spicedb.py`
- `libs/spicedb_tools/src/geti_spicedb_tools/enums.py`
- `interactive_ai/services/resource/app/managers/project_manager.py`
- `interactive_ai/services/jobs/app/microservice/rest/job_controller.py`
- `interactive_ai/services/jobs/app/microservice/grpc_api/grpc_job_service.py`
- `interactive_ai/services/jobs/app/microservice/job_manager.py`
- `interactive_ai/services/jobs/app/scheduler/state_machine.py`
- `interactive_ai/workflows/project_ie/job/usecases/project_import_usecase.py`
- `interactive_ai/workflows/dataset_ie/job/tasks/import_tasks/create_project_from_dataset.py`
- `platform/services/initial_user/app/create_initial_user.py`
- `platform/services/initial_user/app/users_handler_client.py`
- `platform/services/initial_user/app/create_org_relation.py`
- `platform/services/initial_user/app/run_migration.py`
- `platform/services/initial_user/app/postgresql_client.py`

---

## “Fail Fast + Clear Logs” Behavior for Not-Yet-Migrated Areas

For each K8s/Flyte-coupled module above, add compose-mode guard clauses:

1. Detect compose mode (env flag).
2. Emit structured error log including:
   - module/function,
   - requested operation,
   - reason ("requires kubernetes/flyte"),
   - migration hint/ticket reference.
3. Return explicit API/server error:
   - HTTP: `501 Not Implemented` (preferred) or `503 Service Unavailable`.
   - gRPC: equivalent unimplemented/unavailable status.

Suggested message template:

`"Feature unavailable in compose mode: <operation>. This path currently requires Kubernetes/Flyte."`

---

## MongoDB Initialization Plan (Shared DB Across Microservices)

Most microservices share one MongoDB logical database (`MONGODB_DATABASE_NAME`, default `geti`) through shared `MongoConnector`.

### Canonical initialization flow

1. **Start MongoDB container** with persistent volume.
2. **Create service DB user** via migration job utility:
   - `interactive_ai/migration_job/migration_job/mongodb_create_service_user.py`
3. **Run data migrations**:
   - `interactive_ai/migration_job/migration_job/run_migration.py`
   - migration history tracked in `migration_history`.
4. **Run S3 bootstrap** needed by data flows:
   - `interactive_ai/migration_job/migration_job/create_s3_bucket.py`
5. **Then start application services**.

### Why this works with shared DB

- Shared schemas/indexes are versioned through the migration system.
- Repo-level indexes are lazily created on first collection access (via session/read-only repo base classes), so service startup order is less brittle once migrations are applied.

### Compose recommendation

- Add a dedicated `migration_job` service in compose that:
  - waits for MongoDB + S3 + Kafka readiness,
  - runs create-user + migrations + bucket init,
  - exits successfully before dependent app services start.
- Gate interactive_ai services on migration completion (or run migration as a required manual step with a clear script/Make target).

---

## Execution Checklist (Branch-Ready)

Use this as the operational checklist for the current migration branch.

## Phase 1 — Compose foundation

- [ ] Fill runtime env values in `.env` (or `.env.compose`).
- [ ] Add MongoDB service + named volume to root compose.
- [ ] Add/verify infra service healthchecks and `depends_on` ordering.
- [ ] Fix known compose misconfigurations (router collisions, missing config mounts, undefined DB vars, SeaweedFS persistence).
- [ ] Add compose profiles (`infra`, `platform`, `interactive`, `jobs`, `observability`).
- [ ] Validate with `docker compose config`.

**Acceptance:** Infra stack starts from empty state and all healthchecks pass.

## Phase 2 — Local auth/authz mock mode

- [x] Add global `AUTH_MODE=mock` (or equivalent) gating.
- [x] Implement identity fallback in shared request auth dependency.
- [x] Implement SpiceDB bypass adapter returning allow-all.
- [x] Make onboarding/user_directory token checks bypassable in mock mode.
- [x] Add startup warnings and per-request debug markers for bypassed authz checks.
- [ ] Document “mock mode is local-only”.

**Acceptance:** Protected endpoints are callable locally without OIDC/SpiceDB.

### Phase 2 implementation notes (done)

- Identity fallback is implemented in `libs/fastapi_tools/src/geti_fastapi_tools/identity.py`:
  - missing/invalid `x-auth-request-access-token` yields mock identity in `AUTH_MODE=mock`.
- SpiceDB allow-all mode is implemented in `libs/spicedb_tools/src/geti_spicedb_tools/spicedb.py`:
  - permission checks return allow,
  - relation mutation/read calls are no-op or empty in mock mode.
- Onboarding JWT/token validation bypass in mock mode:
  - `platform/services/onboarding/app/jwt_utils.py`
  - `platform/services/onboarding/app/routers/onboarding.py`
- user_directory token/header validation bypass in mock mode:
  - `platform/services/user_directory/app/common/jwt_token_validation.py`
  - `platform/services/user_directory/app/common/users.py`
  - `platform/services/user_directory/app/endpoints/user_management/activate_user.py`
- ACL fallback for jobs/resource to avoid empty-result behavior under mock SpiceDB:
  - `interactive_ai/services/jobs/app/microservice/rest/job_controller.py`
  - `interactive_ai/services/jobs/app/microservice/grpc_api/grpc_job_service.py`
  - `interactive_ai/services/resource/app/managers/project_manager.py`

## Phase 2.1 — Reverse proxy and ingress parity (Traefik)

- [x] Define Traefik as the single entrypoint for local compose (HTTP first, TLS optional).
- [x] Add/verify router rules for all externally reachable APIs and web paths.
- [x] Mirror key ingress path behavior from Kubernetes (host/path routing expectations).
- [x] Ensure auth/mock-auth related routes are reachable through Traefik (including onboarding/user flows).
- [x] Add health and smoke checks through Traefik endpoints (not direct container ports).
- [x] Document route map (`host/path -> service:port`) in compose migration docs.

**Acceptance:** Core UI/API flows work end-to-end through Traefik exactly as the local ingress layer.

### Phase 2.1 route map (implemented in compose labels)

Primary host: `geti.localhost`

- `/dex` -> `dex:5556`
- `/api/v*/set_cookie` -> `platform_auth_proxy:7002`
- account API paths (`/api/v*/organizations*`, `/logout`, `/profile`, `/personal_access_tokens*`) -> `platform_account:5002`
- user-directory paths (`/api/v*/users/reset_password`, `/users/*/update_password`, `/users/confirm_registration`, `/organizations/*/users/*`) -> `platform_user_directory:9000`
- `/api/v1/logs*` -> `platform_observability:9000`
- director API train/optimize/status/configuration paths -> `interactive_ai_director:4999`
- jobs API (`/api/v*/.../workspaces/.../jobs*`) -> `interactive_ai_jobs:8000`
- media display paths -> `interactive_ai_media:5002`
- inference paths (`pipelines/models` predict/explain/status) -> `interactive_ai_inference_gateway:7000`
- visual prompt path (`...:prompt`) -> `interactive_ai_visual_prompt:8000`
- dataset import/export paths -> `interactive_ai_dataset_import_export:8000`
- project import/export paths -> `interactive_ai_project_import_export:8000`
- file service prefix `/api/v1/fileservice/` (with strip-prefix middleware) -> `s3:8333`
- generic API fallback `/api/*` -> `interactive_ai_resource:5000`
- web catch-all -> `web:3000`

Auxiliary hosts:

- `auth.geti.localhost` -> `authelia:9091`
- `traefik.localhost` -> Traefik dashboard/API

Traefik smoke validation command:

- `make compose-smoke`
- Script path: `infrastructure/compose-smoke.sh`
- Current checks verify routing through Traefik (non-404) for:
  - `/`
  - `/dex`
  - `/api/v1/healthz`
  - `/api/v1/organizations/test/workspaces/test/jobs`

## Phase 3 — MongoDB bootstrap automation

- [x] Add compose `migration_job` service.
- [x] Run Mongo service-user creation step.
- [x] Run Mongo version migrations.
- [x] Run S3 bucket bootstrap.
- [x] Make app services depend on successful migration job completion.

**Acceptance:** Fresh environment can be bootstrapped end-to-end without manual DB operations.

### Phase 3 implementation notes (done)

- Added `migration_job` service in root compose that executes:
  - `mongodb_create_service_user`
  - `run_migration`
  - `create_s3_bucket`
- Added env wiring for migration bootstrap in `.env` / `.env.example`:
  - `SERVICE_USER_ALL_DB_ROLES`
  - `S3_BUCKET`
- Added `depends_on: migration_job: condition: service_completed_successfully` to interactive_ai services.
- Added helper bootstrap command:
  - `make compose-bootstrap`
  - Script: `infrastructure/compose-bootstrap.sh`

## Phase 4 — Platform service wiring

- [x] Wire `platform_account` runtime env/dependencies using existing service compose as template.
- [x] Wire `platform_auth_proxy` in mock-compatible mode (or bypass path where applicable).
- [x] Wire `platform_user_directory` with non-K8s config/secrets source.
- [x] Wire remaining platform services (`notifier`, `onboarding`, `credit`, `initial_user`) for compose runtime.

**Acceptance:** Core platform flows (startup + basic API calls) succeed under compose.

### Phase 4 implementation notes (in progress)

- Added runtime env and dependency wiring in root compose for:
  - `platform_account`
  - `platform_auth_proxy`
  - `platform_user_directory`
  - `platform_onboarding`
  - `platform_credit`
  - `platform_notifier`
  - `platform_initial_user`
- Added local supporting services for platform flows:
  - `openldap`
  - `mailhog`
- Added onboarding Traefik routes:
  - `/api/v*/onboarding/user`
  - `/api/v*/admin/onboarding/tokens`
- Added local env defaults needed by platform runtime (`.env`, `.env.example`) for Kafka plaintext mode, LDAP, SMTP, and initial-user bootstrap.

Remaining for full Phase 4 acceptance:

- [x] Provide/generate local JWT cert files for `platform_auth_proxy` mount at `./infrastructure/data/auth_proxy/certs/{tls.crt,tls.key}`.
- [x] Add a platform-focused smoke run proving account/onboarding/user-directory calls succeed end-to-end through Traefik.

Commands added:

- `make compose-prepare-certs`
- `make compose-bootstrap` (now prepares certs before running migration bootstrap)
- `make compose-smoke` now includes platform-routed endpoints:
  - `/api/v1/onboarding/user`
  - `/api/v1/admin/onboarding/tokens`
  - `/api/v1/users/reset_password`

## Phase 5 — Mark K8s/Flyte dependent features explicitly unavailable

- [ ] Add compose-mode guards in all files listed under K8s/Flyte coupling sections.
- [ ] Return 501/503 + explicit logs for unimplemented paths.
- [ ] Ensure error messages are consistent and discoverable.
- [ ] Add one integration smoke test covering unavailable-path response behavior.
- [x] Add one integration smoke test covering unavailable-path response behavior.

**Acceptance:** No hidden hangs/crashes; unsupported features fail fast with actionable logs.

### Phase 5 implementation notes (in progress)

Current status: **partial** (first high-impact subset implemented).

- Added compose-mode (`DEPLOYMENT_MODE=compose`) fail-fast guards for jobs scheduler Flyte paths:
  - `interactive_ai/services/jobs/app/scheduler/flyte.py`
  - `interactive_ai/services/jobs/app/scheduler/loops/scheduling.py`
  - `interactive_ai/services/jobs/app/scheduler/loops/revert_scheduling.py`
  - `interactive_ai/services/jobs/app/scheduler/loops/cancellation.py`
  - `interactive_ai/services/jobs/app/scheduler/loops/recovery.py`
- Added compose-mode fail-fast guards for model registration KServe/K8s paths:
  - `interactive_ai/services/model_registration/app/service/custom_resource.py`
  - `interactive_ai/services/model_registration/app/service/model_registration.py`
- Guard behavior:
  - Scheduler/model-registration logs explicit message:
    - `"Feature unavailable in compose mode: <operation>. This path currently requires Kubernetes/Flyte."`
  - gRPC model-registration endpoints now abort with `UNIMPLEMENTED` in compose mode.
- Added tests for unavailable-path behavior:
  - `interactive_ai/services/model_registration/tests/unit/test_model_registration.py::test_register_new_pipelines_compose_mode_aborts`
  - `interactive_ai/services/model_registration/tests/unit/test_model_registration.py::test_list_pipeline_compose_mode_aborts`
  - `interactive_ai/services/jobs/tests/unit/scheduler/loops/test_recovery.py::test_check_and_recover_workspace_jobs_if_needed_compose_mode`

Additional unavailable-path guard coverage added:

- jobs scheduler API/event boundaries now fail-fast in compose mode:
  - `interactive_ai/services/jobs/app/scheduler/grpc_api/job_update_service.py`
  - `interactive_ai/services/jobs/app/scheduler/kafka_handler.py`
- cancellation path guard standardized to raising behavior:
  - `interactive_ai/services/jobs/app/scheduler/loops/cancellation.py`

Additional tests added:

- `interactive_ai/services/jobs/tests/unit/scheduler/grpc_api/test_job_update_service.py::test_job_update_compose_mode_returns_unimplemented`
- `interactive_ai/services/jobs/tests/unit/scheduler/test_kafka_handler.py::test_on_flyte_event_compose_mode_raises`
- `interactive_ai/services/jobs/tests/unit/scheduler/loops/test_cancellation.py::test_cancel_execution_compose_mode_raises`

## Phase 6 — Replace KServe model registration path

- [ ] Introduce Docker-native model serving control path.
- [ ] Keep existing service API contract stable.
- [ ] Add deploy/infer/undeploy smoke checks.

**Acceptance:** Local model serving works without K8s CRDs.

## Phase 7 — Replace Flyte jobs execution path

- [ ] Choose runtime (Celery+Redis preferred).
- [ ] Replace Flyte scheduler adapters.
- [ ] Replace Flyte secret/context assumptions with env-driven config.
- [ ] Replace K8s resource-capacity policy with host/local policy.
- [ ] Validate train/optimize/test/import-export job flows.

**Acceptance:** Core jobs run in compose without Flyte.

## Phase 8 — Cutover + docs

- [ ] Make compose path default in onboarding docs.
- [ ] Document mock-auth behavior and limitations.
- [ ] Document unsupported/placeholder features and migration status.
- [ ] Add CI compose smoke target.

**Acceptance:** New developer can follow docs and run platform locally with compose only.

---

## Suggested Startup Order (Compose)

1. `db` (Postgres for platform deps / SpiceDB backing store)
2. `spicedb` (or mocked/no-op path depending on chosen auth profile)
3. `mongodb`
4. `kafka`
5. `s3` (SeaweedFS)
6. `migration_job` (Mongo user + data migrations + S3 bootstrap)
7. platform core services
8. interactive_ai services
9. reverse proxy/web

---

## Definition of Done (for this document’s plan)

- Compose path is runnable and documented.
- Auth/authz mock mode unblocks local dev.
- K8s/Flyte code dependencies are explicitly mapped and guarded.
- MongoDB bootstrap for shared DB is automated and repeatable.
- Execution checklist is actionable and can be tracked to completion.
