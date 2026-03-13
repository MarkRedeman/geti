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
- Current default checks verify routing through Traefik (non-404) for:
  - `/`
  - `/dex`
  - `/api/v1/healthz`
  - `/api/v1/organizations/test/workspaces/test/jobs`
  - `/api/v1/organizations/test/workspaces/test/projects/000000000000000000000000/pipelines/active/status`
  - `/api/v1/organizations/test/workspaces/test/projects/000000000000000000000000/models/active/status`
- Smoke script now supports status-aware checks via `SMOKE_CHECKS` (format: `path|expected`):
  - exact status code, e.g. `.../status|200`
  - wildcard status class, e.g. `...|2xx`
  - route-only check, e.g. `...|not_404`

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

- [x] Add compose-mode guards in all files listed under K8s/Flyte coupling sections.
- [x] Return 501/503 + explicit logs for unimplemented paths.
- [x] Ensure error messages are consistent and discoverable.
- [x] Add one integration smoke test covering unavailable-path response behavior.

**Acceptance:** No hidden hangs/crashes; unsupported features fail fast with actionable logs.

### Phase 5 implementation notes (completed)

Current status: **completed**.

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
- startup-critical non-Flyte K8s couplings guarded in compose mode:
  - `platform/services/observability/app/main.py` (skip sherlock Kubernetes backend in compose)
  - `platform/services/user_directory/app/main.py` (skip sherlock Kubernetes backend in compose)
  - `interactive_ai/services/jobs/app/policies/main.py` (skip resource manager loop in compose)
  - `platform/services/user_directory/app/service_connection/k8s_client/apis.py` (fail-fast K8s API init in compose)
  - `platform/services/observability/app/service_connection/k8s_client/apis.py` (fail-fast K8s API init in compose)
  - `platform/services/observability/app/service_connection/k8s_client/cluster_info.py` (fail-fast cluster dump path in compose)
  - `interactive_ai/services/jobs/app/scheduler/loops/scheduling.py` (skip scheduling loop in compose)
  - `interactive_ai/services/jobs/app/scheduler/loops/revert_scheduling.py` (skip revert scheduling loop in compose)

Compose-compatible fallback added (instead of hard failure):

- `platform/services/user_directory/app/service_connection/smtp_client.py`
  - in compose mode, SMTP config now comes from environment variables instead of Kubernetes secrets.

Additional tests added:

- `interactive_ai/services/jobs/tests/unit/scheduler/grpc_api/test_job_update_service.py::test_job_update_compose_mode_returns_unimplemented`
- `interactive_ai/services/jobs/tests/unit/scheduler/test_kafka_handler.py::test_on_flyte_event_compose_mode_raises`
- `interactive_ai/services/jobs/tests/unit/scheduler/loops/test_cancellation.py::test_cancel_execution_compose_mode_raises`
- `interactive_ai/services/jobs/tests/unit/policy/test_main.py::test_start_skips_resource_manager_in_compose`
- `platform/services/user_directory/tests/unit/service_connection/k8s_client/test_apis.py::test_create_k8s_apis_compose_mode_raises`
- `platform/services/observability/tests/unit/service_connection/k8s_client/test_apis.py::test_create_k8s_apis_compose_mode_raises`
- `platform/services/observability/tests/unit/service_connection/k8s_client/test_cluster_info.py::test_create_cluster_info_dump_compose_mode_raises`
- `interactive_ai/services/jobs/tests/unit/scheduler/loops/test_scheduling.py::test_run_scheduling_loop_compose_mode_skips`
- `interactive_ai/services/jobs/tests/unit/scheduler/loops/test_revert_scheduling.py::test_run_revert_scheduling_loop_compose_mode_skips`
- `platform/services/user_directory/tests/unit/service_connection/test_smtp_client.py::test_smtp_client_compose_mode_uses_env`

## Phase 6 — Replace KServe model registration path

