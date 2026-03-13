# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import os
from unittest.mock import patch

from policies import main as policy_main


@patch("policies.main.policy_executor.submit")
@patch("policies.main.resource_manager_executor.submit")
def test_start_skips_resource_manager_in_compose(mock_resource_manager_submit, mock_policy_submit):
    with patch.dict(os.environ, {"DEPLOYMENT_MODE": "compose"}):
        # Refresh module-level mode cache for this test.
        policy_main.DEPLOYMENT_MODE = os.environ.get("DEPLOYMENT_MODE", "").lower()
        policy_main.start()

    mock_policy_submit.assert_called_once_with(policy_main.start_policy_loop)
    mock_resource_manager_submit.assert_not_called()
