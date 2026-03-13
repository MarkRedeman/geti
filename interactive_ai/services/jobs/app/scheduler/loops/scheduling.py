# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import logging
import os

from model.job import Job, JobStepDetails, JobTaskExecutionBranch
from model.job_state import JobTaskState
from scheduler.flyte import ExecutionType, is_compose_mode
from scheduler.jobs_templates import JobsTemplates
from scheduler.local_executor import LocalExecutor
from scheduler.state_machine import StateMachine
from scheduler.utils import get_main_execution_name

from geti_telemetry_tools import unified_tracing
from geti_types import ID, session_context

logger = logging.getLogger(__name__)

MAX_START_RETRY_COUNT = int(os.environ.get("MAX_START_RETRY_COUNT", 5))
logger.info(f"Max start retries number is {MAX_START_RETRY_COUNT}")


def run_scheduling_loop() -> None:
    """
    Runs the scheduling loop iteration for the job scheduler
    """

    try:
        logger.debug("Running job scheduler scheduling loop iteration...")
        while True:
            job = StateMachine().find_and_lock_job_for_scheduling()
            if job is None:
                break

            with session_context(session=job.session):
                schedule_main_job(job_id=job.id)
    except Exception:
        logger.exception("Error occurred in a job scheduler scheduling loop")


def schedule_main_job(job_id: ID) -> None:
    """
    Schedules a main job execution.

    If this is not the first attempt to schedule this job and number of retries exceeded allowed maximum, transfers
    the job to FAILED state.
    If this is not the first attempt to schedule this job and the maximum number of retries has not been reached,
    attempt to obtain Flyte execution.
    If execution is found, uses it. Otherwise starts execution in Flyte.
    Updates the job and sets SCHEDULED state.
    If Flyte execution start fails, sets READY_FOR_SCHEDULING state.
    :param job_id: Job ID
    """
    logger.info(f"Job to be scheduled: {job_id}")
    job = StateMachine().get_by_id(job_id=job_id)
    if job is None:
        logger.error(f"Unable to find job {job_id}")
        return

    start_retry_counter = job.executions.main.start_retry_counter

    # If the number of retries exceeded maximum, set FAILED state
    if start_retry_counter is not None and start_retry_counter > MAX_START_RETRY_COUNT:
        logger.warning(f"Job {job_id} main execution failed to start {start_retry_counter} time(s)")
        StateMachine().set_and_publish_failed_state(job_id=job_id)
        return

    try:
        execution_name, launch_plan_id = start_main_execution(job=job)
        job_steps = JobsTemplates().get_job_steps(job_type=job.type)

        step_details = [
            JobStepDetails(
                index=index + 1,
                task_id=job_step.task_id,
                step_name=job_step.name,
                state=JobTaskState.WAITING,
                branches=(
                    tuple(
                        JobTaskExecutionBranch(
                            condition=branch.condition,
                            branch=branch.branch,
                        )
                        for branch in job_step.branches
                    )
                    if job_step.branches is not None and len(job_step.branches) > 0
                    else None
                ),
                progress=-1,
            )
            for index, job_step in enumerate(job_steps)
        ]

        # Update job in database
        StateMachine().set_scheduled_state(
            job_id=job_id,
            flyte_launch_plan_id=launch_plan_id,
            flyte_execution_id=execution_name,
            step_details=step_details,
        )
    except Exception:
        logger.exception(f"Failed to schedule execution for job {job_id}")
        StateMachine().reset_scheduling_job(job_id=job_id)


@unified_tracing
def start_main_execution(job: Job) -> tuple[str, str]:
    """
    Starts jobs main execution.

    In compose mode, launches via LocalExecutor (Docker).
    Outside compose mode this path is not supported.

    :param job: Job to start main execution for
    :return: Tuple of (execution_name, launch_plan_id).
             In compose mode launch_plan_id equals execution_name.
    """
    execution_name = get_main_execution_name(job_id=job.id)

    if not is_compose_mode():
        raise RuntimeError(
            "Feature unavailable outside compose mode: jobs.start_main_execution. "
            "Flyte-backed scheduling path has been removed."
        )

    container_id = LocalExecutor().start_execution(
        execution_name=execution_name,
        job_id=str(job.id),
        workspace_id=str(job.workspace_id),
        organization_id=str(job.session.organization_id),
        execution_type=ExecutionType.MAIN,
        job_type=job.type,
        payload=job.payload,
        session_headers=list(job.session.as_list_bytes()),
    )
    logger.info(
        f"Job execution started locally (compose mode): execution_name={execution_name}, container_id={container_id}"
    )
    return execution_name, execution_name


@unified_tracing
def start_execution(*args, **kwargs):  # noqa: ANN002, ANN003, ANN201
    raise RuntimeError(
        "Feature unavailable outside compose mode: jobs.start_execution. Flyte-backed scheduling path has been removed."
    )