- [x] Introduce Docker-native model serving control path.
- [x] Keep existing service API contract stable.
- [x] Add deploy/infer/undeploy smoke checks.

### Temporary bridge (implemented)

- `interactive_ai_inference_gateway` now supports a compose OVMS backend bridge:
  - when `DEPLOYMENT_MODE=compose`, gateway starts with OVMS gRPC client,
  - requests are routed through existing controller/usecase path using OVMS-backed model access service.
- This removes the global compose 404 behavior and enables inference path integration work in compose.

Related files:

- `interactive_ai/services/inference_gateway/main.go`
- `interactive_ai/services/inference_gateway/app/grpc/ovms_client.go`
- `interactive_ai/services/inference_gateway/app/service/ovms_model_access.go`
- `docker-compose.yaml` (`interactive_ai_inference_gateway.environment.DEPLOYMENT_MODE`)

### Phase 6 implementation notes (completed)

- `interactive_ai_model_registration` now has a compose-native, KServe-free path backed by S3 metadata:
  - compose mode does **not** call K8s CRDs / `InferenceManager` for:
    - `register_new_pipelines`
    - `deregister_pipeline`
    - `list_pipelines`
    - `recover_pipeline`
    - `delete_project_pipelines`
- Added S3 registry metadata helpers:
  - `put_json_object`, `get_json_object`, `list_registry_folders`
  - registry key format: `<pipeline_name>/.registry.json`
- `interactive_ai_model_registration` compose env now includes S3 endpoint/credentials and model bucket wiring.
- `interactive_ai_inference_gateway` runs in compose mode with OVMS backend bridge.
- compose model lifecycle is now wired end-to-end between model_registration and OVMS:
  - register/override sync model artifacts into OVMS model directory and add `models.json` entry,
  - deregister/purge remove OVMS model config and files,
  - recover restores model artifacts from S3 and re-adds OVMS config.

Validation scope for this phase:

- model registration deploy/register/list/recover/delete paths execute in compose without KServe,
- inference endpoints use OVMS path in compose mode (with readiness/retry behavior).

**Acceptance:** Local model serving works without K8s CRDs.

## Phase 7 — Replace Flyte jobs execution path

- [x] Choose runtime (Celery+Redis preferred).
- [x] Replace Flyte scheduler adapters.
- [x] Replace Flyte secret/context assumptions with env-driven config.
- [x] Replace K8s resource-capacity policy with host/local policy.
- [x] Validate train/optimize/test/import-export job flows.

**Acceptance:** Core jobs run in compose without Flyte.

Phase 7 completion status refinement:

- **Completed for compose local runnability:** scheduler/worker orchestration and job-type bridges are operational without Flyte.
- **Completed train milestone boundary:** train now runs staged compose flow with real prepare/trainer/finalize/evaluate and real registration/acceptance.
- **Completed optimize milestone boundary:** optimize_pot now runs staged compose flow with real prepare/trainer/finalize/evaluate.
- **Intentional remaining boundary:** train inference sub-steps (`task_infer_on_unannotated`, `pipeline_infer_on_unannotated`) remain stubbed until inference replacement is complete.

### Phase 7 implementation notes (completed)

- Selected runtime for compose mode: **local scheduler executor** (simulation-first), with a clean path to later swap to Celery workers.
- Implemented `LocalExecutor` in jobs scheduler:
  - file: `interactive_ai/services/jobs/app/scheduler/local_executor.py`
  - starts local executions and publishes synthetic workflow events to reuse existing state machine/event handlers.
- Replaced Flyte-only scheduler behavior in compose mode:
  - `interactive_ai/services/jobs/app/scheduler/loops/scheduling.py`
  - `interactive_ai/services/jobs/app/scheduler/loops/revert_scheduling.py`
  - `interactive_ai/services/jobs/app/scheduler/loops/cancellation.py`
  - `interactive_ai/services/jobs/app/scheduler/kafka_handler.py`
  - `interactive_ai/services/jobs/app/scheduler/grpc_api/job_update_service.py`
  - `interactive_ai/services/jobs/app/scheduler/main.py`
