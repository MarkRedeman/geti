# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import json
import logging
import os
import subprocess
from scheduler.celery_app import celery_app

logger = logging.getLogger(__name__)

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


def _workflow_docker_network() -> str:
    return os.environ.get("WORKFLOW_DOCKER_NETWORK", "geti")


def _docker_run_cmd() -> list[str]:
    cmd = ["docker", "run", "--rm", "--network", _workflow_docker_network()]
    trainer_version = os.environ.get("DEFAULT_TRAINER_VERSION")
    if trainer_version:
        cmd += ["--env", f"DEFAULT_TRAINER_VERSION={trainer_version}"]
    return cmd


def _should_forward_env(key: str, prefixes: tuple[str, ...]) -> bool:
    if key == "DEFAULT_TRAINER_VERSION":
        return True
    return any(key.startswith(p) for p in prefixes)


def _session_org_id(payload: dict) -> str:
    value = payload.get("organization_id")
    if not value:
        raise KeyError("organization_id is missing from job payload; cannot build SESSION_ORGANIZATION_ID")
    return str(value)


def _session_workspace_id(payload: dict) -> str:
    value = payload.get("workspace_id")
    if not value:
        raise KeyError("workspace_id is missing from job payload; cannot build SESSION_WORKSPACE_ID")
    return str(value)


def _job_metadata_id(payload: dict) -> str:
    value = payload.get("job_id")
    if not value:
        raise KeyError("job_id is missing from job payload; cannot build JOB_METADATA_ID")
    return str(value)


def _job_metadata_name(payload: dict) -> str:
    value = payload.get("job_name")
    if not value:
        raise KeyError("job_name is missing from job payload; cannot build JOB_METADATA_NAME")
    return str(value)


def _job_metadata_author(payload: dict) -> str:
    value = payload.get("author")
    if not value:
        raise KeyError("author is missing from job payload; cannot build JOB_METADATA_AUTHOR")
    return str(value)


def _job_metadata_start_time(payload: dict) -> str:
    value = payload.get("start_time")
    if not value:
        raise KeyError("start_time is missing from job payload; cannot build JOB_METADATA_START_TIME")
    return str(value)


def _dataset_ie_image() -> str:
    return os.environ.get("DATASET_IE_WORKFLOW_IMAGE", "")


def _project_ie_image() -> str:
    return os.environ.get("PROJECT_IE_WORKFLOW_IMAGE", "")


def _model_test_image() -> str:
    return os.environ.get("MODEL_TEST_WORKFLOW_IMAGE", "")


def _train_workflow_image() -> str:
    return os.environ.get("TRAIN_WORKFLOW_IMAGE", "")


def _trainer_runtime_image() -> str:
    accelerator = os.environ.get("TRAINER_RUNTIME_ACCELERATOR", "gpu").lower()
    if accelerator == "xpu":
        return os.environ.get("TRAINER_RUNTIME_XPU_IMAGE", "")
    return os.environ.get("TRAINER_RUNTIME_IMAGE", "")


def _trainer_runtime_accelerator() -> str:
    return os.environ.get("TRAINER_RUNTIME_ACCELERATOR", "gpu").lower()


def _trainer_shard_files_dir() -> str:
    """
    Return a writable shard-files path for trainer runtime containers.

    In compose mode, SHARD_FILES_DIR may be inherited as `/shard_files` (K8s-style path),
    which is not writable in the trainer runtime image. Remap to `/tmp/shard_files`.
    """
    shard_files_dir = os.environ.get("SHARD_FILES_DIR", "/tmp/shard_files")
    if shard_files_dir == "/shard_files":
        return "/tmp/shard_files"
    return shard_files_dir


def _optimize_workflow_image() -> str:
    return os.environ.get("OPTIMIZE_WORKFLOW_IMAGE", "")


