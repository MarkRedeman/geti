# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

"""
Resource Manager module
"""

import asyncio
import logging

from geti_types import Singleton

logger = logging.getLogger(__name__)


class ResourceManager(metaclass=Singleton):
    """
    Resource Manager
    This module obtains information about cluster available resources and provides GPU capacity to clients
    """

    def __init__(self) -> None:
        """
        Initializes resource manager
        """
        self.gpu_capacity: list[int] | None = None

    def refresh_available_resources(self) -> None:
        """
        Fetches information about cluster available resources and gets cluster GPU capacity
        """
        new_gpu_capacity = asyncio.run(get_gpu_capacity())
        if sum(new_gpu_capacity) == 0:
            logger.warning("No GPUs are found in the cluster, fallback to gpu_capacity = 1")
            new_gpu_capacity = [1]

        if self.gpu_capacity is None:
            logger.info(f"Cluster GPU capacity is {new_gpu_capacity}")
        elif self.gpu_capacity != new_gpu_capacity:
            logger.info(f"Cluster GPU capacity has changed to {new_gpu_capacity}")
        self.gpu_capacity = new_gpu_capacity


async def get_gpu_capacity() -> list[int]:
    """Return GPU capacity from compose-friendly environment variables."""
    import os

    capacities_env = os.environ.get("GPU_CAPACITY", "").strip()
    if capacities_env:
        try:
            return [max(0, int(item.strip())) for item in capacities_env.split(",") if item.strip()]
        except ValueError:
            logger.warning("Invalid GPU_CAPACITY value '%s', falling back to GPU_COUNT", capacities_env)

    gpu_count = os.environ.get("GPU_COUNT", "1").strip()
    try:
        return [max(0, int(gpu_count))]
    except ValueError:
        logger.warning("Invalid GPU_COUNT value '%s', falling back to 1", gpu_count)
        return [1]
