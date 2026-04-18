# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

from unittest.mock import patch

from job.workflows.export_project_workflow import export_project_workflow


class TestExportWorkflow:
    def test_export_workflow(self) -> None:
        project_id = "project_id"
        include_models = "all"
        with patch("job.workflows.export_project_workflow.export_project") as mock_export_project_task:
            export_project_workflow(
                project_id=project_id,
                include_models=include_models,
            )
        mock_export_project_task.assert_called_with(
            project_id=project_id,
            include_models=include_models,
        )
