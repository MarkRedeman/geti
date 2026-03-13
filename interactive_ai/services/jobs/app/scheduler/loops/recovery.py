# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import logging
import os

from model.job import Job
from scheduler.flyte import is_compose_mode
from scheduler.local_executor import LocalExecutor
from scheduler.state_machine import StateMachine

from geti_types import ID, RequestSource, make_session, session_context

logger = logging.getLogger(__name__)

BATCH_SIZE = int(os.environ.get("SCHEDULER_RECOVERY_BATCH_SIZE", 50))
logger.info(f"Recovery batch size is {BATCH_SIZE}")


def run_recovery_loop() -> None:
    """
    Runs the recovery loop iteration for the job scheduler
    """

    try:
        if not is_compose_mode():
            logger.error(
                "Feature unavailable outside compose mode: jobs.recovery_loop. "
                "Flyte-backed recovery path has been removed."
            )
            return

        logger.debug("[COMPOSE MODE] Running compose-native recovery loop")
        ids = StateMachine().get_session_ids_with_jobs_not_in_final_state()
        for organization_id, workspace_id in ids.items():
            check_and_recover_organization_if_needed(organization_id=organization_id, workspace_id=workspace_id)
    except Exception:
        logger.exception("Error occurred in a job scheduler recovery loop")


def check_and_recover_organization_if_needed(organization_id: ID, workspace_id: ID) -> None:
    """
    Checks all organization jobs and resets all the jobs missing in Flyte.
    :param organization_id: ID of organization to check
    :param workspace_id: ID of the workspace to check
    """
    logger.debug(f"Checking {organization_id} organization")
    with session_context(
        session=make_session(organization_id=organization_id, workspace_id=workspace_id, source=RequestSource.INTERNAL)
    ):
        active_jobs = list(StateMachine().get_scheduled_jobs_not_in_final_state())
        logger.debug(f"Found {len(active_jobs)} scheduled jobs not in final state")

        for i in range(0, len(active_jobs), BATCH_SIZE):
            batch = active_jobs[i : i + BATCH_SIZE]
            check_and_recover_organization_jobs_if_needed(jobs=batch)


def check_and_recover_organization_jobs_if_needed(jobs: list[Job]) -> None:
    """
    Checks workspace jobs and resets the jobs missing in Flyte.
    :param jobs: list of jobs to check
    """
    logger.debug(f"[COMPOSE MODE] Processing jobs {[job.id for job in jobs]}")
    executor = LocalExecutor()
    for job in jobs:
        execution_id = job.executions.main.execution_id
        if execution_id is None:
            continue

        record = executor.get_execution_metadata(execution_name=execution_id)
        if record is not None:
            continue

        logger.warning(f"Found active job {job.id} with missing local execution {execution_id}")
        StateMachine().reset_job_to_submitted_state(job_id=job.id)
