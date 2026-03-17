# Docker build performance analysis (compose)

This document summarizes a full analysis of Docker build performance for:

- all service/workflow Dockerfiles,
- `docker-compose.yaml` build configuration,
- `pyproject.toml` / `uv.lock` dependency patterns.

It also includes a recommendation on whether to merge multiple `interactive_ai_*` services.

---

## Executive summary

Your slow build time is mostly caused by a few structural issues, not one single Dockerfile.

Highest-impact causes:

1. **duplicate image builds in compose** (same image built multiple times, e.g. jobs variants),
2. **network-heavy build steps repeated across services** (notably repeated OTX `git clone`),
3. **cache-busting Dockerfile ordering** in many Python services (`COPY app` before `uv sync`),
4. **lack of persistent buildx cache** (`cache_from/cache_to` not configured),
5. **heavy trainer images always in the default build graph**.

If you implement only the top 4 recommendations, you should see a large reduction in build time (often from “many minutes” to “few minutes”, and incremental builds to near-seconds for unchanged deps).

---

## 1) Compose-level build bottlenecks

### 1.1 Same image built multiple times (critical)

`interactive_ai_jobs_scheduler`, `interactive_ai_jobs_policy`, and `interactive_ai_jobs_worker` use the same image name and effectively same build context/config.

Current effect:

- repeated build invocations for one logical image,
- avoidable dependency install and layer creation overhead.

Recommendation:

- keep `build:` only on one canonical jobs service (for example `interactive_ai_jobs_scheduler`),
- remove `build:` from the other three and keep `image:` only.

---

### 1.2 OTX templates fetched repeatedly in multiple Dockerfiles (critical)

Several Dockerfiles clone training_extensions independently during build (director/resource/auto_train + workflows train/optimize/dataset_ie patterns).

Recommendation:

- centralize OTX fetch into one dedicated image/stage (you already have an `otx` build service),
- consume `/model_templates` via `COPY --from=...` in downstream Dockerfiles,
- remove per-service `git clone` steps.

---

### 1.3 No remote/persistent build cache strategy (high)

`docker-compose.yaml` build sections do not define buildx cache import/export.

Recommendation:

- add `cache_from`/`cache_to` (registry or local cache),
- in CI, prefer registry-backed cache (`mode=max`) per service image.

---

### 1.4 Broad `additional_contexts` invalidating many builds (high)

Several services include broad contexts like `libs=./libs`, which invalidates caches for many unrelated services when any file under `libs` changes.

Recommendation:

- narrow contexts to required subpaths per service,
- keep interface-specific contexts (like inference_gateway already does) as the preferred pattern.

---

### 1.5 Heavy trainer images always part of standard build path (high)

`interactive_ai_workflows_otx_v2_gpu` / `_xpu` are expensive to build and should not rebuild in normal app iteration.

Recommendation:

- default to prebuilt trainer images for day-to-day compose use,
- gate local trainer rebuild behind an explicit profile/target.

---

## 2) Dockerfile-level issues and fixes

## 2.1 Dependency install ordering (critical)

Many Python Dockerfiles copy source code before `uv sync --frozen`.

Bad cache pattern:

1. `COPY app/ ...`
2. `uv sync ...`

Any app code change invalidates the dependency layer.

Recommended pattern:

1. set `WORKDIR`
2. provide only `pyproject.toml` + `uv.lock`
3. run `uv sync --frozen --no-dev --no-editable` with cache mount
4. copy app source last

---

### 2.2 Missing BuildKit syntax/cache mounts in many Python Dockerfiles (high)

Go Dockerfiles already use BuildKit syntax; many Python ones do not.

Recommendation:

- add `# syntax=docker/dockerfile:1.7` to Python Dockerfiles,
- for apt layers use cache mounts (`/var/cache/apt`, `/var/lib/apt`) to reduce repeated downloads.

---

### 2.3 Repeated network tool install in Go builds (medium)

Some Go Dockerfiles call `go install` tools (e.g. `go-licenses`) in source-coupled layers.

Recommendation:

- move tool install to dedicated reusable tool stage,
- keep source-changing layers separate from tool installation.

---

### 2.4 XPU trainer layer inefficiency (medium)

XPU trainer currently does frozen sync then torch uninstall/reinstall from another index.

Recommendation:

- split XPU variant lockfile/dependency definition so frozen sync already resolves XPU torch,
- at minimum add uv cache mount for reinstall step.

---

