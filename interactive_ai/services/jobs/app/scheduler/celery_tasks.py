# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import json
import os
import subprocess
import time

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

_MODEL_TEST_JOB_TYPES = {"test"}

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


def _model_test_image() -> str:
    return os.environ.get("MODEL_TEST_WORKFLOW_IMAGE", "")


def _build_workflow_runner(job_type: str) -> str:
    return (
        "import json, os; "
        "from unittest.mock import patch; "
        "payload = json.loads(os.environ['WORKFLOW_PAYLOAD_JSON']); "
        "with patch('jobs_common.tasks.utils.secrets.set_env_vars', lambda: None), "
        "patch('jobs_common.tasks.utils.progress.report_progress', lambda *a, **k: None), "
        "patch('jobs_common.tasks.utils.progress.publish_metadata_update', lambda m: None): "
        + (
            "from job.tasks.export_tasks.export_dataset_task import export_dataset_task as fn; "
            "fn(organization_id=payload['organization_id'], project_id=payload['project_id'], "
            "dataset_storage_id=payload['dataset_storage_id'], include_unannotated=payload.get('include_unannotated', False), "
            "export_format=payload['export_format'], save_video_as_images=payload.get('save_video_as_images', False))"
            if job_type == "export_dataset"
            else ""
        )
        + (
            "from job.tasks.import_tasks.parse_dataset_new_project import parse_dataset_for_import_to_new_project as fn; "
            "fn(import_id=payload['import_id'])"
            if job_type == "prepare_import_to_new_project"
            else ""
        )
        + (
            "from job.tasks.import_tasks.parse_dataset_existing_project import parse_dataset_for_import_to_existing_project as fn; "
            "fn(import_id=payload['import_id'], project_id=payload['project_id'])"
            if job_type == "prepare_import_to_existing_project"
            else ""
        )
        + (
            "from job.tasks.import_tasks.create_project_from_dataset import create_project_from_dataset as fn; "
            "fn(import_id=payload['import_id'], name=payload['name'], project_type_str=payload['project_type_str'], "
            "label_names=payload['label_names'], color_by_label=payload['color_by_label'], "
            "keypoint_structure=payload['keypoint_structure'], user_id=payload['user_id'])"
            if job_type == "perform_import_to_new_project"
            else ""
        )
        + (
            "from job.tasks.import_tasks.import_dataset_to_project import import_dataset_to_project as fn; "
            "fn(project_id=payload['project_id'], import_id=payload['import_id'], label_ids_map=payload['label_ids_map'], "
            "dataset_storage_id=payload['dataset_storage_id'], dataset_name=payload['dataset_name'], user_id=payload['user_id'])"
            if job_type == "perform_import_to_existing_project"
            else ""
        )
        + (
            "from job.tasks.export_project import export_project as fn; "
            "fn(project_id=payload['project_id'], include_models=payload.get('include_models', 'all'))"
            if job_type == "export_project"
            else ""
        )
        + (
            "from job.tasks.import_project import import_project as fn; "
            "fn(file_id=payload['file_id'], keep_original_dates=payload.get('keep_original_dates', False), "
            "project_name=payload['project_name'], user_id=payload['user_id'])"
            if job_type == "import_project"
            else ""
        )
        + (
            "from job.tasks.model_testing import run_model_test as fn; "
            "fn(project_id=payload['project_id'], model_test_result_id=payload['model_test_result_id'], "
            "min_annotation_size=payload.get('min_annotation_size'), max_annotation_size=payload.get('max_annotation_size'), "
            "min_number_of_annotations=payload.get('min_number_of_annotations'), "
            "max_number_of_annotations=payload.get('max_number_of_annotations'))"
            if job_type == "test"
            else ""
        )
    )


def _run_import_export_in_container(job_type: str, payload: dict) -> None:
    if job_type in _DATASET_IE_CONTAINER_JOB_TYPES:
        image = _dataset_ie_image()
    elif job_type in _MODEL_TEST_JOB_TYPES:
        image = _model_test_image()
    else:
        image = _project_ie_image()
    if not image:
        raise RuntimeError(f"Missing workflow image for job_type={job_type}")

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

    Dispatches import/export and model-test job types to dedicated workflow runtime containers.
    Other job types remain in simulation fallback for now.
    """
    if job_type in _IMPORT_EXPORT_JOB_TYPES or job_type in _MODEL_TEST_JOB_TYPES:
        _run_import_export_in_container(job_type=job_type, payload=payload)
    else:
        duration = float(payload.get("sim_duration_sec", 2))
        time.sleep(duration)
    return {"execution_name": execution_name, "status": "succeeded"}
