# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

"""Compose-mode trainer task shim."""

import logging
from collections.abc import Callable

from geti_types import Session

from jobs_common.runtime_helpers.k8s_resources_calculation import ComputeResources, EphemeralStorageResources
from jobs_common.runtime_helpers.trainer_image_info import TrainerImageInfo

logger = logging.getLogger(__name__)


def create_container_task(  # noqa: PLR0913
    session: Session,
    project_id: str,
    job_id: str,
    compute_resources: ComputeResources,
    ephemeral_storage_resources: EphemeralStorageResources,
    trainer_image_info: TrainerImageInfo,
    command: list[str],
    container_name: str,
    namespace: str = "impt",
) -> Callable[[], None]:
    """Return a compose-mode callable used by legacy task code paths.

    Trainer execution is orchestrated by the jobs service in compose mode. This
    shim keeps legacy task modules importable and callable without requiring
    legacy runtime objects.
    """

    _ = (
        session,
        project_id,
        job_id,
        compute_resources,
        ephemeral_storage_resources,
        trainer_image_info,
        command,
        container_name,
        namespace,
    )

    def _noop() -> None:
        logger.info(
            "Compose mode: trainer container is executed by scheduler/celery pipeline; "
            "legacy create_container_task callable is a no-op."
        )

    return _noop
