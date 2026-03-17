# Docker Compose Container Usage Report

Point-in-time snapshot of CPU and memory usage for currently running Compose services.

Captured on: 2026-03-17

Data sources:

- `docker compose ps`
- `docker stats --no-stream`
- `nproc && free -h`

> Note: `docker stats --no-stream` is an instantaneous sample. Use it for triage and relative comparisons, not long-term capacity planning.

---

## Host baseline

- CPU cores: **24**
- RAM: **62 GiB total**
- RAM used: **18 GiB**
- RAM available: **43 GiB**
- Swap: **8.0 GiB total**, **4.7 GiB used**

The non-trivial swap usage suggests recent memory pressure or previous heavy jobs.

---

## Per-service usage (Compose services)

| Service                              | CPU % |    Memory | Mem % | PIDs | Notes                                |
|--------------------------------------|------:|----------:|------:|-----:|--------------------------------------|
| kafka                                | 2.52% | 902.9 MiB | 1.41% |  117 | Highest memory consumer in stack     |
| interactive_ai_resource              | 1.61% | 326.4 MiB | 0.51% |  124 | Highest API-service memory footprint |
| s3                                   | 0.25% | 295.8 MiB | 0.46% |   30 | Heavy network/block I/O service      |
| interactive_ai_director              | 1.99% | 172.6 MiB | 0.27% |  110 | Moderate steady CPU                  |
| interactive_ai_dataset_import_export | 0.58% | 156.6 MiB | 0.24% |   56 | Active data transfer/import path     |
| interactive_ai_model_registration    | 0.08% | 142.3 MiB | 0.22% |   44 | Moderate memory, low CPU at idle     |
| interactive_ai_jobs                  | 1.07% | 131.8 MiB | 0.21% |   49 | Control-plane API                    |
| mongodb                              | 1.03% | 126.5 MiB | 0.20% |   72 | Stable baseline DB usage             |
| interactive_ai_jobs_scheduler        | 1.05% | 125.5 MiB | 0.20% |   43 | Queue/scheduler loop activity        |
| interactive_ai_jobs_policy           | 0.17% | 114.1 MiB | 0.18% |   51 | Low CPU, moderate memory             |
| interactive_ai_project_import_export | 0.22% | 110.9 MiB | 0.17% |   47 | Mostly idle in sample                |
| interactive_ai_auto_train            | 0.04% | 107.7 MiB | 0.17% |   50 | Low idle overhead                    |
| interactive_ai_jobs_worker           | 0.36% | 105.9 MiB | 0.17% |   47 | Will spike during jobs               |
| ovms                                 | 0.22% | 94.15 MiB | 0.15% |  130 | Inference server baseline            |
| db (postgres)                        | 0.01% | 48.01 MiB | 0.07% |    9 | Low usage in current workload        |
| openldap                             | 0.00% | 41.91 MiB | 0.07% |    5 | Low and stable                       |
| spicedb                              | 0.00% | 41.13 MiB | 0.06% |   28 | Low and stable                       |
| reverse-proxy                        | 0.02% | 39.93 MiB | 0.06% |   28 | Gateway overhead is low              |
| web                                  | 0.00% | 19.42 MiB | 0.03% |   25 | Very low                             |
| platform_auth_proxy                  | 0.06% | 14.33 MiB | 0.02% |   13 | Very low                             |
| platform_account                     | 0.00% | 14.28 MiB | 0.02% |   21 | Very low                             |
| interactive_ai_media                 | 0.02% | 13.33 MiB | 0.02% |   27 | Very low in this sample              |
| dex                                  | 0.30% | 10.69 MiB | 0.02% |   16 | Very low                             |
| interactive_ai_inference_gateway     | 0.01% | 10.38 MiB | 0.02% |   24 | Very low                             |
| redis                                | 0.98% |  3.98 MiB | 0.01% |    6 | CPU can spike with queue load        |

---

## Quick findings

1. **No immediate memory saturation** on the host (43 GiB available).
2. **Kafka dominates RAM usage** among services (~0.9 GiB).
3. Main API services are generally in the **100–330 MiB** range at this moment.
4. Current CPU is modest across services; no clear CPU bottleneck in this sample.
5. **Swap usage is high** relative to current container RAM usage, likely from prior heavy operations (builds/training).

---

## Why `resource` and `director` are heavier

Compared with lighter API services (for example `interactive_ai_jobs`), these two services have a heavier startup/runtime profile.

### `interactive_ai_resource`

- Loads heavier media-processing dependencies (notably OpenCV/numpy/Pillow) via transitive imports.
- Initializes multiple Kafka consumers and background threads at startup.
- Uses media-related in-memory caches (video frame/cache paths from shared media utils).
- Current live process had a high thread count (`Threads: 124`) and RSS around `410 MiB`.

### `interactive_ai_director`

- Loads active-learning stack including `scikit-learn`/`scipy` ecosystem at import time.
- Initializes more Kafka handlers than most API services.
- Keeps additional in-process scheduler/debouncer state for training automation workflows.
- Current live process had high thread count (`Threads: 110`) and RSS around `259 MiB`.

### Baseline comparison (`interactive_ai_jobs`)

- Lower dependency footprint at rest.
- Fewer always-on background loops.
- Lower thread count (`Threads: 24`) and lower RSS profile in the same snapshot.

---

## Application image size overview

Image size can be interpreted in two ways:

1. **Naive sum across running services** (counts repeated image tags multiple times)
2. **Unique-image total** (counts each image tag once; better estimate for local storage impact)

From the current running stack:

- Naive service-image sum: **~21.11 GiB**
- Unique-image total (16 image tags): **~5.45 GiB**

