# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import json
import os
import subprocess

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
_TRAIN_JOB_TYPES = {"train"}
_OPTIMIZE_JOB_TYPES = {"optimize_pot"}

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


def _train_workflow_image() -> str:
    return os.environ.get("TRAIN_WORKFLOW_IMAGE", "")


def _trainer_runtime_image() -> str:
    return os.environ.get("TRAINER_RUNTIME_IMAGE", "")


def _optimize_workflow_image() -> str:
    return os.environ.get("OPTIMIZE_WORKFLOW_IMAGE", "")


def _run_optimize_trainer_container(payload: dict) -> None:
    image = _trainer_runtime_image()
    if not image:
        raise RuntimeError("Missing TRAINER_RUNTIME_IMAGE for optimize_pot job")

    org_id = os.environ.get("SESSION_ORGANIZATION_ID", payload.get("organization_id", ""))
    workspace_id = os.environ.get("SESSION_WORKSPACE_ID", payload.get("workspace_id", ""))
    project_id = payload["project_id"]
    job_id = os.environ.get("JOB_METADATA_ID", payload.get("job_id", ""))
    identifier_json = json.dumps(
        {
            "organization_id": str(org_id),
            "workspace_id": str(workspace_id),
            "project_id": str(project_id),
            "job_id": str(job_id),
        }
    )

    cmd = ["docker", "run", "--rm", "--network", "host"]
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
        "FEATURE_FLAG_",
        "WORKFLOW_",
        "MODEL_REGISTRATION_",
    )
    for key in os.environ:
        if any(key.startswith(p) for p in _forward_prefixes):
            cmd += ["--env", key]

    cmd += ["--env", f"IDENTIFIER_JSON={identifier_json}"]
    cmd += ["--env", f"SHARD_FILES_DIR={os.environ.get('SHARD_FILES_DIR', '/tmp/shard_files')}"]
    cmd += ["--env", "TASK_ID=optimize"]
    cmd += ["--env", "JOB_TYPE=optimize_pot"]

    trainer_command = os.environ.get("TRAINER_RUNTIME_COMMAND", "run")
    cmd += [image, "bash", "-c", trainer_command]
    _ = subprocess.run(cmd, check=True, timeout=7200)  # noqa: S603


def _run_optimize_finalize_stage(payload: dict, prep_result: dict) -> None:
    image = _optimize_workflow_image()
    if not image:
        raise RuntimeError("Missing OPTIMIZE_WORKFLOW_IMAGE for optimize finalize stage")

    cmd = ["docker", "run", "--rm", "--network", "host"]
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
        "FEATURE_FLAG_",
        "WORKFLOW_",
        "MODEL_REGISTRATION_",
    )
    for key in os.environ:
        if any(key.startswith(p) for p in _forward_prefixes):
            cmd += ["--env", key]

    cmd += ["--env", f"WORKFLOW_PAYLOAD_JSON={json.dumps(payload)}"]
    cmd += ["--env", "WORKFLOW_JOB_TYPE=optimize_pot"]
    cmd += ["--env", "WORKFLOW_JOB_STAGE=finalize"]
    cmd += ["--env", f"OPTIMIZE_PREP_RESULT_JSON={json.dumps(prep_result)}"]
    cmd += [image, *_workflow_runner_command()]
    _ = subprocess.run(cmd, check=True, timeout=3600)  # noqa: S603


def _run_optimize_evaluate_stage(payload: dict, prep_result: dict) -> None:
    image = _optimize_workflow_image()
    if not image:
        raise RuntimeError("Missing OPTIMIZE_WORKFLOW_IMAGE for optimize evaluate stage")

    cmd = ["docker", "run", "--rm", "--network", "host"]
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
        "FEATURE_FLAG_",
        "WORKFLOW_",
        "MODEL_REGISTRATION_",
    )
    for key in os.environ:
        if any(key.startswith(p) for p in _forward_prefixes):
            cmd += ["--env", key]

    cmd += ["--env", f"WORKFLOW_PAYLOAD_JSON={json.dumps(payload)}"]
    cmd += ["--env", "WORKFLOW_JOB_TYPE=optimize_pot"]
    cmd += ["--env", "WORKFLOW_JOB_STAGE=evaluate"]
    cmd += ["--env", f"OPTIMIZE_PREP_RESULT_JSON={json.dumps(prep_result)}"]
    cmd += [image, *_workflow_runner_command()]
    _ = subprocess.run(cmd, check=True, timeout=3600)  # noqa: S603