- Added compose service wiring for jobs control loops in root compose:
  - `interactive_ai_jobs_scheduler` (`python scheduler/main.py`)
  - `interactive_ai_jobs_policy` (`python policies/main.py`)
  - shared env wiring for Mongo/Kafka and local executor mode.
- Added compose-local job templates mount:
  - `infrastructure/data/jobs/jobs_templates.yaml`

Current compose executor mode:

- `LOCAL_EXECUTOR_MODE=celery` (default)
- `CELERY_BROKER_URL=redis://redis:6379/0`
- `CELERY_RESULT_BACKEND=redis://redis:6379/1`
- `LOCAL_EXECUTOR_SIM_DURATION_SEC=2`

Compose now includes:

- `redis` service
- `interactive_ai_jobs_worker` Celery worker service

Execution bridge behavior:

- Scheduler dispatches local job execution to Celery tasks in compose mode.
- LocalExecutor continues to publish synthetic workflow events (`RUNNING` -> terminal phase)
  so existing state-machine/event handlers are reused.

Celery execution status (current):

- dataset/project import-export job types are now routed through Celery to workflow runtime containers:
  - `export_dataset`
  - `prepare_import_to_new_project`
  - `prepare_import_to_existing_project`
  - `perform_import_to_new_project`
  - `perform_import_to_existing_project`
  - `export_project`
  - `import_project`
- model-test job type is now routed through Celery workflow runtime container:
  - `test`
- train job now has an initial Celery workflow-container execution bridge for preflight payload/runtime validation (`get_train_data` path).
- train job now has an expanded Celery workflow-container bridge covering:
  - lock + train data resolution
  - train dataset creation
  - pre-train model/output preparation (`prepare_train`)
- train bridge now also launches the trainer runtime container step (OTX runtime image command execution).
- train bridge now also runs a post-trainer finalize stage (`finalize_train`) using the train workflow runtime container.
- train bridge now includes a compose-safe evaluate stage hook using the train workflow runtime container.
- optimize_pot now runs a staged Celery workflow-container bridge:
  - optimize prepare (`prepare_optimize`)
  - trainer runtime stage (`JOB_TYPE=optimize_pot`)
  - optimize finalize (`finalize_optimize`)
  - optimize evaluate (`_evaluate_optimized_model`)

Celery compose fallback policy:

- unsupported job types now fail fast with explicit runtime error in `celery_tasks`.
- silent simulation fallback in Celery path has been removed to avoid hiding unported runtime behavior.

Scheduler import coupling reduction (compose startup):

- removed eager `flytekit.remote` imports from scheduling/revert loops and kafka handler (TYPE_CHECKING-only typing usage).
- removed eager `flyteidl` import from cancellation loop by mirroring required workflow phase constants locally.

Train status caveat:

- current train Celery path includes a stubbed evaluate/infer bridge in compose mode (registration/inference-heavy substeps are still bypassed).

Train safety safeguards added:

- evaluate stage now checks that base model status is in `TRAINED_NO_STATS`/`SUCCESS` before running.
- finalize stage is skipped on retry if model status is no longer `NOT_READY`, to avoid double-finalize state corruption.
- evaluate stub mode is now explicit via `WORKFLOW_EVALUATE_STUB` env in jobs worker compose config.
- evaluate stage now always no-ops embedded `finalize_train` call because finalize is executed in a dedicated prior stage.

Evaluate stub control is now split per sub-step:

- `WORKFLOW_EVALUATE_STUB_METADATA`
- `WORKFLOW_EVALUATE_STUB_EVALUATE`
- `WORKFLOW_EVALUATE_STUB_REGISTER`
- `WORKFLOW_EVALUATE_STUB_ACCEPTANCE`
- `WORKFLOW_EVALUATE_STUB_TASK_INFER`
- `WORKFLOW_EVALUATE_STUB_PIPELINE_INFER`