def _run_optimize_trainer_container(payload: dict) -> None:
    image = _trainer_runtime_image()
    if not image:
        raise RuntimeError("Missing trainer runtime image for optimize_pot job")

    org_id = _session_org_id(payload)
    workspace_id = _session_workspace_id(payload)
    project_id = payload["project_id"]
    job_id = _job_metadata_id(payload)
    identifier_json = json.dumps(
        {
            "organization_id": str(org_id),
            "workspace_id": str(workspace_id),
            "project_id": str(project_id),
            "job_id": str(job_id),
        }
    )

    cmd = _docker_run_cmd()
    _forward_prefixes = (
        "DATABASE_",
        "MONGODB_",
        "KAFKA_",
        "SPICEDB_",
        "S3_",
        "JOBS_SCHEDULER",
        "SIGNING_IE_PRIVKEY",
        "CELERY_",
        "OTEL_",
        "ENABLE_",
        "FEATURE_FLAG_",
        "WORKFLOW_",
        "DEFAULT_TRAINER_VERSION",
        "MODEL_REGISTRATION_",
        "STORAGE_",
        "BUCKET_NAME_",
    )
    for key in os.environ:
        if _should_forward_env(key=key, prefixes=_forward_prefixes):
            cmd += ["--env", key]

    _append_trainer_runtime_env(cmd)

    accelerator = _trainer_runtime_accelerator()
    if accelerator == "xpu":
        xpu_devices = os.environ.get("TRAINER_RUNTIME_XPU_DEVICES", "/dev/dri")
        for device in xpu_devices.split(","):
            device = device.strip()
            if device:
                cmd += ["--device", device]

    cmd += ["--env", f"IDENTIFIER_JSON={identifier_json}"]
    cmd += ["--env", f"SHARD_FILES_DIR={_trainer_shard_files_dir()}"]
    cmd += ["--env", "TASK_ID=optimize"]
    cmd += ["--env", "JOB_TYPE=optimize_pot"]
    cmd += ["--env", f"SESSION_ORGANIZATION_ID={str(org_id)}"]
    cmd += ["--env", f"SESSION_WORKSPACE_ID={str(workspace_id)}"]
    cmd += ["--env", f"JOB_METADATA_ID={str(job_id)}"]
    cmd += ["--env", "JOB_METADATA_TYPE=optimize_pot"]
    cmd += ["--env", f"JOB_METADATA_NAME={_job_metadata_name(payload)}"]
    cmd += ["--env", f"JOB_METADATA_AUTHOR={_job_metadata_author(payload)}"]
    cmd += ["--env", f"JOB_METADATA_START_TIME={_job_metadata_start_time(payload)}"]

    trainer_command = os.environ.get("TRAINER_RUNTIME_COMMAND", "run")
    cmd += [image, "bash", "-c", trainer_command]
    _ = subprocess.run(cmd, check=True, timeout=7200)  # noqa: S603


def _run_optimize_finalize_stage(payload: dict, prep_result: dict) -> None:
    image = _optimize_workflow_image()
    if not image:
        raise RuntimeError("Missing OPTIMIZE_WORKFLOW_IMAGE for optimize finalize stage")

    cmd = _docker_run_cmd()
    _forward_prefixes = (
        "DATABASE_",
        "MONGODB_",
        "KAFKA_",
        "SPICEDB_",
        "S3_",
        "JOBS_SCHEDULER",
        "SIGNING_IE_PRIVKEY",
        "CELERY_",
        "OTEL_",
        "ENABLE_",
        "FEATURE_FLAG_",
        "WORKFLOW_",
        "DEFAULT_TRAINER_VERSION",
        "MODEL_REGISTRATION_",
        "STORAGE_",
        "BUCKET_NAME_",
    )
    for key in os.environ:
        if _should_forward_env(key=key, prefixes=_forward_prefixes):
            cmd += ["--env", key]

    _append_trainer_runtime_env(cmd)

    cmd += ["--env", f"SESSION_ORGANIZATION_ID={_session_org_id(payload)}"]
    cmd += ["--env", f"SESSION_WORKSPACE_ID={_session_workspace_id(payload)}"]
    cmd += ["--env", f"JOB_METADATA_ID={_job_metadata_id(payload)}"]
    cmd += ["--env", "JOB_METADATA_TYPE=optimize_pot"]
    cmd += ["--env", f"JOB_METADATA_NAME={_job_metadata_name(payload)}"]
    cmd += ["--env", f"JOB_METADATA_AUTHOR={_job_metadata_author(payload)}"]
    cmd += ["--env", f"JOB_METADATA_START_TIME={_job_metadata_start_time(payload)}"]

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

    cmd = _docker_run_cmd()
    _forward_prefixes = (
        "DATABASE_",
        "MONGODB_",
        "KAFKA_",
        "SPICEDB_",
        "S3_",
        "JOBS_SCHEDULER",
        "SIGNING_IE_PRIVKEY",
        "CELERY_",
        "OTEL_",
        "ENABLE_",
        "FEATURE_FLAG_",
        "WORKFLOW_",
        "DEFAULT_TRAINER_VERSION",
        "MODEL_REGISTRATION_",
        "STORAGE_",
        "BUCKET_NAME_",
    )
    for key in os.environ:
        if _should_forward_env(key=key, prefixes=_forward_prefixes):
            cmd += ["--env", key]

    _append_trainer_runtime_env(cmd)

    cmd += ["--env", f"SESSION_ORGANIZATION_ID={_session_org_id(payload)}"]
    cmd += ["--env", f"SESSION_WORKSPACE_ID={_session_workspace_id(payload)}"]
    cmd += ["--env", f"JOB_METADATA_ID={_job_metadata_id(payload)}"]
    cmd += ["--env", "JOB_METADATA_TYPE=optimize_pot"]
    cmd += ["--env", f"JOB_METADATA_NAME={_job_metadata_name(payload)}"]
    cmd += ["--env", f"JOB_METADATA_AUTHOR={_job_metadata_author(payload)}"]
    cmd += ["--env", f"JOB_METADATA_START_TIME={_job_metadata_start_time(payload)}"]

    cmd += ["--env", f"WORKFLOW_PAYLOAD_JSON={json.dumps(payload)}"]
    cmd += ["--env", "WORKFLOW_JOB_TYPE=optimize_pot"]
    cmd += ["--env", "WORKFLOW_JOB_STAGE=evaluate"]
    cmd += ["--env", f"OPTIMIZE_PREP_RESULT_JSON={json.dumps(prep_result)}"]
    cmd += [image, *_workflow_runner_command()]
    _ = subprocess.run(cmd, check=True, timeout=3600)  # noqa: S603