### 2.5 Cleanup / no-op instructions (low)

- inconsistent apt cleanup conventions,
- `RUN ulimit ...` in Dockerfile is not persistent at runtime.

Recommendation:

- normalize apt cleanup strategy,
- remove no-op runtime-limit Dockerfile instructions and configure ulimits at runtime instead.

---

## 3) `pyproject.toml` analysis (build-impact focused)

### 3.1 Lockfile status

Good news: pyproject/lock coverage is strong (no major lockfile gaps in service packages).

### 3.2 Major dependency duplication / skew

Key findings:

- `openvino-model-api` appears in multiple places with **different versions** (reduces cross-image wheel cache reuse).
- `opencv-python-headless` is duplicated across core libs with mixed constraint styles.
- `uvicorn` versions are fragmented (including older outliers), preventing broader cache sharing and increasing maintenance risk.
- some packages include heavy test-oriented deps in runtime dependency sets (image bloat).

Recommendation:

1. align shared heavy dependencies (`openvino-model-api`, `opencv`, `uvicorn`) where possible,
2. move test-only packages to dev groups,
3. keep internal lib versions aligned across services to maximize wheel/layer reuse.

### 3.3 Editable local path dependencies and cache invalidation

Many services depend on local editable path packages from `libs` / `interactive_ai/libs`.

Effect:

- tiny shared-lib changes can invalidate dependency layers in many service images.

Recommendation:

- medium term: publish internal wheels and install by version,
- short term: narrow copied contexts to only needed local packages per service.

---

## 4) Prioritized improvement plan

### Phase A (fast, high ROI)

1. deduplicate jobs image build in compose,
2. reorder dependency layers in Python Dockerfiles,
3. add buildx cache import/export,
4. make trainer image builds opt-in.

### Phase B (structural)

5. centralize OTX fetch/templates as a shared stage/image,
6. narrow `additional_contexts` usage,
7. align heavy shared dependency versions in pyproject files.

### Phase C (polish)

8. normalize apt cleanup + BuildKit syntax across all Dockerfiles,
9. remove no-op Dockerfile instructions,
10. clean test-only runtime dependencies.

---

## 5) Extra: should we merge multiple `interactive_ai_*` services?

Short answer: **partially yes, full monolith no**.

### Why merging everything is risky

- larger blast radius (one crash affects many API domains),
- jobs worker security boundary (`root` + docker socket) should stay isolated,
- dependency conflicts across currently separate services become harder,
- independent deploy/restart boundaries are lost.

### What can be merged safely for single-node compose

A practical middle ground:

1. **Merge-ish API group** (same container, separate processes):
   - `resource` + `director` + `dataset_ie` + `project_ie`
2. **Keep jobs worker isolated** (`interactive_ai_jobs_worker`) due to docker-socket/root concerns.
3. **Keep heavy/specialized services isolated**:
   - `visual_prompt` (heavy model memory),
   - `model_registration` (OVMS fs permissions/sync concerns),
   - `inference_gateway` and `media` (Go services, already lean).

This can reduce baseline RAM/CPU overhead for single-node without taking full-monolith risk.

---

## 6) Concrete next steps

If you want to execute this incrementally, the highest-confidence first PR is:

1. compose dedup for jobs build,
2. Python Dockerfile dependency-layer reordering for 2-3 heaviest services first (`jobs`, `director`, `resource`),
3. buildx cache wiring in CI.

Then measure build time deltas before moving to larger structural changes.


## Physical AI studio example

This section contains an example of another applicatoin's pyproject.toml, dockerfile and docker compose.
These have been heavily optimized making it so that if the user makes an application change (i.e. in `application/backend`) then we don't have to wait for any gpu runtime or package updates when rebuilding. Instead rebuild will focus on actual application changes.


