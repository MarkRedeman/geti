# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

from unittest.mock import patch

from job.workflows.model_test_workflow import model_test_workflow


class TestModelTest:
    def test_model_test(self) -> None:
        with (
            patch("job.workflows.model_test_workflow.run_model_test") as mock_model_test,
        ):
            model_test_workflow(
                project_id="project_id",
                model_test_result_id="model_test_result_id",
            )
        mock_model_test.assert_called_once()