def _run_train_trainer_container(payload: dict, execution_name: str) -> None:
    """
    Transitional trainer runtime stage for train jobs.

    This runs the trainer image after train-data/model preparation has completed.
    """
    image = _trainer_runtime_image()
    if not image:
        raise RuntimeError("Missing trainer runtime image for train job")

    org_id = _session_org_id(payload)
    workspace_id = _session_workspace_id(payload)
    project_id = payload["project_id"]
    job_id = _job_metadata_id(payload)
    identifier_json = json.dumps(
        {
            "organization_id": str(org_id),
            "workspace_id": str(workspace_id),
            "project_id": str(project_id),
            "job_id": str(job_id),
        }
    )

    cmd = _docker_run_cmd()

    _forward_prefixes = (
        "DATABASE_",
        "MONGODB_",
        "KAFKA_",
        "SPICEDB_",
        "S3_",
        "JOBS_SCHEDULER",
        "SIGNING_IE_PRIVKEY",
        "CELERY_",
        "OTEL_",
        "ENABLE_",
        "FEATURE_FLAG_",
        "WORKFLOW_",
        "TRAINER_RUNTIME_",
        "TRAINER_RENDER_GID",
        "DEFAULT_TRAINER_VERSION",
        "MODEL_REGISTRATION_",
        "STORAGE_",
        "BUCKET_NAME_",
    )
    for key in os.environ:
        if _should_forward_env(key=key, prefixes=_forward_prefixes):
            cmd += ["--env", key]

    trainer_shm_size = os.environ.get("TRAINER_RUNTIME_SHM_SIZE", "2g")
    if trainer_shm_size:
        cmd += ["--shm-size", trainer_shm_size]

    accelerator = _trainer_runtime_accelerator()
    if accelerator == "xpu":
        xpu_devices = os.environ.get("TRAINER_RUNTIME_XPU_DEVICES", "/dev/dri")
        for device in xpu_devices.split(","):
            device = device.strip()
            if device:
                cmd += ["--device", device]
    else:
        trainer_gpu_request = os.environ.get("TRAINER_RUNTIME_GPU_REQUEST", "all")
        if trainer_gpu_request:
            cmd += ["--gpus", trainer_gpu_request]

    cmd += ["--env", f"IDENTIFIER_JSON={identifier_json}"]
    cmd += ["--env", f"EXECUTION_ID={execution_name}"]
    cmd += ["--env", f"SESSION_ORGANIZATION_ID={str(org_id)}"]
    cmd += ["--env", f"SESSION_WORKSPACE_ID={str(workspace_id)}"]
    cmd += ["--env", f"JOB_METADATA_ID={str(job_id)}"]
    cmd += ["--env", f"SHARD_FILES_DIR={_trainer_shard_files_dir()}"]
    cmd += ["--env", "WEIGHTS_URL=https://storage.geti.intel.com/weights"]
    cmd += ["--env", "JOB_METADATA_TYPE=train"]
    cmd += ["--env", f"JOB_METADATA_NAME={_job_metadata_name(payload)}"]
    cmd += ["--env", f"JOB_METADATA_AUTHOR={_job_metadata_author(payload)}"]
    cmd += ["--env", f"JOB_METADATA_START_TIME={_job_metadata_start_time(payload)}"]
    cmd += ["--env", "TASK_ID=train"]

    trainer_command = os.environ.get("TRAINER_RUNTIME_COMMAND", "bash -c run")
    cmd += [image, "bash", "-c", trainer_command]
    subprocess.run(cmd, check=True, timeout=7200)  # noqa: S603