def _run_train_trainer_container(payload: dict) -> None:
    """
    Transitional trainer runtime stage for train jobs.

    This runs the trainer image after train-data/model preparation has completed.
    """
    image = _trainer_runtime_image()
    if not image:
        raise RuntimeError("Missing TRAINER_RUNTIME_IMAGE for train job")

    org_id = os.environ.get("SESSION_ORGANIZATION_ID", payload.get("organization_id", ""))
    workspace_id = os.environ.get("SESSION_WORKSPACE_ID", payload.get("workspace_id", ""))
    project_id = payload["project_id"]
    job_id = os.environ.get("JOB_METADATA_ID", payload.get("job_id", ""))
    identifier_json = json.dumps(
        {
            "organization_id": str(org_id),
            "workspace_id": str(workspace_id),
            "project_id": str(project_id),
            "job_id": str(job_id),
        }
    )

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
        "FEATURE_FLAG_",
        "WORKFLOW_",
        "MODEL_REGISTRATION_",
    )
    for key in os.environ:
        if any(key.startswith(p) for p in _forward_prefixes):
            cmd += ["--env", key]

    cmd += ["--env", f"IDENTIFIER_JSON={identifier_json}"]
    cmd += ["--env", f"SHARD_FILES_DIR={os.environ.get('SHARD_FILES_DIR', '/tmp/shard_files')}"]
    cmd += ["--env", "TASK_ID=train"]

    trainer_command = os.environ.get("TRAINER_RUNTIME_COMMAND", "bash -c run")
    cmd += [image, "bash", "-c", trainer_command]
    subprocess.run(cmd, check=True, timeout=7200)  # noqa: S603


def _run_train_finalize_stage(payload: dict, prep_result: dict) -> None:
    image = _train_workflow_image()
    if not image:
        raise RuntimeError("Missing TRAIN_WORKFLOW_IMAGE for train finalize stage")

    cmd = ["docker", "run", "--rm", "--network", "host"]
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
        "FEATURE_FLAG_",
        "WORKFLOW_",
        "MODEL_REGISTRATION_",
    )
    for key in os.environ:
        if any(key.startswith(p) for p in _forward_prefixes):
            cmd += ["--env", key]

    cmd += ["--env", f"WORKFLOW_PAYLOAD_JSON={json.dumps(payload)}"]
    cmd += ["--env", "WORKFLOW_JOB_TYPE=train"]
    cmd += ["--env", "WORKFLOW_JOB_STAGE=finalize"]
    cmd += ["--env", f"TRAIN_PREP_RESULT_JSON={json.dumps(prep_result)}"]
    cmd += [image, *_workflow_runner_command()]
    _ = subprocess.run(cmd, check=True, timeout=3600)  # noqa: S603


def _should_run_train_finalize(prep_result: dict) -> bool:
    from geti_types import ID
    from iai_core.entities.model import ModelStatus
    from iai_core.repos import ModelRepo
    from job.utils.train_workflow_data import TrainWorkflowData
    from jobs_common_extras.experiments.utils.train_output_models import TrainOutputModelIds

    train_data = TrainWorkflowData.from_json(prep_result["train_data_json"])
    train_output_model_ids = TrainOutputModelIds.from_json(prep_result["train_output_model_ids_json"])
    model_repo = ModelRepo(train_data.get_model_storage_identifier())
    base_model = model_repo.get_by_id(ID(train_output_model_ids.base))
    return base_model.model_status == ModelStatus.NOT_READY