```toml
[project]
name = "physical-ai-studio"
version = "1.0.0"
description = "Physical AI Studio server"
requires-python = ">=3.12"

dependencies = [
  "opencv-python",
  "cv2-enumerate-cameras",
  'harvesters; sys_platform != "darwin"',
  "fastapi[standard]",
  "physicalai-train[pi0,smolvla]",
  "lerobot[feetech]==0.4.4",
  "numpy",
  "websockets",
  'pyrealsense2-macosx; sys_platform == "darwin"',
  'pyrealsense2; sys_platform != "darwin"',
  "aiortc>=1.13.0",
  "pydantic-settings>=2.10.1",
  "sqlalchemy>=2.0.43",
  "aiosqlite~=0.21",
  "alembic>=1.16.5",
  "click>=8.3.0",
  "FrameSource>=0.2.2",
  "loguru>=0.7.3",
  "greenlet>=3.2.4",
  "tenacity>=9.1.2",
  "aiofiles>=25.1.0",
  "types-aiofiles>=25.1.0.20251011",
  "trossen-arm==1.9.0"
]

[project.optional-dependencies]
cpu = [
    "torch<2.11",
    "torchvision",
]
cuda = [
    "torch<2.11",
    "torchvision",
]
xpu = [
    "torch<2.11",
    "torchvision",
    "pytorch-triton-xpu ; sys_platform == 'linux' or sys_platform == 'win32'",
]

tests = [
    "pytest",
]

# --- PyTorch index configuration ---
# torch is a transitive dependency (via lightning, lerobot) that defaults to
# PyPI's fat CUDA wheel on Linux. Source routing here directs uv to fetch
# torch/torchvision from the correct hardware-specific PyTorch index.
# This must be declared in the consumer project because uv does not
# propagate [tool.uv.sources] from path dependencies (uv #14675).
#
# PyPI is listed first as a named default index so that it takes priority
# over the non-explicit pytorch-xpu index in unsafe-best-match resolution.
# Without this, the XPU index can shadow PyPI packages with incompatible
# wheels (e.g. markupsafe cp314-only, see uv #9647).
[[tool.uv.index]]
name = "pypi"
url = "https://pypi.org/simple"

[[tool.uv.index]]
name = "pytorch-cpu"
url = "https://download.pytorch.org/whl/cpu"
explicit = true

[[tool.uv.index]]
name = "pytorch-cu128"
url = "https://download.pytorch.org/whl/cu128"
explicit = true

[[tool.uv.index]]
name = "pytorch-xpu"
url = "https://download.pytorch.org/whl/xpu"
explicit = false

[tool.uv.sources]
FrameSource = { git = "https://github.com/ArendJanKramer/FrameSource.git", rev = "c3023714ceaa2bf50cf04e1d2861d9fe7cd01422" }
physicalai-train = { path = "../../library", editable = true }
torch = [
    { index = "pytorch-cpu", extra = "cpu" },
    { index = "pytorch-cu128", extra = "cuda" },
    { index = "pytorch-xpu", extra = "xpu" },
]
torchvision = [
    { index = "pytorch-cpu", extra = "cpu" },
    { index = "pytorch-cu128", extra = "cuda" },
    { index = "pytorch-xpu", extra = "xpu" },
]
pytorch-triton-xpu = [{ index = "pytorch-xpu", extra = "xpu" }]

[dependency-groups]
dev = [
  "ruff~=0.11.2",
]
lint = [
  "ruff~=0.11.2",
  "mypy~=1.17",
]
all = [
  "ruff~=0.11.2",
  "mypy~=1.17",
]

[tool.uv]
default-groups = ["all"]
# The pytorch-xpu index is non-explicit (explicit = false) because
# transitive deps like pytorch-triton-xpu only exist on the XPU index.
# unsafe-best-match is required because the XPU index also hosts stale
# copies of common packages (e.g. cmake 3.25.0); with first-match uv
# would stop at the XPU index and miss the newer PyPI version.
#
# To prevent the XPU index from providing incompatible wheels for
# common packages (e.g. markupsafe cp314-only, see uv #9647), PyPI
# is listed as a named index with higher priority above.
index-strategy = "unsafe-best-match"
conflicts = [
    [
        { extra = "cpu" },
        { extra = "cuda" },
        { extra = "xpu" },
    ],
]

# ============================================================================ #
# RUFF CONFIGURATION                                                           #
# ============================================================================ #
[tool.ruff]
# Extend shared configuration from root
extend = "../../pyproject.toml"

# Disable preview mode for backend (inherited as true from root)
preview = false

# Backend-specific source directories
src = ["src"]

# Backend-specific excludes
extend-exclude = [".venv*"]

[tool.ruff.lint]
# Backend uses a subset of rules (different from library's ALL)
select = [
    "ARG", "E", "F", "I", "N", "UP", "YTT", "ASYNC", "S", "COM", "C4", "FA",
    "PIE", "PYI", "Q", "RSE", "RET", "SIM", "TID", "TC", "PL", "RUF", "C90",
    "D103", "ANN001", "ANN201", "ANN205", "FAST"
]

ignore = [
    "N801", "N805", "N806", "N807", "N818", "COM812", "RET503", "SIM108",
    "SIM105", "PLR2004", "RUF010", "TC001", "RUF012"
]

fixable = ["ALL"]
dummy-variable-rgx = "^(_+|(_+[a-zA-Z0-9_]*[a-zA-Z0-9]+?))$"

[tool.ruff.lint.per-file-ignores]
"*test*.py" = ["S", "ANN", "D", "ARG", "PLR"]

[tool.ruff.lint.isort]
split-on-trailing-comma = false

[tool.ruff.lint.pylint]
max-args = 7


# ============================================================================ #
# MYPY CONFIGURATION                                                           #
# ============================================================================ #
[tool.mypy]
python_version = "3.12"
ignore_missing_imports = true
show_error_codes = true

[tool.pytest.ini_options]
addopts = ["--strict-markers", "--strict-config", "--showlocals", "-ra"]
testpaths = "tests"
pythonpath = "src"
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "requires_download: marks tests that require downloading external datasets",
    "integration: marks tests as integration tests",
]
filterwarnings = [
  "ignore:XPU device count is zero!:UserWarning",
  "ignore:This process.*is multi-threaded:DeprecationWarning", # using actual queues in tests
]
```


