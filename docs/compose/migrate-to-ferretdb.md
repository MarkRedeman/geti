# Investigating MongoDB → FerretDB migration (compose / single-node)

This document summarizes a feasibility investigation for replacing MongoDB with [FerretDB](https://docs.ferretdb.io/) in this codebase.

---

## Executive summary

**Short answer:** migration is possible in principle, but **not low-risk** for our current architecture.

For this repository, the highest-risk blockers are:

1. heavy use of MongoDB **sessions/transactions** in jobs scheduler paths,
2. broad use of **aggregation with `allowDiskUse=True`**,
3. critical reliance on **TTL indexes** (leader election + cleanup),
4. potential gaps around **collation**, advanced aggregation features, and admin/auth behavior.

Given that our primary target is single-node compose deployments, FerretDB could still be pursued as a phased effort, but we should treat it as a project with compatibility hardening rather than a drop-in swap.

---

## What FerretDB is (relevant to us)

FerretDB is a MongoDB-wire-compatible proxy backed by PostgreSQL (+ DocumentDB extension in v2). App drivers still talk “MongoDB protocol”, but semantics are not guaranteed 1:1 for every feature.

Key practical implications:

- driver-level compatibility is generally good for common CRUD,
- edge behavior differs for some commands/operators/options,
- migration success depends on **our exact query/transaction/index usage**.

---

## Repository-specific compatibility findings

### High risk areas

#### 1) Sessions and transaction semantics in scheduler/state machine

The jobs scheduler uses session-aware operations extensively, including explicit transaction usage.

Notable files:

- `interactive_ai/services/jobs/app/scheduler/state_machine.py`
- `interactive_ai/services/jobs/app/scheduler/job_repo.py`
- `interactive_ai/services/jobs/app/microservice/job_manager.py`
- `interactive_ai/libs/iai_core_py/iai_core/repos/base/session_repo.py`

Why this matters:

- scheduler correctness depends on atomic state transitions,
- any mismatch in transaction/session behavior can cause duplicates, stuck jobs, or inconsistent lifecycle states.

#### 2) `allowDiskUse=True` on aggregation paths

`allowDiskUse=True` is used in repository base classes and scheduler/policy paths.

Notable files:

- `interactive_ai/libs/iai_core_py/iai_core/repos/base/read_only_repo.py`
- `interactive_ai/libs/iai_core_py/iai_core/repos/base/session_repo.py`
- `interactive_ai/services/jobs/app/scheduler/state_machine.py`
- `interactive_ai/services/jobs/app/policies/policy.py`

Why this matters:

- if unsupported or ignored differently, heavy aggregations can fail or degrade unpredictably.

#### 3) TTL indexes used for core behavior

TTL is not just convenience here; it’s operationally important.

Notable files:

- `interactive_ai/libs/iai_core_py/iai_core/repos/leader_election_repo.py`
- `interactive_ai/services/dataset_ie/app/communication/repos/file_metadata_repo.py`

Why this matters:

- TTL behavior impacts lock expiry and cleanup reliability.

### Medium risk areas

- advanced aggregation operators/stages (`$lookup`, `$facet`, `$mergeObjects`, etc.) across repos,
- collation-based behavior (`Collation(...)`) for search/sorting,
- admin/user-management command compatibility in migration/bootstrap scripts,
- BSON UUID/Binary edge behavior used in import/export workflows.

---

## Direct MongoDB dependencies map (repos/services/ops)

This section lists code that directly depends on MongoDB APIs or MongoDB deployment primitives.

### A) Shared repository base layers (`iai_core`)

These are foundational and affect almost every service repo:

- `interactive_ai/libs/iai_core_py/iai_core/repos/base/mongo_connector.py`
- `interactive_ai/libs/iai_core_py/iai_core/repos/base/session_repo.py`
- `interactive_ai/libs/iai_core_py/iai_core/repos/base/database_client.py`
- `interactive_ai/libs/iai_core_py/iai_core/repos/base/{project_based_repo.py,dataset_based_repo.py,dataset_storage_based_repo.py,model_storage_based_repo.py,read_only_repo.py}`

### B) Core `iai_core` concrete repos (Mongo-backed)

- `interactive_ai/libs/iai_core_py/iai_core/repos/project_repo.py`
- `.../dataset_repo.py`
- `.../dataset_entity_repo.py`
- `.../dataset_storage_repo.py`
- `.../dataset_storage_filter_repo.py`
- `.../image_repo.py`
- `.../video_repo.py`
- `.../annotation_scene_repo.py`
- `.../annotation_scene_state_repo.py`
- `.../metadata_repo.py`
- `.../media_score_repo.py`
- `.../model_repo.py`
- `.../model_storage_repo.py`
- `.../model_test_result_repo.py`
- `.../evaluation_result_repo.py`
- `.../configurable_parameters_repo.py`
- `.../label_schema_repo.py`
- `.../task_node_repo.py`
- `.../active_model_state_repo.py`
- `.../compiled_dataset_shards_repo.py`
- `.../training_revision_filter_repo.py`
- `.../video_annotation_range_repo.py`
- `.../suspended_annotation_scenes_repo.py`
- `.../leader_election_repo.py`
- `.../metrics_reporting_project_repo.py`
- `.../metrics_reporting_model_storage_repo.py`

### C) Service-owned Mongo repos / direct Mongo usages

#### Jobs
- `interactive_ai/services/jobs/app/microservice/job_repo.py`
- `interactive_ai/services/jobs/app/scheduler/job_repo.py`
- `interactive_ai/services/jobs/app/policies/job_repo.py`
- `interactive_ai/services/jobs/app/microservice/job_manager.py` (explicit session usage)
- `interactive_ai/services/jobs/app/scheduler/state_machine.py` (state transitions persisted in Mongo)

#### Director
- `interactive_ai/services/director/app/storage/repos/{auto_train_activation_repo.py,partial_training_configuration_repo.py,project_configuration_repo.py,dataset_item_count_repo.py,dataset_item_labels_repo.py}`
- `interactive_ai/services/director/app/active_learning/storage/repos/{active_score_repo.py,active_suggestion_repo.py}`

#### Auto-train
- `interactive_ai/services/auto_train/app/repos/{auto_train_activation_repo.py,partial_training_configuration_repo.py}`

#### Resource
- `interactive_ai/services/resource/app/repos/ui_settings_repo.py`
- `interactive_ai/services/resource/app/usecases/query_builder.py` (aggregation-heavy reads across Mongo repos)
- `interactive_ai/services/resource/app/resource_management/resource_utils.py` (`DatabaseClient().is_running()`)

#### Dataset IE / Project IE / Visual Prompt
- `interactive_ai/services/dataset_ie/app/communication/repos/file_metadata_repo.py`
- `interactive_ai/services/project_ie/app/repos/upload_operation_repo.py`
- `interactive_ai/services/visual_prompt/app/repos/reference_feature_repo.py`

### D) Migration scripts and operations code

#### Migration runtime and admin scripts
- `interactive_ai/migration_job/migration_job/{run_migration.py,mongodb_upgrades_history.py,mongodb_create_service_user.py,utils.py}`
- `interactive_ai/data_migration/migration/utils/connection.py`
- `interactive_ai/data_migration/migration/scripts/*.py`

#### Compose / Helm / deployment wiring
- `docker-compose.yaml` (MongoDB service, env wiring, migration bootstrap)
- `infrastructure/compose-bootstrap.sh`
- `deploy/charts/impt/chart/charts/mongodb/*`
- `platform/services/config/chart/templates/config-map-impt-configuration.yaml`
- `deploy/charts/impt/chart/charts/secrets/templates/mongo-secret.yaml`
- service chart templates that inject Mongo env/init jobs (jobs/director/resource/dataset_ie/auto_train/project_ie/visual_prompt)
- `interactive_ai/migration_job/chart/templates/migration-job.yaml`

---

## Paired dependencies (must be migrated together)

Below are migration groups that should be treated as atomic units. Splitting them introduces high risk of runtime inconsistencies.

### 1) Jobs data plane (highest coupling)

**Group:** jobs scheduler + jobs microservice + jobs policy repos + scheduler Kafka handler.

Key files:

- `interactive_ai/services/jobs/app/scheduler/{state_machine.py,job_repo.py,kafka_handler.py}`
- `interactive_ai/services/jobs/app/microservice/{job_manager.py,job_repo.py}`
- `interactive_ai/services/jobs/app/policies/job_repo.py`

Why paired:

- all mutate/read the same `job` collection schema;
- scheduler locking and state transitions depend on shared atomic semantics.

### 2) Director ↔ Auto-train shared configuration collections

**Group:** director storage repos + auto_train repos for activation/config.

Key files:

- Director: `.../director/app/storage/repos/{auto_train_activation_repo.py,partial_training_configuration_repo.py}`
- Auto-train: `.../auto_train/app/repos/{auto_train_activation_repo.py,partial_training_configuration_repo.py}`

Why paired:

- both services read/write same collections and rely on matching schema/index/query behavior.

### 3) Resource query layer ↔ core dataset/media repos

**Group:** resource query usecases + underlying `iai_core` repos used by filters/scores.

Key files:

- `interactive_ai/services/resource/app/usecases/query_builder.py`
- `interactive_ai/libs/iai_core_py/iai_core/repos/{dataset_storage_filter_repo.py,annotation_scene_repo.py,dataset_repo.py,media_score_repo.py,...}`

Why paired:

- query logic assumes exact aggregation field shapes produced by those repos.

### 4) Shared `iai_core` base repo contract ↔ all service repos

**Group:** `mongo_connector/session_repo` + every repo inheriting from them.

Key files:

- `interactive_ai/libs/iai_core_py/iai_core/repos/base/{mongo_connector.py,session_repo.py,database_client.py}`
- plus all service-specific repo classes built on this contract.

Why paired:

- changing session/query/update semantics in base layer impacts every dependent service at once.

### 5) Migration job + data migration scripts + deployment bootstrap

**Group:** migration runtime scripts + Mongo user/bootstrap config + chart/compose secrets/env.

Key files:

- `interactive_ai/migration_job/migration_job/*`
- `interactive_ai/data_migration/migration/*`
- `docker-compose.yaml`, Mongo chart templates, Mongo secret/config templates

Why paired:

- schema upgrades, credentials, and startup ordering are coupled; partial migration breaks startup and data upgrades.

### 6) Event consumers that immediately persist to Mongo

**Group:** Kafka handlers + their target repos.

Key files:

- Jobs: `services/jobs/app/scheduler/kafka_handler.py`
- Director: `services/director/app/communication/kafka_handler.py`
- Dataset IE: `services/dataset_ie/app/communication/kafka_handler.py`
- Visual Prompt: `services/visual_prompt/app/services/kafka_handler.py`

Why paired:

- event payload handling and persistence schemas must remain aligned; mismatched migration causes dropped/invalid state updates.

---

## Fit assessment for single-node compose

### Pros

- keeps MongoDB driver model for services,
- can align with “all-open-source” stack goals,
- single-node deployments can be simpler operationally than full Mongo replica set management.

### Cons

- our app is **not** CRUD-only; scheduler and analytics rely on non-trivial Mongo behavior,
- replacing DB engine under these workflows can introduce subtle correctness bugs,
- migration cost is non-trivial relative to user-visible value unless licensing/ops constraints demand it.

---

## Recommendation

**Recommendation: do not directly switch compose defaults to FerretDB yet.**

Instead, run a staged validation and only move forward if compatibility tests pass on scheduler + training/test/inference lifecycles.

---

## Proposed migration plan

### Phase 0 — hard compatibility gate (must pass)

Create a compose profile with FerretDB backend and run:

- training lifecycle tests (including retries/cancel/recovery),
- model testing lifecycle,
- dataset import/export flows,
- inference cache and query/filter APIs,
- TTL-dependent flows (leader election, cleanup).

### Phase 1 — code hardening for portability

1. Wrap Mongo session/transaction usage behind a thin repository capability layer.
2. Remove/feature-gate unconditional `allowDiskUse=True` usage.
3. Add explicit integration tests for collation-sensitive queries.
4. Add capability checks at startup (e.g., TTL behavior sanity check).

### Phase 2 — dual profile rollout

- keep `mongodb` as default compose backend,
- add optional `ferretdb` compose profile for early adopters/internal validation,
- gather production-like telemetry and failure patterns.

### Phase 3 — decision checkpoint

Only consider default switch after:

- no correctness regressions in scheduler/job lifecycle,
- no critical query incompatibilities,
- acceptable performance under representative load.

---

## Minimal compose experiment (suggested)

For experimentation, run FerretDB + PostgreSQL (DocumentDB extension) under a dedicated compose profile and point app `MONGODB_URI` to FerretDB endpoint.

Do this in an isolated environment first; avoid in-place migration on active datasets until dump/restore and rollback are rehearsed.

---

## Open questions to resolve before any real cutover

1. Which exact transaction/session patterns are truly required vs legacy safety margins?
2. Are any production-critical APIs dependent on collation semantics?
3. Do our largest aggregation queries remain stable/performant without Mongo-native behavior?
4. Is TTL behavior sufficiently deterministic for leader election and cleanup workflows?

---

## References

- FerretDB docs: https://docs.ferretdb.io/
- Compatibility: https://docs.ferretdb.io/migration/compatibility/
- Migration guidance: https://docs.ferretdb.io/migration/migrating-from-mongodb/
- Pre-migration testing: https://docs.ferretdb.io/migration/premigration-testing/