> The unique total is the more meaningful number for disk footprint. Actual on-disk Docker usage still depends on shared layers across tags.

### Largest currently-used images

| Image | Size |
|---|---:|
| `ghcr.io/geti/interactive_ai/api:main` | ~1.74 GiB |
| `mongo:7.0` | ~829 MiB |
| `ghcr.io/geti/interactive_ai/inference_gateway:main` | ~541 MiB |
| `openvino/model_server:2025.0` | ~441 MiB |
| `postgres:14.13` | ~402 MiB |
| `apache/kafka:3.7.1` | ~372 MiB |

### Related Docker host footprint

At capture time:

- `docker system df` images total: **124.3 GB**
- Reclaimable images: **118.2 GB (95%)**
- Build cache: **73.65 GB**

This indicates large historical build/cache accumulation beyond the active Compose stack.

### Estimated user download budget

Yes — the **unique-image total includes infrastructure images** (Kafka, MongoDB,
Redis, Traefik, S3, etc.) because it is derived from running Compose services.

For planning, treat these as rough budgets (compressed pull size will differ by registry/layer reuse):

- **Core running stack (current compose set): ~5.45 GiB**
- **+ training workflows + GPU trainer (`otx_v2_gpu`)**: add ~19.1 GiB (total ~24.5 GiB)
- **+ XPU trainer (`otx_v2_xpu`) as well**: add ~8.0 GiB (total ~32.5 GiB)

So a user who wants "everything including training runtimes" should plan for roughly **25–33 GiB** of image footprint.

---

## Suggestions to improve resource usage

### 1) Add Compose memory/CPU guardrails (recommended)

Set explicit limits/reservations for high-variance services to prevent one service from starving others:

- `interactive_ai_jobs_worker`
- `interactive_ai_jobs_scheduler`
- `interactive_ai_resource`
- `kafka`
- `ovms`

This improves predictability under heavy train/import bursts.

### 2) Tune Kafka JVM heap

Kafka is the largest memory consumer in this snapshot. Compose supports JVM heap tuning through `KAFKA_HEAP_OPTS` (in `.env`) with a conservative default:

```bash
KAFKA_HEAP_OPTS=-Xms256m -Xmx512m
```

Suggested tuning tiers:

- constrained dev host: `-Xms128m -Xmx384m`
- default local/dev: `-Xms256m -Xmx512m`
- heavier local load: `-Xms512m -Xmx1g`

Apply and validate:

```bash
docker compose up -d --force-recreate kafka init-kafka-topics
docker stats --no-stream
```

Avoid setting `Xmx` too low (<256m) unless validated with your expected event load.

### 3) Scale worker concurrency/queue isolation deliberately

You already hit queue starvation behavior earlier. Keep long scheduler timeouts (already configured), and consider:

- dedicated queue/worker for import/export jobs,
- separate worker for train/optimize workloads.

This reduces long-job interference and improves perceived responsiveness.

### 4) Track trends, not just snapshots

Add lightweight periodic collection during a representative workflow (import + train + optimize), then compute p50/p95 peaks per service. Point-in-time values can hide spikes.

### 5) Manage host swap pressure

Because swap is already in use:

- avoid parallel heavy image builds during active training,
- periodically prune stale Docker artifacts,
- if needed, increase host RAM/swap policy tuning for dev machines.

### 6) Lower image footprint for users (download/storage)

1. **Use compose profiles for optional workloads**
   - Keep core platform in default profile.
   - Move trainer/workflow services (`interactive_ai_workflows_*`, `otx_v2_*`) to optional profiles so users only pull them when needed.

2. **Avoid pulling both GPU and XPU trainer images by default**
   - Pull only the selected accelerator runtime (`TRAINER_RUNTIME_ACCELERATOR`).
   - Document one-liner for switching accelerators and pulling on demand.

3. **Publish slim/dev variants where feasible**
   - Example: lighter local-only images without optional toolchains/debug packages.
   - Keep full images for CI/release parity.

4. **Separate rare workflow images from default startup docs**
   - Make "minimal stack" and "train-capable stack" explicit in getting-started docs.

5. **Continuously prune unreferenced images/cache in dev environments**
   - `docker image prune -f`
   - `docker builder prune -f`
   - This does not reduce first-time pull size, but prevents local disk growth.

---

## Optional follow-up commands

```bash
# Live view
docker stats

# Focus only compose containers (example filter by prefix)
docker stats --no-stream $(docker ps --format '{{.Names}}' | grep '^geti-')

# Per-service state and restarts
docker compose ps

# Disk usage pressure
docker system df
```

### Re-generate this report data snapshot

```bash
# 1) Running services
docker compose ps

# 2) Point-in-time container CPU/memory
docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}\t{{.BlockIO}}\t{{.PIDs}}'

# 3) Host capacity baseline
nproc
free -h

# 4) Image sizes used by running compose services (service -> image -> size)
docker compose ps --format json | python3 - <<'PY'
import json, sys, subprocess
rows = [json.loads(l) for l in sys.stdin if l.strip()]
seen = {}
for r in rows:
    img = r["Image"]
    if img not in seen:
        seen[img] = int(subprocess.check_output(["docker","image","inspect",img,"--format","{{.Size}}"], text=True).strip())
for r in sorted(rows, key=lambda x: x["Service"]):
    print(f"{r['Service']}\t{r['Image']}\t{seen[r['Image']]}")
print("UNIQUE_IMAGE_TOTAL_BYTES", sum(seen.values()))
print("NAIVE_SERVICE_IMAGE_TOTAL_BYTES", sum(seen[r['Image']] for r in rows))
PY

# 5) Docker-wide storage pressure
docker system df
```