```Dockerfile
# syntax=docker/dockerfile:1@sha256:b6afd42430b15f2d2a4c5a02b919e98a525b785b1aaff16747d2f623364e39b6

# Build arguments
ARG PYTHON_VERSION=3.12

# ===========================================================================
# Stage 1: Clone Geti UI packages and URDF robot models
# ===========================================================================
FROM node:24-alpine3.22@sha256:76db75ca7e7da9148ae42c92d9be12d12a8d7b03e171f18339355d8078d644a0 AS ui-packages

WORKDIR /home/app/web_ui/
RUN apk add --no-cache git
COPY --link ./application/ui/package.json ./
RUN npm run clone-geti-ui-packages

# Clone URDF files
RUN npm run clone-so101
RUN npm run clone-widowx

# ===========================================================================
# Stage 2: Build Web UI
# ===========================================================================
FROM node:24-alpine3.22@sha256:76db75ca7e7da9148ae42c92d9be12d12a8d7b03e171f18339355d8078d644a0 AS web-ui

WORKDIR /home/app/web_ui/

COPY --link application/ui/package.json ./
COPY --link application/ui/package-lock.json ./
COPY --from=ui-packages /home/app/web_ui/packages/ /home/app/web_ui/packages/
COPY --from=ui-packages /home/app/web_ui/public/ /home/app/web_ui/public/
RUN npm ci --audit=false --ignore-scripts

COPY --link application/ui/tsconfig.json ./
COPY --link application/ui/rsbuild.config.ts ./
COPY --link application/ui/src/ src/

RUN npm run build

# ===========================================================================
# Stage 3: App source assembly
#
# Collects all non-.venv application files into a single layer so that
# the final runtime stages can COPY them in one instruction. Built in
# parallel with the Python builder stages (no dependency between them).
# ===========================================================================
FROM scratch AS app-source

# Root workspace manifests (needed by uv run for workspace resolution)
COPY --link pyproject.toml uv.lock LICENSE README.md /app/

# Library source + manifest (needed by uv run for hatchling version)
COPY --link --from=libs ./src /app/library/src
COPY --link --from=libs ./LICENSE /app/library/LICENSE
COPY --link --from=libs ./README.md /app/library/README.md
COPY --link --from=libs ./pyproject.toml /app/library/pyproject.toml

# Backend source, entrypoint, and manifests
COPY --link application/backend/src /app/application/backend/src
COPY --link application/backend/pyproject.toml application/backend/uv.lock \
    /app/application/backend/
COPY --link application/backend/run.sh /app/application/backend/run.sh

# Built UI assets
COPY --link --from=web-ui /home/app/web_ui/dist /app/application/ui/

# ===========================================================================
# Stage 4: Python builder base
#
# Contains build-time-only packages (g++, build-essential, etc.)
# and dependency manifests — but NOT backend source code or UI assets.
# This separation ensures that source-only changes do not invalidate
# the expensive uv sync layers in the device-specific builders below.
# ===========================================================================
FROM python:${PYTHON_VERSION}-slim@sha256:f3fa41d74a768c2fce8016b98c191ae8c1bacd8f1152870a3f9f87d350920b7c AS builder-base

COPY --from=docker.io/astral/uv:0.10.4@sha256:4cac394b6b72846f8a85a7a0e577c6d61d4e17fe2ccee65d9451a8b3c9efb4ac /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0

# Build-time system dependencies (not shipped in final image)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        g++ \
        build-essential \
        libclang-dev \
        libusb-1.0-0-dev \
        pkg-config \
        git \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only dependency manifests — no backend source or UI assets.
COPY --link pyproject.toml uv.lock LICENSE README.md ./

# Library source is needed for hatchling to resolve the dynamic version
# of the physicalai-train path dependency during uv sync.
COPY --link --from=libs ./src /app/library/src
COPY --link --from=libs ./LICENSE /app/library/LICENSE
COPY --link --from=libs ./README.md /app/library/README.md
COPY --link --from=libs ./pyproject.toml /app/library/pyproject.toml

# Backend manifests only (not src/ or run.sh) — sufficient for dep resolution.
COPY --link application/backend/pyproject.toml application/backend/uv.lock \
    /app/application/backend/

WORKDIR /app/application/backend

# Install hardware-independent dependencies (FastAPI, SQLAlchemy, etc.)
# first so this layer is shared across all device-specific builders.
# --no-install-project: skip building the backend wheel (source not present).
RUN --mount=type=cache,id=uv-base,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable --no-install-project

# ===========================================================================
# Stage 4a: CPU builder
# ===========================================================================
FROM builder-base AS builder-cpu

RUN --mount=type=cache,id=uv-cpu,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable --no-install-project --extra cpu

# ===========================================================================
# Stage 4b: XPU builder
# ===========================================================================
FROM builder-base AS builder-xpu

RUN --mount=type=cache,id=uv-xpu,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable --no-install-project --extra xpu

# ===========================================================================
# Stage 4c: CUDA builder
# ===========================================================================
FROM builder-base AS builder-cuda

RUN --mount=type=cache,id=uv-cuda,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable --no-install-project --extra cuda

# ===========================================================================
# Stage 5: Runtime base — shared across all hardware targets
#
# Provides the non-root user, common runtime libraries, environment
# variables, and directory structure. Healthcheck is defined in
# docker-compose.yaml (not here) so it can reference runtime PORT.
# ===========================================================================
FROM python:${PYTHON_VERSION}-slim@sha256:f3fa41d74a768c2fce8016b98c191ae8c1bacd8f1152870a3f9f87d350920b7c AS runtime-base

# OCI image metadata
ARG GIT_SHA=unknown
LABEL org.opencontainers.image.source="https://github.com/open-edge-platform/physical-ai-studio" \
      org.opencontainers.image.description="Physical AI Studio is an end-to-end framework for teaching robots to perform tasks through imitation learning from human demonstrations" \
      org.opencontainers.image.revision="${GIT_SHA}"

# uv is needed at runtime for `uv run` in run.sh
COPY --from=docker.io/astral/uv:0.10.4@sha256:4cac394b6b72846f8a85a7a0e577c6d61d4e17fe2ccee65d9451a8b3c9efb4ac /uv /uvx /bin/

# Non-root user — override at build time to match host UID/GID for
# bind-mounted volumes (e.g. calibration data, HuggingFace cache).
ARG APP_UID=1000
ARG APP_GID=1000

RUN groupadd --gid "${APP_GID}" appuser \
    && useradd --uid "${APP_UID}" --gid "${APP_GID}" --create-home appuser

# Common runtime system dependencies (OpenCV, USB access, video decoding)
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libgl1 \
        libglib2.0-0 \
        libusb-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create directories for mounted volumes and uv cache.
# /home/appuser/.cache must be pre-created so that bind mounts for
# subdirectories (e.g. huggingface calibration) don't cause Docker
# to create .cache as root, which blocks uv from writing its cache.
RUN mkdir -p /app/data /app/storage /app/tmp /home/appuser/.cache/huggingface \
    && chown -R "${APP_UID}:${APP_GID}" /app /home/appuser/.cache

# Environment configuration
ENV PATH="/app/application/backend/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONFAULTHANDLER=1 \
    UV_NO_SYNC=1 \
    STATIC_FILES_DIR="/app/application/ui/" \
    DATA_DIR="/app/data" \
    STORAGE_DIR="/app/storage" \
    PYTHONPATH="/app/application/backend"

EXPOSE 8000

# ===========================================================================
# Stage 6a: CPU runtime target
# ===========================================================================
FROM runtime-base AS physical-ai-studio-cpu

ARG APP_UID=1000
ARG APP_GID=1000

# Virtual environment from CPU builder; app files from app-source.
COPY --link --from=builder-cpu --chown=${APP_UID}:${APP_GID} \
    /app/application/backend/.venv /app/application/backend/.venv
COPY --link --from=app-source --chown=${APP_UID}:${APP_GID} /app /app

WORKDIR /app/application/backend
USER appuser
CMD ["./run.sh"]

# ===========================================================================
# Stage 6b: XPU (Intel) runtime target
# ===========================================================================
FROM runtime-base AS runtime-xpu

# Intel GPU compute & media runtime from Kobuk PPA (Ubuntu Noble).
# The PPA packages work on Debian 13 (trixie); trusted=yes is required
# because Debian 13's sqv GPG verifier cannot validate the Launchpad key.
# Based on: https://dgpu-docs.intel.com/driver/client/overview.html
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN echo "deb [arch=amd64 trusted=yes] https://ppa.launchpadcontent.net/kobuk-team/intel-graphics/ubuntu noble main" \
        > /etc/apt/sources.list.d/kobuk-intel.list \
    && apt-get update && apt-get install -y --no-install-recommends \
        libze-intel-gpu1 \
        libze1 \
        libze-dev \
        intel-opencl-icd \
        intel-metrics-discovery \
        intel-gsc \
        intel-ocloc \
        clinfo \
        intel-media-va-driver-non-free \
        libmfx-gen1 \
        libvpl2 \
        libvpl-tools \
        libva-glx2 \
        va-driver-all \
        vainfo \
    && rm -rf /var/lib/apt/lists/*

SHELL ["/bin/sh", "-c"]

FROM runtime-xpu AS physical-ai-studio-xpu

ARG APP_UID=1000
ARG APP_GID=1000

# Virtual environment from XPU builder; app files from app-source.
COPY --link --from=builder-xpu --chown=${APP_UID}:${APP_GID} \
    /app/application/backend/.venv /app/application/backend/.venv
COPY --link --from=app-source --chown=${APP_UID}:${APP_GID} /app /app

WORKDIR /app/application/backend
USER appuser
CMD ["./run.sh"]

# ===========================================================================
# Stage 6c: CUDA runtime target
# ===========================================================================
FROM runtime-base AS runtime-cuda

# NVIDIA CUDA 12.8 runtime libraries (matches cu128 PyTorch wheels).
# Requires NVIDIA Container Toolkit on the host for GPU passthrough.
#
# Uses the debian12 repo on Debian 13 (trixie) because the debian13 repo
# only has CUDA 13.1 packages (not 12.8). trusted=yes is required because
# Debian 13's sqv GPG verifier cannot validate the NVIDIA signing key.
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN echo "deb [arch=amd64 trusted=yes] https://developer.download.nvidia.com/compute/cuda/repos/debian12/x86_64 /" \
        > /etc/apt/sources.list.d/nvidia-cuda.list \
    && apt-get update && apt-get install -y --no-install-recommends \
        cuda-cudart-12-8=12.8.90-1 \
        libcublas-12-8=12.8.4.1-1 \
        libcudnn9-cuda-12=9.19.0.56-1 \
    && rm -rf /var/lib/apt/lists/*

SHELL ["/bin/sh", "-c"]

# ---------------------------------------------------------------------------
# EULA compliance cleanup — remove non-redistributable CUDA components.
# Keeps only the runtime shared libraries needed for inference.
# Based on: https://docs.nvidia.com/cuda/eula/index.html
# ---------------------------------------------------------------------------
RUN set -eux; \
    # Remove development tools (compilers, debuggers, profilers)
    apt-get remove -y --allow-remove-essential \
        cuda-compiler-12-8 cuda-cudart-dev-12-8 cuda-nvcc-12-8 \
        cuda-gdb-12-8 cuda-nsight-12-8 cuda-nsight-compute-12-8 \
        cuda-nsight-systems-12-8 || true; \
    # Remove headers and static libraries
    find /usr/local/cuda* /usr/lib/x86_64-linux-gnu/ \
        \( -path '*/include' -o -path '*/headers' \) -type d \
        -exec rm -rf {} + 2>/dev/null || true; \
    find /usr/local/cuda* /usr/lib/x86_64-linux-gnu/ \
        -name '*.a' -delete 2>/dev/null || true; \
    # Remove documentation and samples
    rm -rf /usr/local/cuda*/doc /usr/local/cuda*/samples \
           /usr/local/cuda*/extras/demo_suite; \
    # Remove CUPTI profiling libraries (non-redistributable)
    rm -rf /usr/local/cuda*/extras/CUPTI; \
    # Remove cuSolver multi-GPU component (requires separate license)
    find /usr/lib/x86_64-linux-gnu/ -name 'libcusolverMg*' -delete 2>/dev/null || true; \
    # Clean up
    apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

FROM runtime-cuda AS physical-ai-studio-cuda

ARG APP_UID=1000
ARG APP_GID=1000

# Virtual environment from CUDA builder; app files from app-source.
COPY --link --from=builder-cuda --chown=${APP_UID}:${APP_GID} \
    /app/application/backend/.venv /app/application/backend/.venv
COPY --link --from=app-source --chown=${APP_UID}:${APP_GID} /app /app

WORKDIR /app/application/backend
USER appuser
CMD ["./run.sh"]
```


