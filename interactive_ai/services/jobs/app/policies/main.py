# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import atexit
import logging
import os
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from opentelemetry import trace

from policies import Prioritizer

from geti_telemetry_tools import ENABLE_TRACING
from geti_types import RequestSource, make_session, session_context

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)  # type: ignore[attr-defined]
DEPLOYMENT_MODE = os.environ.get("DEPLOYMENT_MODE", "").lower()


def _is_compose_mode() -> bool:
    return DEPLOYMENT_MODE == "compose"


POLICY_LOOP_INTERVAL = int(os.environ.get("SCHEDULING_POLICY_SERVICE_LOOP_INTERVAL", 1))
logger.info(f"Running scheduling policy checks every {POLICY_LOOP_INTERVAL} second(s)")

RESOURCE_MANAGER_LOOP_INTERVAL = int(os.environ.get("RESOURCE_MANAGER_LOOP_INTERVAL", 60))
logger.info(f"Running resource manager every {RESOURCE_MANAGER_LOOP_INTERVAL} second(s)")

policy_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="scheduling_policy_service")
resource_manager_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="resource_manager")


def stop() -> None:
    """
    Stops the job scheduling policy service
    """
    logger.info("Shutting down")

    policy_executor.shutdown(wait=False)
    resource_manager_executor.shutdown(wait=False)


def start() -> None:
    """
    Control loop implementation
    """
    atexit.register(stop)

    policy_executor.submit(start_policy_loop)
    if _is_compose_mode():
        logger.warning(
            "Compose mode: resource_manager_loop is disabled (no Kubernetes). "
            "Initialising GPU capacity to [1] so CPU/GPU jobs can be scheduled."
        )
        _initialize_compose_gpu_capacity()
    else:
        resource_manager_executor.submit(start_resource_manager_loop)


def _initialize_compose_gpu_capacity() -> None:
    """
    In compose mode there is no Kubernetes node-capacity API, so we set a
    sensible default of [1] GPU directly on the ResourceManager singleton.
    This allows the scheduling policy to treat every job as schedulable rather
    than leaving GPU jobs stuck in SUBMITTED forever.
    """
    try:
        from policies import ResourceManager

        manager = ResourceManager()
        if manager.gpu_capacity is None:
            manager.gpu_capacity = [1]
            logger.info("Compose mode: ResourceManager.gpu_capacity initialised to [1].")
    except Exception:
        logger.exception("Compose mode: failed to initialise ResourceManager GPU capacity.")


def start_loop(loop_id: str, loop: Callable, loop_interval: int) -> None:
    """
    Starts a loop
    :param loop_id: loop identifier
    :param loop: loop implementation
    :param loop_interval: loop interval
    """
    while True:
        try:
            if ENABLE_TRACING:
                with tracer.start_as_current_span(loop_id):
                    loop()
            else:
                loop()
        finally:
            time.sleep(loop_interval)


def start_policy_loop() -> None:
    """
    Job scheduling policy loop implementation
    """
    start_loop("job-scheduling-policy-loop", run_policy_loop, POLICY_LOOP_INTERVAL)


def start_resource_manager_loop() -> None:
    """
    Resource manager loop implementation
    """
    start_loop("resource-manager-loop", run_resource_manager_loop, RESOURCE_MANAGER_LOOP_INTERVAL)


def run_policy_loop() -> None:
    """
    Starts the control loop for the job scheduler
    """
    prioritizer = Prioritizer()
    try:
        logger.debug("Running job scheduling policy loop...")
        ids = prioritizer.get_session_ids_with_submitted_jobs()
        for organization_id, workspace_id in ids.items():
            with session_context(
                session=make_session(
                    organization_id=organization_id, workspace_id=workspace_id, source=RequestSource.INTERNAL
                )
            ):
                prioritizer.mark_next_jobs_as_ready_for_scheduling_from_submitted_queue()
    except Exception:
        logger.exception("Error occurred in job scheduling policy loop")
    finally:
        time.sleep(POLICY_LOOP_INTERVAL)


def run_resource_manager_loop() -> None:
    """
    Starts the resource manager loop
    """
    try:
        logger.debug("Running resource manager loop...")
        from policies import ResourceManager

        ResourceManager().refresh_available_resources()
    except Exception:
        logger.exception("Error occurred in resource manager loop")
    finally:
        time.sleep(RESOURCE_MANAGER_LOOP_INTERVAL)


if __name__ == "__main__":
    start()

    while True:
        time.sleep(POLICY_LOOP_INTERVAL)