This allows incremental de-stubbing of evaluate flow without all-or-nothing risk.

Current de-stub progression:

- `WORKFLOW_EVALUATE_STUB_EVALUATE=false` in compose worker (real evaluate path enabled)
- `WORKFLOW_EVALUATE_STUB_REGISTER=false` and `WORKFLOW_EVALUATE_STUB_ACCEPTANCE=false` (real registration + acceptance enabled)
- `WORKFLOW_EVALUATE_STUB_TASK_INFER=false` and `WORKFLOW_EVALUATE_STUB_PIPELINE_INFER=false` (real post-train task/pipeline inference enabled in compose)

Required compose wiring for real registration path:

- `MODEL_REGISTRATION_SERVICE=interactive_ai_model_registration:5555` added to jobs worker env.
- `MODEL_REGISTRATION_*` forwarding added in Celery stage container launches.

Important note on current scope:

- train / optimize / model-test / import-export run through real staged Celery workflow-container execution in compose.
- any job type outside the supported set now fails fast in Celery mode until explicitly ported.

New files:

- `interactive_ai/services/jobs/app/scheduler/celery_app.py`
- `interactive_ai/services/jobs/app/scheduler/celery_tasks.py`
- `interactive_ai/services/jobs/app/scheduler/workflow_adapters.py`

## Phase 8 — Cutover + docs

- [x] Make compose path default in onboarding docs.
- [x] Document mock-auth behavior and limitations.
- [x] Document unsupported/placeholder features and migration status.
- [x] Add CI compose smoke target.

**Acceptance:** New developer can follow docs and run platform locally with compose only.

### Phase 8 implementation notes (completed)

- Updated onboarding docs to make compose the default local path:
  - `CONTRIBUTING.md` (compose-first setup and commands)
  - `README.md` (compose local development entry in Getting Started)
- Added explicit mock-auth local-only documentation and limitations in `CONTRIBUTING.md`.
- Added explicit compose-mode unsupported/placeholder features section in `CONTRIBUTING.md` and linked migration status to this document.
- Added CI compose smoke job in `.github/workflows/main.yml`:
  - validates `make compose-config`
  - starts compose stack
  - runs `make compose-smoke`
  - always tears down stack
- Updated smoke script to support configurable path lists via `SMOKE_PATHS` env (used by CI).
- Expanded default smoke route coverage with inference status path through Traefik to validate compose OVMS bridge routing.
- CI compose smoke now uses `SMOKE_CHECKS` and enforces `200` for inference status endpoint.
- CI compose smoke now enforces `200` for both pipeline and model status endpoints in inference gateway.

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

---

## Migration Findings Summary (Appended)

This section summarizes what was discovered and implemented during the migration work across Phases 1–8.

### What is now in place

1. **Compose-first local stack exists and is wired**
   - Root compose has infra dependencies (Postgres, MongoDB, Kafka, S3, SpiceDB, Traefik, Dex/Authelia) and persistence.
   - Compose bootstrap + smoke scripts exist and are integrated into Make targets.

2. **Ingress parity via Traefik is in place for core routes**
   - Service routes are label-driven with priorities.
   - Smoke tests validate routing through Traefik rather than direct service ports.

3. **Auth/authz can be bypassed for local development**
   - `AUTH_MODE=mock` path implemented across shared identity + SpiceDB + key service paths.
   - This unblocks local dev without OIDC/SpiceDB setup friction.

4. **Mongo bootstrap is automated**
   - One-shot `migration_job` service runs Mongo user setup, migrations, and S3 bootstrap.
   - Interactive AI services depend on successful bootstrap.

5. **Platform services are wired for compose runtime**
   - Account/auth_proxy/user_directory/onboarding/notifier/credit/initial_user have compose env/dependency wiring.
   - Local helper services (LDAP + Mailhog) added.

