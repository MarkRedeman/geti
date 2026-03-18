# syntax=docker/dockerfile:1.7

FROM python:3.10-slim-bookworm@sha256:23f63358922e79a794f71be8f3723c84e5ccca9638af3f74456dc73d6184499e

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    openssl \
    libsasl2-dev \
    libldap2-dev \
    libssl-dev \
    libsasl2-2 \
    libldap-2.5-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY libs ./libs
COPY platform/libs ./platform/libs
COPY interactive_ai/data_migration ./interactive_ai/data_migration
COPY interactive_ai/migration_job/migration_job ./interactive_ai/migration_job/migration_job
COPY platform/services/initial_user/app ./platform/services/initial_user/app
COPY platform/services/weights_uploader/app ./platform/services/weights_uploader/app
COPY platform/services/weights_uploader/app/pretrained_models ./platform/services/weights_uploader/app/pretrained_models

COPY infrastructure/geti_init/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY infrastructure/geti_init/main.py /workspace/infrastructure/geti_init/main.py

ENV PYTHONPATH="/workspace:/workspace/interactive_ai/migration_job:/workspace/platform/services/initial_user/app:/workspace/platform/services/weights_uploader/app"

CMD ["python", "-u", "/workspace/infrastructure/geti_init/main.py"]
