# syntax=docker/dockerfile:1.7

# Required runtime flags to enable XPU support:
# --device /dev/dri          # Intel GPU access
# -v /dev/dri/by-path:/dev/dri/by-path  # Device path mapping

# app-source: holds source/runtime scripts; no heavy deps, stays small and cacheable
FROM scratch AS app-source
COPY --link scripts/ scripts/
COPY --link run run
COPY --link download_pretrained_weights.py download_pretrained_weights.py

FROM python:3.10-slim-bookworm@sha256:23f63358922e79a794f71be8f3723c84e5ccca9638af3f74456dc73d6184499e AS python_dependencies

COPY --link --from=libs . libs

WORKDIR /interactive_ai/workflows/train/trainer
RUN chown -R 10001:10001 /interactive_ai/workflows/train/trainer

COPY --link --from=ghcr.io/astral-sh/uv:0.6.12@sha256:515b886e8eb99bcf9278776d8ea41eb4553a794195ef5803aa7ca6258653100d /uv /bin/uv

# Install base deps, then replace torch with the XPU-enabled build in a single cached layer
RUN --mount=type=cache,id=uv-cache,target=/root/.cache/uv,sharing=locked \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev --no-editable && \
    uv pip uninstall torch torchvision && \
    uv pip install torch==2.8.0 torchvision==0.23.0 --default-index https://download.pytorch.org/whl/xpu

RUN rm -rf /interactive_ai/workflows/train/trainer/.venv/lib/python3.10/site-packages/nvidia \
           /interactive_ai/workflows/train/trainer/.venv/lib/python3.10/site-packages/triton/backends/nvidia/

FROM python:3.10-slim-bookworm@sha256:23f63358922e79a794f71be8f3723c84e5ccca9638af3f74456dc73d6184499e AS base

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_PYTHON_DOWNLOADS=0

# Step 1: Install runtime dependencies and intel graphics libs
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    libgl1=1.6.* \
    libglib2.0-0=2.74.* \
    software-properties-common \
    gpg \
    wget \
    curl && \
    rm -rf /var/lib/apt/lists/* && \
    useradd -l -u 10001 non-root && \
    pip3 uninstall -y setuptools pip wheel && \
    rm -rf /root/.cache/pip

RUN wget -qO /tmp/intel-graphics.key https://repositories.intel.com/gpu/intel-graphics.key && \
    gpg --yes --dearmor --output /usr/share/keyrings/intel-graphics.gpg /tmp/intel-graphics.key
RUN echo "deb [arch=amd64,i386 signed-by=/usr/share/keyrings/intel-graphics.gpg] https://repositories.intel.com/gpu/ubuntu jammy unified" | tee /etc/apt/sources.list.d/intel-gpu-jammy.list
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update \
    && apt-get install -y --no-install-recommends \
    git libze-intel-gpu1 libze1 intel-opencl-icd clinfo libze-dev intel-ocloc && \
    rm -rf /var/lib/apt/lists/*
# Remove unnecessary packages and files to reduce the final image size
RUN apt-get purge -y --auto-remove gpg wget && \
    rm -rf /root/.cache \
    /var/cache/apt/* /var/lib/apt/lists/* /var/log/* \
    /tmp/* \
    /usr/share/man/* /usr/share/doc/*

# Copy the service dependencies
COPY --link --from=libs . libs

WORKDIR /interactive_ai/workflows/train/trainer
RUN chown -R 10001:10001 /interactive_ai/workflows/train/trainer

COPY --link --from=ghcr.io/astral-sh/uv:0.6.12@sha256:515b886e8eb99bcf9278776d8ea41eb4553a794195ef5803aa7ca6258653100d /uv /bin/uv

COPY --link --from=app-source scripts/ scripts
COPY --link --from=app-source run run
COPY --link --from=app-source download_pretrained_weights.py download_pretrained_weights.py

COPY --link --from=python_dependencies /interactive_ai/workflows/train/trainer/.venv /interactive_ai/workflows/train/trainer/.venv

# Place executables in the environment at the front of the path
ENV PATH="/interactive_ai/workflows/train/trainer/.venv/bin:/interactive_ai/workflows/train/trainer:$PATH"
ENV PYTHONPATH="/interactive_ai/workflows/train/trainer"
ENV HF_HUB_OFFLINE=1

USER non-root

WORKDIR /home/non-root
WORKDIR /interactive_ai/workflows/train/trainer