```yaml
# ================================================================
# Physical AI Studio — Docker Compose
#
# Uses Docker Compose profiles to select the hardware backend.
# Set COMPOSE_PROFILES in your .env file (cpu, xpu, or cuda)
# or pass --profile on the command line:
#
#   docker compose --profile cpu up      # CPU (default)
#   docker compose --profile xpu up      # Intel XPU
#   docker compose --profile cuda up     # NVIDIA CUDA
#
# ================================================================

x-common: &common
    ports:
      - "${PORT:-7860}:${PORT:-7860}"
    environment:
      - HOST=${HOST:-0.0.0.0}
      - PORT=${PORT:-7860}
    env_file:
      - path: .env
        required: false
    restart: unless-stopped
    stop_grace_period: 35s

    # PyTorch DataLoader workers need shared memory (/dev/shm) beyond
    # Docker's 64 MB default. Using ipc: host shares the host's /dev/shm
    # (typically 50% of system RAM on Linux), so it scales automatically
    # with available memory and works across different hardware configs.
    #
    # If you prefer an isolated, fixed-size allocation instead, comment
    # out "ipc: host" and uncomment the line below:
    # shm_size: 16g
    ipc: host

    healthcheck:
      test:
        [
          "CMD",
          "python",
          "-c",
          "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-7860}/api/health')",
        ]
      interval: 30s
      timeout: 10s
      start_period: 60s
      retries: 3

    # ============================================================
    # HARDWARE ACCESS
    #
    # Choose ONE of the two modes below by commenting/uncommenting.
    # Both modes require group_add for device permissions.
    #
    # Docker resolves group names against the *container's* /etc/group,
    # not the host's. The defaults below (dialout, plugdev, video) work
    # on Debian/Ubuntu hosts where the host GIDs match the container's.
    # On other distros (e.g. Arch Linux) you must override these with
    # your host's numeric GIDs — run `application/docker/setup-devices.sh`
    # to auto-detect and write them to .env.
    # ============================================================

    group_add:
      - "${DIALOUT_GID:-dialout}" # serial ports (/dev/ttyACM*)
      - "${PLUGDEV_GID:-plugdev}" # pluggable USB devices
      - "${VIDEO_GID:-video}" # cameras & video (/dev/video*)

    # Persisted data and storage volumes + shared robot calibration
    volumes:
      - physical-ai-studio-data:/app/data
      - physical-ai-studio-storage:/app/storage
      - ${HOME}/.cache/huggingface/lerobot/calibration:/home/appuser/.cache/huggingface/lerobot/calibration:ro

    # --- Option 1: Privileged mode (active by default)
    # Grants full access to all host devices. Easiest setup, but the
    # container runs with elevated privileges.
    # Also covers Intel RealSense cameras via /dev/bus/usb.
    privileged: true

    # --- Option 2: Non-privileged mode (more secure)
    # Map only the specific devices the robot needs. More secure since
    # the container cannot access arbitrary host devices, but you must
    # update the device list whenever hardware changes.
    # To switch: comment out "privileged: true" above and uncomment below.
    # privileged: false
    # devices:
    #    # Feetech servo USB connection (e.g., /dev/ttyUSB0)
    #    - /dev/ttyACM0:/dev/ttyACM0
    #    - /dev/ttyACM1:/dev/ttyACM1
    #    - /dev/ttyACM2:/dev/ttyACM2
    #    # Standard USB cameras (v4l2)
    #    - /dev/video0:/dev/video0
    #    - /dev/video2:/dev/video2
    #    - /dev/video4:/dev/video4
    #    # Intel RealSense cameras
    #    # - /dev/bus/usb:/dev/bus/usb

x-common-build: &common-build
    context: ../../
    dockerfile: application/docker/Dockerfile
    additional_contexts:
      libs: ../../library
    args:
      - APP_UID=${APP_UID:-1000}
      - APP_GID=${APP_GID:-1000}
      - HTTP_PROXY=${HTTP_PROXY}
      - HTTPS_PROXY=${HTTPS_PROXY}
      - NO_PROXY=${NO_PROXY}
      - http_proxy=${http_proxy}
      - https_proxy=${https_proxy}
      - no_proxy=${no_proxy}

services:
  physical-ai-studio-cpu:
    <<: *common
    profiles: [cpu]
    container_name: physical-ai-studio-cpu
    image: ${REGISTRY:-ghcr.io/open-edge-platform/}physical-ai-studio-cpu:${IMAGE_TAG:-main}
    build:
      <<: *common-build
      target: physical-ai-studio-cpu

  physical-ai-studio-xpu:
    <<: *common
    profiles: [xpu]
    container_name: physical-ai-studio-xpu
    image: ${REGISTRY:-ghcr.io/open-edge-platform/}physical-ai-studio-xpu:${IMAGE_TAG:-main}
    build:
      <<: *common-build
      target: physical-ai-studio-xpu
    # --- Non-privileged XPU additions
    # When running in non-privileged mode, add these to grant
    # Intel GPU access via /dev/dri/renderD* nodes:
    # group_add:
    #   - "${DIALOUT_GID:-dialout}"
    #   - "${PLUGDEV_GID:-plugdev}"
    #   - "${VIDEO_GID:-video}"
    #   - "${RENDER_GID:-render}"   # Intel GPU render nodes
    # devices:
    #   - /dev/dri:/dev/dri         # Intel GPU device nodes

  physical-ai-studio-cuda:
    <<: *common
    profiles: [cuda]
    container_name: physical-ai-studio-cuda
    image: ${REGISTRY:-ghcr.io/open-edge-platform/}physical-ai-studio-cuda:${IMAGE_TAG:-main}
    build:
      <<: *common-build
      target: physical-ai-studio-cuda
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]

volumes:
  physical-ai-studio-data:
  physical-ai-studio-storage:
```