6. **K8s/Flyte failure modes are explicit**
   - Many previously implicit failures now fail fast with clear compose-mode logs/status.
   - Startup-critical lazy K8s clients are guarded.

7. **KServe dependency removed from model_registration compose path**
   - Compose-mode model registration uses S3-backed metadata (`.registry.json`) instead of CRDs.
   - Register/list/recover/delete flows are available without KServe.

8. **Flyte jobs path replaced for compose mode**
   - Local executor added for scheduler flow continuity.
   - Scheduler and related event/update paths were adapted for compose-mode execution metadata.

9. **Docs + CI were cut over**
   - Compose is now documented as default local path.
   - Main CI includes compose smoke job.

---

## Honest State Review (Current)

### Overall status

The repository is now in a **workable compose-first local state** for developer onboarding and core platform bring-up. However, some areas are intentionally temporary and not equivalent to production behavior.

### What is good

- Local startup path is much clearer and more reproducible than before.
- Major Kubernetes/Flyte hard dependencies are no longer hard blockers for day-to-day local development.
- CI now has a compose smoke gate, reducing drift risk.

### Gaps / limitations found while implementing

1. **Inference parity is partial in compose mode**
   - `interactive_ai_inference_gateway` uses OVMS in compose mode with real readiness checks and recovery retries.
   - Full API conformance and negative-path coverage (deploy/infer/undeploy/error semantics) still needs systematic testing.

2. **Jobs execution in compose is transitional**
   - Local executor still supports simulation mode, but compose worker path now runs staged real execution for import/export/model-test/train/optimize.
   - Recovery loop is intentionally disabled in compose (no Flyte-backed execution recovery), so failed/stuck-run auto-recovery semantics are still limited.

3. **Auth model is intentionally insecure for local mode**
   - `AUTH_MODE=mock` bypasses identity/authorization.
   - Useful for dev speed, but must stay tightly scoped and non-default outside local.

4. **Route coverage is representative, not exhaustive**
   - Traefik rules and smoke checks cover core paths.
   - Full API surface parity with historical ingress behavior still needs systematic verification.

5. **Configuration complexity remains high**
   - Env surface is still large; some values are placeholders.
   - A stricter env validation layer would reduce startup/runtime surprises.

6. **Service behavior parity is mixed**
   - Some compose-mode paths are true replacements (e.g., model registration metadata path).
   - Others are explicit temporary bridges (404/unimplemented/simulated).

7. **Local data/state hygiene is still rough**
   - Runtime-generated artifacts (auth/db files) and local volumes can cause stale-state issues between runs.

---

## Improvement Checklist (Next)

Use this as the next execution backlog after Phases 1–8.

- [x] **Inference replacement (highest priority):** OVMS-based local serving path integrated; compose 404 mode removed.
- [ ] Add deploy/infer/undeploy conformance tests for inference API contract.
- [ ] Move jobs executor from simulation-first to validated real execution for at least one job type end-to-end.
- [ ] Expand real-execution coverage to train/optimize/test/import-export with deterministic retries/cancel semantics.
- [ ] Add readiness-driven waits in CI compose job (remove blind sleep).
- [ ] Upload compose logs/artifacts on CI smoke failure for fast diagnosis.
- [ ] Expand Traefik smoke paths to a broader API matrix and verify expected status classes.
- [ ] Add stricter startup env validation per service (fail early on missing critical vars).
- [ ] Create a config parity matrix (K8s ConfigMap/Secret -> Compose env/secret) and maintain it.
- [ ] Externalize sensitive local secrets where possible (file/secret mount over plain env).
- [ ] Add developer ergonomics targets: `compose-up`, `compose-down`, `compose-reset`, `compose-logs`.
- [ ] Add a documented “clean-room local run” procedure and expected timing/health criteria.
- [ ] Define compose local “GA” criteria and track pass rate over time.
