# Compose Platform Services Refactor Plan

This document defines how to refactor `platform/services/` for a compose-first Geti runtime.

## Goal

Reduce platform complexity for self-hosted compose deployments by:

- Removing SaaS/K8s-only services that are not part of the compose product path.
- Folding bootstrap-only logic into `geti_init`.
- Keeping only the minimum set of platform runtime services needed in compose.
- Documenting one optional future merge (`account` + `auth_proxy`) without committing to it now.

Target steady state: **2-3 platform runtime services** plus infra dependencies.

## Implementation status

- **Phase 1 (remove unused service trees): completed**
- **Phase 2 (consolidate bootstrap jobs): completed**
- **Phase 3 (clean compose and docs surface): completed**
- **Phase 4 (optional account+auth_proxy merge): completed**
- **Phase 5 (merge user_directory into account): completed**

## Current service inventory

### Go runtime services

- `platform/services/account/`: Core identity and tenancy service (organizations, workspaces, users, memberships, tokens). Exposes gRPC and REST gateway APIs; integrates with PostgreSQL, SpiceDB, Kafka, and S3.
- `platform/services/auth_proxy/`: Auth gateway service used by Traefik forward-auth flow; validates/mints JWTs and calls account gRPC APIs.

### Python runtime services

- `platform/services/user_directory/`: User lifecycle flows (invite, registration confirmation, password reset/update, status changes), integrating LDAP/SpiceDB/account APIs and Kafka.
- `platform/services/credit/`: Billing and credits subsystem (products, subscriptions, balances, leases); SaaS-oriented.
- `platform/services/onboarding/`: Self-serve onboarding and subscription activation; SaaS-oriented.
- `platform/services/notifier/`: Kafka-to-SMTP notification worker for invitation and account emails.
- `platform/services/observability/`: API for collecting and packaging telemetry artifacts; includes K8s-oriented runtime paths.
- `platform/services/platform_cleaner/`: Scheduled cleanup for telemetry and inactive users.
- `platform/services/initial_user/`: Bootstrap job that creates initial org/workspace/admin and assigns roles.
- `platform/services/weights_uploader/`: Bootstrap job that preloads model weights into object storage.

### Non-runtime service directories

- `platform/services/opa_bundle/`: Rego policy bundle for OPA-based authorization paths.
- `platform/services/config/`: Build/config stub directory (no runtime service implementation).

## Compose-first disposition by service

### Keep as runtime services

- `account` (**keep**): Required central platform API and data authority.
- `auth_proxy` (**keep for now**): Required auth middleware entry point in current compose routing model.
- `user_directory` (**keep**): Required user lifecycle operations still used by compose API flows.

### Absorb into bootstrap

- `initial_user` (**absorb into `geti_init`**): This is init-only behavior and belongs in bootstrap, not a standalone platform service.
- `weights_uploader` (**absorb into `geti_init`**): Already part of compose bootstrap responsibilities; remove duplicate standalone path.

### Remove from compose-first codebase

- `credit` (**remove**): SaaS billing/credit path not required for compose self-hosted product.
- `onboarding` (**remove**): SaaS sign-up/subscription flow not required in compose.
- `notifier` (**remove**): Notification pipeline tied to removed onboarding/invitation SaaS flows.
- `observability` (**remove**): K8s-leaning telemetry service not needed in compose local runtime.
- `platform_cleaner` (**remove**): Scheduled maintenance service not required in compose scope.
- `opa_bundle` (**remove**): OPA policy bundle not used in compose routing/auth path.
- `config` (**remove**): Non-functional stub directory.

## Proposed end-state architecture

### Runtime platform services (compose)

- `platform_account` (Go)

Auth proxy functionality now runs in `platform_account` (`/api/v1/auth`, `/api/v1/set_cookie`, `/api/v1/keys/`).
User lifecycle functionality previously served by `platform_user_directory` now runs in `platform_account`.

### Bootstrap/init responsibilities

- `geti_init` handles initial-user creation and pretrained weight upload.

### Removed legacy platform surface

- Billing/onboarding/notification/OPA/maintenance-only service trees removed.

## Refactor phases

### Phase 1: Remove unused service trees

Status: **Completed**

