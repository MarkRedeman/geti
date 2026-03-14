# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import logging
import os

from model.job import Job
from scheduler.flyte import ExecutionType
from scheduler.local_executor import LocalExecutor
from scheduler.state_machine import StateMachine
from scheduler.utils import get_revert_execution_name, resolve_revert_job

from geti_telemetry_tools import unified_tracing
from geti_types import ID, session_context

logger = logging.getLogger(__name__)

MAX_START_RETRY_COUNT = int(os.environ.get("MAX_START_RETRY_COUNT", 5))
logger.info(f"Max start retries number is {MAX_START_RETRY_COUNT}")


def run_revert_scheduling_loop() -> None:
    """
    Runs the revert scheduling loop iteration for the job scheduler
    """

    try:
        while True:
            logger.debug("Running job scheduler revert scheduling loop iteration...")
            job = StateMachine().find_and_lock_job_for_reverting()
            if job is None:
                break

            with session_context(session=job.session):
                schedule_revert_job(job_id=job.id)
    except Exception:
        logger.exception("Error occurred in a job scheduler revert scheduling loop")


def schedule_revert_job(job_id: ID) -> None:
    """
    Schedules a revert job execution.

    If this is not the first attempt to schedule this job and number of retries exceeded allowed maximum, transfers
    the job either to FAILED state or to CANCELLED state depending ob cancelled flag.
    If this is not the first attempt to schedule this job and the maximum number of retries has not been reached,
    attempt to obtain an existing execution.
    If execution is found, uses it. Otherwise starts a new execution.
    Updates the job and sets SCHEDULED state.
    If execution start fails, sets READY_FOR_REVERT state.
    :param job_id: Job ID
    """
    logger.info(f"Job a revert execution to be scheduled for: {job_id}")
    job = StateMachine().get_by_id(job_id=job_id)

    if job is None:
        logger.error(f"Unable to find job {job_id}")
        return

    start_retry_counter = job.executions.revert.start_retry_counter if job.executions.revert is not None else None

    def set_final_state():
        if job.cancellation_info.is_cancelled:
            StateMachine().set_and_publish_cancelled_state(job_id=job_id)
        else:
            StateMachine().set_and_publish_failed_state(job_id=job_id)

    # If the number of retries exceeded maximum, set FAILED state
    if start_retry_counter is not None and start_retry_counter > MAX_START_RETRY_COUNT:
        logger.critical(f"Job {job_id} revert execution failed to start {start_retry_counter} time(s)")
        set_final_state()
        return

    try:
        execution = start_revert_execution(job=job)
        if execution is None:
            set_final_state()
            return

        execution_id = execution
        StateMachine().set_revert_scheduled_state(
            job_id=job_id,
            execution_id=execution_id,
        )
    except Exception:
        logger.exception(f"Failed to schedule revert execution for job {job_id}")
        StateMachine().reset_revert_scheduling_job(job_id=job_id)


@unified_tracing
def start_revert_execution(job: Job) -> str | None:
    """
    Starts jobs revert execution.

    Launches via LocalExecutor (Docker/Celery compose runtime) and returns
    the execution_name string.

    :param job: Job to start revert execution for
    :return: execution_name (compose) | None
    """
    execution_name = get_revert_execution_name(job_id=job.id)

    # Resolving revert workflow/image for this job type
    resolved = resolve_revert_job(job_type=job.type)
    if resolved is None:
        return None

    container_id = LocalExecutor().start_execution(
        execution_name=execution_name,
        job_id=str(job.id),
        workspace_id=str(job.workspace_id),
        organization_id=str(job.session.organization_id),
        execution_type=ExecutionType.REVERT,
        job_type=job.type,
        payload={},
        session_headers=list(job.session.as_list_bytes()),
    )
    logger.info(
        f"Revert execution started locally (compose mode): execution_name={execution_name}, container_id={container_id}"
    )
    return execution_name


@unified_tracing
def start_execution(*args, **kwargs):  # noqa: ANN002, ANN003, ANN201
    raise RuntimeError(
        "Feature unavailable outside compose mode: jobs.start_execution. "
        "Flyte-backed revert scheduling path has been removed."
    )