## 7) Applying the Physical AI Studio pattern to Geti OTX GPU/XPU and all Python Dockerfiles

Short answer: **yes**. The two most valuable parts of the pattern are:

1. **dependency-first layering** (run `uv sync` before app source copy), and
2. **`app-source` stage separation** (copy mutable source from a dedicated stage after dependency install).

These are safe to apply broadly to our Python-based Dockerfiles because they reduce cache invalidation without changing runtime behavior.

### 7.1 OTX GPU/XPU applicability

For trainer images (`interactive_ai/workflows/train/trainer/{gpu,xpu}`), we can and should use the same idea:

- keep heavy dependency resolution isolated from application source,
- avoid pre-sync copies of `scripts/`, `run`, and `download_pretrained_weights.py`,
- copy those runtime artifacts from a dedicated `app-source` stage only after dependency layers are resolved.

This gives faster rebuilds when trainer logic changes while preserving existing CUDA/XPU runtime packaging semantics.

### 7.2 Repository-wide rollout scope

The same cache-preserving idea was applied across Python, Go, and UI images with language-appropriate dependency boundaries.

Applied coverage in this repo:

- all Dockerfiles using `uv sync` now follow dependency-first ordering,
- those Python files now use an `app-source` stage for application/job source,
- Go service Dockerfiles now run `go mod download` before local source copy and use an `app-source` stage for mutable `main.go`/`app` inputs,
- UI Dockerfiles now install npm dependencies before mutable source/config copy, with dedicated app-source stages for source assets/templates.

### 7.3 Expected impact

- source-only edits no longer invalidate expensive Python dependency layers,
- repeat local rebuilds should be materially faster,
- CI cache hit rate should improve for unchanged dependency manifests.

### 7.4 Remaining optional enhancement

For XPU specifically, further gains are available by defining torch/XPU resolution directly in dependency metadata (extras + index mapping) so a single frozen `uv sync` resolves the right wheels without uninstall/reinstall steps.
