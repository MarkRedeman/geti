# What Is Different In This Geti Version

This repository now runs a **compose-first, single-host** Geti runtime.

The previous setup used Kubernetes + Flyte and a larger microservice graph for Interactive AI. The current setup removes that orchestration stack and simplifies both runtime and codepaths.

## Quick Summary

- **Kubernetes removed** from local/runtime architecture.
- **Flyte replaced** with Celery-driven local execution.
- **Interactive AI service graph reduced**, with multiple previously separate components merged or run from a shared API image/runtime.
- **Compose-only codepaths inlined**, with most dual-mode (K8s vs non-K8s) branching removed.
- **Memory and disk footprint reduced** via fewer services, fewer heavy dependencies, and less orchestration overhead.

## Before vs Now

| Area                            | Old (K8s/Flyte era)                | Current (Compose-first era)                                  |
|---------------------------------|------------------------------------|--------------------------------------------------------------|
| Orchestration                   | Kubernetes                         | Docker Compose                                               |
| Workflow engine                 | Flyte                              | Celery + local workflow runner                               |
| Job execution model             | Remote workflow orchestration      | Local Docker/Celery execution with scheduler-owned lifecycle |
| Interactive AI deployment shape | More split microservices           | Consolidated services/shared runtime image                   |
| Secrets/config retrieval        | K8s APIs/objects                   | Environment-driven runtime client shims                      |
| Infra dependencies              | Helm/chart and K8s API assumptions | Compose-native bootstrap and runtime                         |

## Noteworthy Changes

### 1) Orchestration and scheduling model

- Workflow execution no longer depends on Flyte services.
- Jobs are scheduled by the jobs scheduler and executed locally through Celery and Docker.
- Workflow lifecycle events now use compose-local event handling and topic conventions.

### 2) Compose-only codepaths (no dual-runtime drift)

- Many `if kubernetes` / `if compose` branches were removed.
- Scheduler/policy behavior is now directly compose-centric instead of toggled by runtime mode.
- Legacy K8s-only service modules and tests were removed where no longer meaningful.

### 3) Microservice consolidation and runtime simplification

- Several Interactive AI responsibilities now run through fewer service containers.
- Shared runtime images reduce duplicate dependency layers and startup overhead.
- Startup surface area is smaller, which lowers operational complexity.

### 4) Platform service adapters switched from K8s APIs to runtime shims

- User directory and observability paths that previously referenced `k8s_client` behavior are now runtime-client style adapters.
- Secret/config-map access patterns are environment-backed for compose use.
- K8s-specific client modules were removed or replaced with explicit compose stubs/no-ops where appropriate.

### 5) Dependency and repository cleanup

- Flyte/K8s-era dependencies were removed from affected services/workflows.
- Dead K8s/Flyte modules, stale comments, and obsolete tests were pruned or renamed.
- Naming was updated across many workflow/job files to reflect runtime behavior instead of legacy Flyte/K8s terms.

### 6) Resource behavior for trainer/workflow containers

- Shared-memory behavior was hardened for local workload stability (especially optimization/training paths).
- Runtime supports host IPC mode and explicit shm sizing for heavy DataLoader-style workloads.

### 7) Bootstrap/infrastructure simplification

- Local startup flow is oriented around compose initialization and service readiness.
- Legacy Helm/deployment scaffolding assumptions are no longer part of the active local runtime path.

## Practical Benefits

- Faster local bring-up and easier debugging.
- Lower idle memory usage and less storage consumed by orchestration components.
- Smaller cognitive load when navigating job execution code.
- Fewer environment-specific failure modes for local development.

## Trade-offs To Be Aware Of

- This runtime is intentionally optimized for compose/local single-host operation, not Kubernetes cluster features.
- No K8s-native autoscaling/scheduling semantics in this mode.
- Some functionality now uses explicit compose stubs/no-ops where K8s integrations used to exist.

## Bottom Line

This version of Geti is a deliberate shift from a cluster-first architecture to a **lean, compose-first architecture** focused on reducing memory/disk consumption, simplifying operations, and making local development and iteration significantly easier.

## Migration Timeline (High Level)

The transition happened in stages, each reducing complexity and preserving behavior for local development:

1. **Compose-first direction established**
   - Local runtime became the primary target.
   - Kubernetes-only deployment assumptions stopped being the default development path.

2. **K8s/Flyte orchestration paths removed from workflows/jobs**
   - Workflow execution moved to Celery + local runner behavior.
   - Dual-runtime branches (K8s vs compose) were collapsed into compose-native logic.

3. **Interactive AI service consolidation**
   - Multiple split services were combined into fewer runtime processes/images.
   - Startup orchestration and inter-service wiring were simplified.

4. **Platform adapters converted to runtime/environment model**
   - K8s client-style access in user directory and observability was replaced by runtime client shims.
   - Compose-compatible stubs/no-ops replaced unsupported cluster-only operations.

5. **Dependency and naming cleanup pass**
   - Legacy Flyte/K8s package references were removed.
   - Legacy naming in code/docs/tests was normalized toward runtime/compose terminology.

6. **Runtime stability hardening**
   - Trainer/workflow container memory behavior was tuned for local heavy workloads.
   - IPC/shared-memory handling was made explicit and configurable.

7. **Current state**
   - A single, consistent compose-first execution model.
   - Lower resource usage, fewer moving parts, and clearer operational behavior for local environments.
