# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import logging
import os
from datetime import timedelta

from scheduler.state_machine import StateMachine

from iai_core.utils.time_utils import now

logger = logging.getLogger(__name__)

MAX_START_TIME_SEC = int(os.environ.get("MAX_START_TIME_SEC", 30))
logger.info(f"Max workflow start time is {MAX_START_TIME_SEC} second(s)")

MAX_START_TIME_SEC_TRAIN = int(os.environ.get("MAX_START_TIME_SEC_TRAIN", max(MAX_START_TIME_SEC, 3600)))
logger.info(f"Max workflow start time for train jobs is {MAX_START_TIME_SEC_TRAIN} second(s)")

MAX_CANCEL_TIME_SEC = int(os.environ.get("MAX_CANCEL_TIME_SEC", 30))
logger.info(f"Max workflow cancellation time is {MAX_CANCEL_TIME_SEC} second(s)")


def run_resetting_loop() -> None:
    """
    Runs the resetting loop iteration for the job scheduler
    """
    try:
        reset_timed_out_jobs_processings()
    except Exception:
        logger.exception("Error occurred in a job scheduler resetting loop")


def reset_timed_out_jobs_processings() -> None:
    """
    Resets timed out processings.
    Following steps are performed:

    1. All jobs in a CANCELING state which has been picked for scheduling more than MAX_START_TIME_SEC are reset, most
    probably scheduling process has been interrupted.
    They are returned either to SCHEDULED or to RUNNING state depending on previous state,
    and cancel_retry_counter is incremented.
    It will be picked again for canceling in next control loop iterations.

    2. All jobs in a SCHEDULING state which has been picked for scheduling more than MAX_START_TIME_SEC are reset, most
    probably scheduling process has been interrupted.
    They are returned to READY_FOR_SCHEDULING state, and start_retry_counter is incremented.
    It will be picked again for scheduling in next control loop iterations.

    2. All jobs in a REVERT_SCHEDULING state which has been picked for scheduling more than MAX_START_TIME_SEC are
    reset, most probably scheduling process has been interrupted.
    They are returned to READY_FOR_REVERT state, and start_retry_counter is incremented.
    It will be picked again for scheduling in next control loop iterations.

    """
    # Reset jobs which are in CANCELING status for too long
    threshold = now() - timedelta(seconds=MAX_CANCEL_TIME_SEC)
    StateMachine().reset_canceling_jobs(threshold=threshold)

    # Reset jobs which are in SCHEDULING status for too long.
    # Train jobs often spend substantial time in the compose preparation stage
    # before moving to RUNNING; use a dedicated, longer threshold to avoid
    # duplicate rescheduling.
    common_threshold = now() - timedelta(seconds=MAX_START_TIME_SEC)
    train_threshold = now() - timedelta(seconds=MAX_START_TIME_SEC_TRAIN)
    StateMachine().reset_scheduling_jobs_except_types(threshold=common_threshold, excluded_job_types=("train",))
    StateMachine().reset_scheduling_jobs_for_types(threshold=train_threshold, job_types=("train",))

    # Reset jobs which are in REVERT_SCHEDULING status for too long
    threshold = now() - timedelta(seconds=MAX_START_TIME_SEC)
    StateMachine().reset_revert_scheduling_jobs(threshold=threshold)
