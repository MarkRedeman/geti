# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import os
from unittest.mock import patch

from policies import main as policy_main
from policies.resource_manager import ResourceManager


def reset_resource_manager() -> None:
    ResourceManager._instance = None


@patch("policies.main.policy_executor.submit")
def test_start_skips_resource_manager_in_compose(mock_policy_submit):
    with patch.dict(os.environ, {}, clear=False):
        policy_main.start()

    mock_policy_submit.assert_called_once_with(policy_main.start_policy_loop)


@patch("policies.main.policy_executor.submit")
def test_initialize_compose_gpu_capacity_sets_default(mock_policy_submit, request):
    """In compose mode, _initialize_compose_gpu_capacity should set gpu_capacity=[1] on ResourceManager."""
    request.addfinalizer(reset_resource_manager)

    with patch.dict(os.environ, {}, clear=False):
        policy_main.start()

    assert ResourceManager().gpu_capacity == [1]


@patch("policies.main.policy_executor.submit")
def test_initialize_compose_gpu_capacity_skips_if_already_set(mock_policy_submit, request):
    """_initialize_compose_gpu_capacity should not overwrite an already-set gpu_capacity."""
    request.addfinalizer(reset_resource_manager)
    ResourceManager().gpu_capacity = [4]

    with patch.dict(os.environ, {}, clear=False):
        policy_main.start()

    # Should remain at [4], not reset to [1].
    assert ResourceManager().gpu_capacity == [4]
