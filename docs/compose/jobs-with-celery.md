# Jobs in Compose with Celery

This document explains how job execution works in compose mode after moving away from local Flyte/Kubernetes.

## Short version

- The workflow images (`interactive_ai_workflows_*`, `interactive_ai_workflows_otx_v2_*`) are **still used**.
- They are no longer required to be always-on services.
- Instead, jobs are coordinated by the jobs control plane and executed by Celery workers.

## Main services and responsibilities

In compose mode, the jobs stack is split into distinct roles:

### `interactive_ai_jobs_policy`

Policy loop / queue admission service.

It continuously evaluates submitted jobs and applies scheduling policy, such as:

- max running jobs limits,
- duplicate handling,
- GPU-related schedulability checks.

Its main outcome is moving jobs from `SUBMITTED` to `READY_FOR_SCHEDULING` when policy allows.

It does **not** execute workflow logic.

### `interactive_ai_jobs_scheduler`

Orchestration and state-machine service.

It:

- picks `READY_FOR_SCHEDULING` jobs,
- dispatches execution to Celery,
- consumes progress/update events,
- drives job/step state transitions,
- publishes final state and metadata updates.

### `interactive_ai_jobs_worker`

Execution service (Celery worker).

It runs job execution tasks. For supported job types, it launches the appropriate workflow runtime image/container on demand (dataset/project IE, model test, train/optimize stages, trainer runtime, etc.).

So worker = where actual job work happens.

## Where workflow images fit now

Previously, workflow-related containers were often thought of as separate always-running app services.

Now they are primarily **runtime images** referenced by worker env vars, for example:

- `DATASET_IE_WORKFLOW_IMAGE`
- `PROJECT_IE_WORKFLOW_IMAGE`
- `MODEL_TEST_WORKFLOW_IMAGE`
- `TRAIN_WORKFLOW_IMAGE`
- `OPTIMIZE_WORKFLOW_IMAGE`
- trainer runtime image vars

The worker starts these as needed per job/stage instead of requiring permanently running per-workflow services.

## Scaling guidance

If you need higher throughput:

- scale **workers** first (most direct impact on execution concurrency),
- scale **scheduler** if orchestration/event handling becomes a bottleneck,
- scale **policy** only if policy loop throughput becomes limiting (usually lighter workload).

In practice, worker scaling is typically the primary lever.