def _run_train_finalize_stage(payload: dict, prep_result: dict, execution_name: str) -> None:
    image = _train_workflow_image()
    if not image:
        raise RuntimeError("Missing TRAIN_WORKFLOW_IMAGE for train finalize stage")

    cmd = _docker_run_cmd()
    _forward_prefixes = (
        "DATABASE_",
        "MONGODB_",
        "KAFKA_",
        "SPICEDB_",
        "S3_",
        "JOBS_SCHEDULER",
        "SIGNING_IE_PRIVKEY",
        "CELERY_",
        "OTEL_",
        "ENABLE_",
        "FEATURE_FLAG_",
        "WORKFLOW_",
        "TRAINER_RUNTIME_",
        "TRAINER_RENDER_GID",
        "DEFAULT_TRAINER_VERSION",
        "MODEL_REGISTRATION_",
        "STORAGE_",
        "BUCKET_NAME_",
    )
    for key in os.environ:
        if _should_forward_env(key=key, prefixes=_forward_prefixes):
            cmd += ["--env", key]

    cmd += ["--env", f"WORKFLOW_EXECUTION_ID={execution_name}"]
    cmd += ["--env", f"SESSION_ORGANIZATION_ID={_session_org_id(payload)}"]
    cmd += ["--env", f"SESSION_WORKSPACE_ID={_session_workspace_id(payload)}"]
    cmd += ["--env", f"JOB_METADATA_ID={_job_metadata_id(payload)}"]
    cmd += ["--env", "JOB_METADATA_TYPE=train"]
    cmd += ["--env", f"JOB_METADATA_NAME={_job_metadata_name(payload)}"]
    cmd += ["--env", f"JOB_METADATA_AUTHOR={_job_metadata_author(payload)}"]
    cmd += ["--env", f"JOB_METADATA_START_TIME={_job_metadata_start_time(payload)}"]
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


def _run_train_evaluate_stage(payload: dict, prep_result: dict, execution_name: str) -> None:
    image = _train_workflow_image()
    if not image:
        raise RuntimeError("Missing TRAIN_WORKFLOW_IMAGE for train evaluate stage")

    cmd = _docker_run_cmd()
    _forward_prefixes = (
        "DATABASE_",
        "MONGODB_",
        "KAFKA_",
        "SPICEDB_",
        "S3_",
        "JOBS_SCHEDULER",
        "SIGNING_IE_PRIVKEY",
        "CELERY_",
        "OTEL_",
        "ENABLE_",
        "FEATURE_FLAG_",
        "WORKFLOW_",
        "TRAINER_RUNTIME_",
        "TRAINER_RENDER_GID",
        "MODEL_REGISTRATION_",
        "STORAGE_",
        "BUCKET_NAME_",
    )
    for key in os.environ:
        if any(key.startswith(p) for p in _forward_prefixes):
            cmd += ["--env", key]

    cmd += ["--env", f"WORKFLOW_EXECUTION_ID={execution_name}"]
    cmd += ["--env", f"SESSION_ORGANIZATION_ID={_session_org_id(payload)}"]
    cmd += ["--env", f"SESSION_WORKSPACE_ID={_session_workspace_id(payload)}"]
    cmd += ["--env", f"JOB_METADATA_ID={_job_metadata_id(payload)}"]
    cmd += ["--env", "JOB_METADATA_TYPE=train"]
    cmd += ["--env", f"JOB_METADATA_NAME={_job_metadata_name(payload)}"]
    cmd += ["--env", f"JOB_METADATA_AUTHOR={_job_metadata_author(payload)}"]
    cmd += ["--env", f"JOB_METADATA_START_TIME={_job_metadata_start_time(payload)}"]
    cmd += ["--env", f"WORKFLOW_PAYLOAD_JSON={json.dumps(payload)}"]
    cmd += ["--env", "WORKFLOW_JOB_TYPE=train"]
    cmd += ["--env", "WORKFLOW_JOB_STAGE=evaluate"]
    cmd += ["--env", f"TRAIN_PREP_RESULT_JSON={json.dumps(prep_result)}"]
    cmd += [image, *_workflow_runner_command()]
    _ = subprocess.run(cmd, check=True, timeout=3600)  # noqa: S603


