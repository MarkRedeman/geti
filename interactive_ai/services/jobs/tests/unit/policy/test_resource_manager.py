# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE
from unittest.mock import patch

from policies.resource_manager import ResourceManager


def reset_singletons() -> None:
    ResourceManager._instance = None


@patch("policies.resource_manager.get_gpu_capacity")
def test_refresh_available_resources(mock_get_gpu_capacity, request) -> None:
    request.addfinalizer(reset_singletons)

    # Arrange
    mock_get_gpu_capacity.return_value = [5]

    assert ResourceManager().gpu_capacity is None

    # Act
    ResourceManager().refresh_available_resources()

    # Assert
    assert ResourceManager().gpu_capacity == [5]


@patch("policies.resource_manager.get_gpu_capacity")
def test_refresh_available_resources_no_gpus(mock_get_gpu_capacity, request) -> None:
    request.addfinalizer(reset_singletons)

    # Arrange
    mock_get_gpu_capacity.return_value = [0]

    assert ResourceManager().gpu_capacity is None

    # Act
    ResourceManager().refresh_available_resources()

    # Assert
    assert ResourceManager().gpu_capacity == [1]