- Delete `credit`, `onboarding`, `notifier`, `observability`, `platform_cleaner`, `opa_bundle`, and `config` under `platform/services/`.
- Remove references to these services from build scripts, docs, CI jobs, and dependency manifests.
- Remove no-longer-used Python dependencies and lock entries introduced only for these services.

Notes:

- Removed service trees from `platform/services/`, leaving only `account`, `auth_proxy`, and `user_directory`.
- Updated CI path filters in `.github/components-path-filters.yml`.
- Removed observability acceptance block from `infrastructure/compose-parity.sh`.

### Phase 2: Consolidate bootstrap jobs

Status: **Completed**

- Move any remaining `initial_user` logic into `infrastructure/geti_init` if still duplicated.
- Move any remaining `weights_uploader` logic into `infrastructure/geti_init` if still duplicated.
- Delete standalone service directories after bootstrap parity is verified.

Notes:

- Moved initial-user modules into `infrastructure/geti_init/initial_user/`.
- Moved weights uploader code and model manifest into `infrastructure/geti_init/weights_uploader/`.
- Updated `infrastructure/geti_init/main.py` imports and config path usage.
- Updated `infrastructure/geti_init/Dockerfile` copy paths and `PYTHONPATH`.

### Phase 3: Clean compose and docs surface

Status: **Completed**

- Ensure `docker-compose.yaml` only references active platform services.
- Update `docs/compose/README.md` and getting-started docs to reflect final platform surface.
- Update troubleshooting docs to remove references to deleted services.

Notes:

- Compose runtime currently uses the reduced platform surface (`platform_account`).
- Compose docs were updated to reflect the reduced platform surface and current document set.
- This plan document has been updated with implementation progress.

### Phase 4: Optional future merge (discussion item)

Status: **Completed**

- Evaluate a single Go binary/container that hosts both account APIs and auth proxy handlers.
- Keep this as a follow-up design discussion; do not block current reduction work.

Notes:

- Merged auth proxy HTTP/JWT/cache/JWKS code into `platform/services/account/app/auth_proxy/`.
- Wired `/api/v1/auth`, `/api/v1/set_cookie`, and `/api/v1/keys/` into the account HTTP server.
- Removed standalone `platform_auth_proxy` service from `docker-compose.yaml` and pointed Traefik forwardAuth middleware to `platform_account:5002`.
- Removed `platform/services/auth_proxy/` directory.

## Optional merge analysis: `account` + `auth_proxy`

This merge is intentionally not mandatory in the current refactor, but it is a strong candidate for further simplification.

### Potential benefits

- Removes one network hop for auth/account lookups.
- Simplifies compose service graph and deployment surface.
- Reduces duplicated operational wiring (logging, telemetry, config, cert path handling).

### Potential risks

- Blends gateway and domain responsibilities into one deployable unit.
- Increases blast radius of regressions in auth paths.
- Requires careful preservation of current Traefik middleware behavior and routes.

### Recommendation for now

- Keep merged as a single Go runtime service in compose.
- Re-evaluate only if operational concerns require re-splitting.

### Phase 5: Merge `user_directory` into `account`

Status: **Completed**

- Implement account HTTP handlers for user lifecycle routes previously routed to `platform_user_directory`.
- Route those Traefik paths to `platform_account`.
- Remove standalone `platform_user_directory` service from compose.

Notes:

- Added account-side REST handlers for user lifecycle endpoints (`create`, `invite`, `confirm_registration`, `request_password_reset`, `reset_password`, `update_password`, `users/count`).
- Added LDAP + JWT token handling directly in account service to support these flows in compose mode.
- Removed `platform/services/user_directory/` and compose/CI references to that service.

## Validation checklist

After refactor implementation, verify:

- Compose bootstrap still creates initial org/workspace/admin and required buckets.
- Login/auth flow via Dex/LDAP + `platform_account` forward-auth endpoints remains functional.
- User lifecycle endpoints served by `platform_account` still pass smoke tests.
- No compose docs or scripts reference removed platform services.
- No CI targets attempt to build or test deleted service directories.

## Scope boundaries

- This plan is compose-first and self-host focused.
- SaaS/K8s-only capabilities intentionally removed rather than preserved as dormant code.
- Historical commit references are intentionally excluded; this is a forward-looking architecture plan.