def _workflow_runner_command() -> list[str]:
    return ["python", "-m", "jobs_common.compose.workflow_runner"]


def _append_trainer_runtime_env(cmd: list[str]) -> None:
    """Append trainer runtime env vars explicitly for workflow containers."""
    for key in (
        "TRAINER_RUNTIME_IMAGE",
        "TRAINER_RUNTIME_XPU_IMAGE",
        "TRAINER_RUNTIME_ACCELERATOR",
        "TRAINER_RENDER_GID",
    ):
        if value := os.environ.get(key):
            cmd += ["--env", f"{key}={value}"]


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

    cmd = _docker_run_cmd()

    _forward_prefixes = (
        "DATABASE_",
        "MONGODB_",
        "KAFKA_",
        "SPICEDB_",
        "S3_",
        "JOBS_SCHEDULER",
        "SIGNING_IE_PRIVKEY",
        "CELERY_",
        "OTEL_",
        "ENABLE_",
        "FEATURE_FLAG_",
        "WORKFLOW_",
        "TRAINER_RUNTIME_",
        "TRAINER_RENDER_GID",
        "MODEL_REGISTRATION_",
        "STORAGE_",
        "BUCKET_NAME_",
    )
    for key in os.environ:
        if any(key.startswith(p) for p in _forward_prefixes):
            cmd += ["--env", key]

    _append_trainer_runtime_env(cmd)

    cmd += ["--env", f"WORKFLOW_PAYLOAD_JSON={json.dumps(payload)}"]
    cmd += ["--env", f"WORKFLOW_JOB_TYPE={job_type}"]
    cmd += ["--env", f"SESSION_ORGANIZATION_ID={_session_org_id(payload)}"]
    cmd += ["--env", f"SESSION_WORKSPACE_ID={_session_workspace_id(payload)}"]
    cmd += ["--env", f"JOB_METADATA_ID={_job_metadata_id(payload)}"]
    cmd += ["--env", f"JOB_METADATA_TYPE={job_type}"]
    cmd += ["--env", f"JOB_METADATA_NAME={_job_metadata_name(payload)}"]
    cmd += ["--env", f"JOB_METADATA_AUTHOR={_job_metadata_author(payload)}"]
    cmd += ["--env", f"JOB_METADATA_START_TIME={_job_metadata_start_time(payload)}"]

    cmd += [image, *_workflow_runner_command()]
    try:
        result = subprocess.run(cmd, check=True, timeout=3600, capture_output=True, text=True)  # noqa: S603
    except subprocess.CalledProcessError as err:
        logger.error(
            "Workflow container failed for job_type=%s job_id=%s (exit=%s)\nstdout:\n%s\nstderr:\n%s",
            job_type,
            _job_metadata_id(payload),
            err.returncode,
            (err.stdout or "").strip(),
            (err.stderr or "").strip(),
        )
        raise
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
        _run_train_trainer_container(payload=payload, execution_name=execution_name)
        should_finalize = True
        try:
            should_finalize = _should_run_train_finalize(prep_result=prep_result)
        except ModuleNotFoundError as exc:
            logger.warning(
                "Train finalize readiness check failed in compose mode; running finalize stage by default. "
                f"Reason: {exc}"
            )

        if should_finalize:
            _run_train_finalize_stage(payload=payload, prep_result=prep_result, execution_name=execution_name)
        _run_train_evaluate_stage(payload=payload, prep_result=prep_result, execution_name=execution_name)
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