def _run_train_evaluate_stage(payload: dict, prep_result: dict) -> None:
    image = _train_workflow_image()
    if not image:
        raise RuntimeError("Missing TRAIN_WORKFLOW_IMAGE for train evaluate stage")

    cmd = ["docker", "run", "--rm", "--network", "host"]
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
        "FEATURE_FLAG_",
        "WORKFLOW_",
        "MODEL_REGISTRATION_",
    )
    for key in os.environ:
        if any(key.startswith(p) for p in _forward_prefixes):
            cmd += ["--env", key]

    cmd += ["--env", f"WORKFLOW_PAYLOAD_JSON={json.dumps(payload)}"]
    cmd += ["--env", "WORKFLOW_JOB_TYPE=train"]
    cmd += ["--env", "WORKFLOW_JOB_STAGE=evaluate"]
    cmd += ["--env", f"TRAIN_PREP_RESULT_JSON={json.dumps(prep_result)}"]
    cmd += [image, *_workflow_runner_command()]
    _ = subprocess.run(cmd, check=True, timeout=3600)  # noqa: S603


def _workflow_runner_command() -> list[str]:
    return ["python", "-m", "scheduler.workflow_runner"]


def _run_import_export_in_container(job_type: str, payload: dict) -> str:
    if job_type in _DATASET_IE_CONTAINER_JOB_TYPES:
        image = _dataset_ie_image()
    elif job_type in _MODEL_TEST_JOB_TYPES:
        image = _model_test_image()
    elif job_type in _TRAIN_JOB_TYPES:
        image = _train_workflow_image()
    elif job_type in _OPTIMIZE_JOB_TYPES:
        image = _optimize_workflow_image()
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
        "WORKFLOW_",
        "MODEL_REGISTRATION_",
    )
    for key in os.environ:
        if any(key.startswith(p) for p in _forward_prefixes):
            cmd += ["--env", key]

    cmd += ["--env", f"WORKFLOW_PAYLOAD_JSON={json.dumps(payload)}"]
    cmd += ["--env", f"WORKFLOW_JOB_TYPE={job_type}"]

    cmd += [image, *_workflow_runner_command()]
    result = subprocess.run(cmd, check=True, timeout=3600, capture_output=True, text=True)  # noqa: S603
    return result.stdout


@celery_app.task(bind=True, name="scheduler.run_job_execution")
def run_job_execution(self, execution_name: str, job_type: str, payload: dict):  # noqa: ANN001
    """
    Compose-mode Celery executor.

    Dispatches supported job types to workflow runtime containers.
    Unsupported job types fail fast to avoid silent simulation fallback.
    """
    if job_type in _IMPORT_EXPORT_JOB_TYPES or job_type in _MODEL_TEST_JOB_TYPES:
        _run_import_export_in_container(job_type=job_type, payload=payload)
    elif job_type in _TRAIN_JOB_TYPES:
        stdout = _run_import_export_in_container(job_type=job_type, payload=payload)
        prep_result = None
        for line in stdout.splitlines():
            if line.startswith("TRAIN_PREP_RESULT="):
                prep_result = json.loads(line.removeprefix("TRAIN_PREP_RESULT="))
                break
        if prep_result is None:
            raise RuntimeError("Train prep stage did not emit TRAIN_PREP_RESULT")
        _run_train_trainer_container(payload=payload)
        if _should_run_train_finalize(prep_result=prep_result):
            _run_train_finalize_stage(payload=payload, prep_result=prep_result)
        _run_train_evaluate_stage(payload=payload, prep_result=prep_result)
    elif job_type in _OPTIMIZE_JOB_TYPES:
        stdout = _run_import_export_in_container(job_type=job_type, payload=payload)
        prep_result = None
        for line in stdout.splitlines():
            if line.startswith("OPTIMIZE_PREP_RESULT="):
                prep_result = json.loads(line.removeprefix("OPTIMIZE_PREP_RESULT="))
                break
        if prep_result is None:
            raise RuntimeError("Optimize prep stage did not emit OPTIMIZE_PREP_RESULT")
        _run_optimize_trainer_container(payload=payload)
        _run_optimize_finalize_stage(payload=payload, prep_result=prep_result)
        _run_optimize_evaluate_stage(payload=payload, prep_result=prep_result)
    else:
        raise RuntimeError(
            f"Unsupported compose Celery job type: {job_type}. "
            "No simulation fallback is enabled for unsupported job types."
        )
    return {"execution_name": execution_name, "status": "succeeded"}
