# syntax=docker/dockerfile:1.7

FROM python:3.10-slim-bookworm@sha256:23f63358922e79a794f71be8f3723c84e5ccca9638af3f74456dc73d6184499e AS base

FROM base AS builder

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_PYTHON_DOWNLOADS=0

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
        gcc \
    && rm -rf /var/lib/apt/lists/*

COPY --link --from=ghcr.io/astral-sh/uv:0.6.12@sha256:515b886e8eb99bcf9278776d8ea41eb4553a794195ef5803aa7ca6258653100d /uv /bin/uv

WORKDIR /workspace

# Local editable dependencies referenced in infrastructure/geti_init/pyproject.toml
COPY --link libs ./libs
COPY --link interactive_ai/data_migration ./interactive_ai/data_migration
COPY --link interactive_ai/migration_job/migration_job ./interactive_ai/migration_job/migration_job

COPY --link infrastructure/geti_init/pyproject.toml /workspace/infrastructure/geti_init/pyproject.toml
RUN --mount=type=cache,id=uv-cache,target=/root/.cache/uv,sharing=locked \
    uv venv /opt/venv && \
    uv pip install --python /opt/venv/bin/python /workspace/infrastructure/geti_init

FROM base AS runtime

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
        openssl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY --link --from=builder /opt/venv /opt/venv

# Editable dependency sources must exist in runtime at the same paths.
COPY --link --from=builder /workspace/libs ./libs
COPY --link --from=builder /workspace/interactive_ai/data_migration ./interactive_ai/data_migration
COPY --link --from=builder /workspace/interactive_ai/migration_job/migration_job ./interactive_ai/migration_job/migration_job

COPY --link infrastructure/geti_init/initial_user ./infrastructure/geti_init/initial_user
COPY --link infrastructure/geti_init/weights_uploader ./infrastructure/geti_init/weights_uploader
COPY --link infrastructure/geti_init/main.py /workspace/infrastructure/geti_init/main.py

ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONPATH="/workspace:/workspace/interactive_ai/migration_job:/workspace/infrastructure/geti_init"

CMD ["python", "-u", "/workspace/infrastructure/geti_init/main.py"]
