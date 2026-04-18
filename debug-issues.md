# Debug Issues Summary

This file summarizes the compose/bootstrap/runtime issues investigated and fixed in this session.

## 1) `make compose-bootstrap` failed during migrations

- **Symptom**
  - `geti_init` failed with:
    - `OSError: Environment variable S3_CREDENTIALS_PROVIDER should be set to either 'local' or 'aws'`
    - followed by `UnboundLocalError: local variable 'project_idx' referenced before assignment`
- **Root cause**
  - `geti_init` container did not receive S3 credential provider env expected by migration code.
  - Migration error handler assumed `project_idx` existed even if failure happened before project loop.
- **Fixes**
  - `docker-compose.yaml`
    - Added for `geti_init`:
      - `S3_CREDENTIALS_PROVIDER: local`
      - `S3_HOST: s3:8333`
  - `interactive_ai/migration_job/migration_job/run_migration.py`
    - Made failure bookkeeping safe when exception occurs before project enumeration.

## 2) Login failed in Dex (`invalid password for user`)

- **Symptom**
  - Dex logs showed invalid credentials for `admin@geti.local` after bootstrap.
- **Root cause**
  - LDAP password reconciliation path in init used a hash/update flow that was incompatible in this setup.
- **Fix**
  - `infrastructure/geti_init/main.py`
    - Switched to LDAP native password modify operation (`passwd_s`) with plaintext input from `INITIAL_USER_PASSWORD`.

## 3) `/api/v1/user_settings` returned 500 after login

- **Symptom**
  - API traceback: `NoUserSettingsException` from resource endpoint.
- **Root cause**
  - Missing default UI settings doc for user; endpoint raised exception instead of self-healing.
- **Fixes**
  - `infrastructure/geti_init/main.py`
    - Added default user settings initialization during bootstrap.
  - `interactive_ai/services/resource/app/communication/rest_endpoints/user_settings_endpoints.py`
    - `GET /api/v1/user_settings` now creates default settings when missing and returns them.

## 4) Video frame annotation lookup produced 500

- **Symptom**
  - Requests like `/frames/{idx}/annotations/latest` returned 500 when annotation was absent.
  - Traceback showed `AnnotationsNotFoundException`.
- **Root cause**
  - In unified API mode, `GetiBaseException` mapping was missing at top-level app, so expected non-500 statuses bubbled as 500.
- **Fix**
  - `interactive_ai/services/main.py`
    - Added `GetiBaseException` handler mirroring resource behavior (including 204/304 response handling).

## 5) Training submission failed with gRPC `UNIMPLEMENTED: Method not found`

- **Symptom**
  - `submit` / `get_count` calls from API/auto-train failed against `interactive_ai_jobs_scheduler:50051`.
- **Root cause**
  - Address pointed to scheduler gRPC endpoint exposing `JobUpdateService` only, not `JobService` (`submit`, `list`, `get_count`).
- **Fixes**
  - `interactive_ai/services/main.py`
    - Started embedded jobs `GRPCJobService` process in unified API lifespan.
  - `docker-compose.yaml`
    - For `interactive_ai_api`, changed `JOB_SERVICE_ADDRESS` to `localhost:50051` so client targets embedded service.

## 6) Training job still failed after submission (latest failed job)

- **Symptom**
  - Scheduler/worker marked job failed after start.
  - Worker logs showed pretrained weight bootstrap errors:
    - missing `pretrainedweights/pretrained_models_v2.json`
    - fallback to `https://storage.geti.intel.com/weights/pretrained_models_v2.json` returned `403`
- **Root cause**
  - Weight seeding was effectively disabled by default and runtime fallback URL required external access not available in environment.
- **Fixes**
  - `infrastructure/compose-bootstrap.sh`
    - Default changed to seed weights (`SEED_WEIGHTS=1`).
  - `docker-compose.yaml`
    - Added `INIT_SEED_WEIGHTS: ${INIT_SEED_WEIGHTS:-0}` to `geti_init` env so bootstrap flag actually reaches container.
  - `interactive_ai/workflows/train/trainer/scripts/pretrained_weights.py`
    - Enhanced fallback: when S3 object missing, allow direct download from per-model `url` in `pretrained_models_v2.json`.
  - Manually seeded required objects for current template into `pretrainedweights` bucket:
    - `pretrained_models_v2.json`
    - `efficientnet_b2b-0527-531f10e6.pth`
    - `efficientnet_b2b-mask_rcnn-576x576.pth`

## Notes

- Repeated feature flag warnings like `FEATURE_FLAG_KEYPOINT_DETECTION` / `FEATURE_FLAG_ANNOTATION_HOLE` are noisy but non-fatal (defaulting to `False`).
- Protobuf runtime warnings in logs are informational for now and did not block the fixed flows above.
