# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import json
import os
import subprocess
import time

from scheduler.workflow_adapters import WorkflowAdapterError, run_import_export_job

from scheduler.celery_app import celery_app

_IMPORT_EXPORT_JOB_TYPES = {
    "export_dataset",
    "prepare_import_to_new_project",
    "prepare_import_to_existing_project",
    "perform_import_to_new_project",
    "perform_import_to_existing_project",
    "export_project",
    "import_project",
}

_DATASET_IE_CONTAINER_JOB_TYPES = {
    "export_dataset",
    "prepare_import_to_new_project",
    "prepare_import_to_existing_project",
    "perform_import_to_new_project",
    "perform_import_to_existing_project",
}


def _dataset_ie_image() -> str:
    return os.environ.get("DATASET_IE_WORKFLOW_IMAGE", "")


def _project_ie_image() -> str:
    return os.environ.get("PROJECT_IE_WORKFLOW_IMAGE", "")


def _build_workflow_runner(job_type: str) -> str:
    return (
        "import json, os; "
        "from scheduler.workflow_adapters import run_import_export_job; "
        "payload = json.loads(os.environ['WORKFLOW_PAYLOAD_JSON']); "
        f"run_import_export_job('{job_type}', payload)"
    )


def _run_import_export_in_container(job_type: str, payload: dict) -> None:
    image = _dataset_ie_image() if job_type in _DATASET_IE_CONTAINER_JOB_TYPES else _project_ie_image()
    if not image:
        raise WorkflowAdapterError(f"Missing workflow image for job_type={job_type}")

    cmd = [
        "docker",
        "run",
        "--rm",
        "--network",
        "host",
    ]

    _forward_prefixes = (
        "DATABASE_",
        "MONGODB_",
        "KAFKA_",
        "SPICEDB_",
        "S3_",
        "SESSION_",
        "JOB_METADATA_",
        "JOBS_SCHEDULER",
        "SIGNING_IE_PRIVKEY",
        "CELERY_",
        "OTEL_",
        "ENABLE_",
    )
    for key in os.environ:
        if any(key.startswith(p) for p in _forward_prefixes):
            cmd += ["--env", key]

    cmd += ["--env", f"WORKFLOW_PAYLOAD_JSON={json.dumps(payload)}"]

    cmd += [image, "python", "-c", _build_workflow_runner(job_type=job_type)]
    subprocess.run(cmd, check=True, timeout=3600)  # noqa: S603


@celery_app.task(bind=True, name="scheduler.run_job_execution")
def run_job_execution(self, execution_name: str, job_type: str, payload: dict):  # noqa: ANN001
    """
    Transitional Celery task for compose mode.

    Dispatches import/export job types to dedicated workflow runtime containers.
    Other job types remain in simulation fallback for now.
    """
    if job_type in _IMPORT_EXPORT_JOB_TYPES:
        _run_import_export_in_container(job_type=job_type, payload=payload)
    else:
        duration = float(payload.get("sim_duration_sec", 2))
        time.sleep(duration)
    return {"execution_name": execution_name, "status": "succeeded"}
