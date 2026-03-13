# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import time

from scheduler.celery_app import celery_app


@celery_app.task(bind=True, name="scheduler.run_job_execution")
def run_job_execution(self, execution_name: str, payload: dict):  # noqa: ANN001
    """
    Transitional Celery task for compose mode.

    For now it simulates work to produce deterministic RUNNING -> SUCCEEDED
    transitions through LocalExecutor's event bridge.
    """
    duration = float(payload.get("sim_duration_sec", 2))
    time.sleep(duration)
    return {"execution_name": execution_name, "status": "succeeded"}
