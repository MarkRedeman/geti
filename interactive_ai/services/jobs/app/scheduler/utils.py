# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

"""
Job scheduler utils
"""

import os


def resolve_revert_job(job_type: str) -> tuple[str, str] | None:
    """
    Resolves a job type to a revert workflow name and version.
    Uses environment variables for mapping.

    Workflow name env var mapping: job_type -> "JOB_{job_type.upper()}_REVERT_FLYTE_WORKFLOW_NAME"
    Workflow version env var mapping: job_type -> "JOB_{job_type.upper()}_REVERT_FLYTE_WORKFLOW_VERSION"
    Note: these env var names retain "FLYTE" for backward compatibility.

    Example: job_type = train
    Workflow name env var: JOB_TRAIN_REVERT_FLYTE_WORKFLOW_NAME
    Workflow version env var: JOB_TRAIN_REVERT_FLYTE_WORKFLOW_VERSION

    :param job_type: Job type
    :return Tuple[str, str]: workflow name and version
    """
    workflow_name = os.environ.get(f"JOB_{job_type.upper()}_REVERT_FLYTE_WORKFLOW_NAME", None)
    if workflow_name is None:
        return None

    workflow_version = os.environ.get(f"JOB_{job_type.upper()}_REVERT_FLYTE_WORKFLOW_VERSION", None)
    if workflow_version is None:
        return None

    return workflow_name, workflow_version



def get_revert_execution_name(job_id: str) -> str:
    """
    Returns the revert execution name for a job.
    Revert execution name is the main execution name plus a "-revert" suffix.

    :param job_id: Job ID
    :return str: revert execution name
    """

    return f"{get_main_execution_name(job_id=job_id)}-revert"


def get_main_execution_name(job_id: str) -> str:
    """
    Returns the main execution name for a job.
    The execution name matches the job ID with an "ex-" prefix
    (required so the execution ID starts with a-z).

    :param job_id: Job ID
    :return str: main execution name
    """

    return f"ex-{job_id}"
