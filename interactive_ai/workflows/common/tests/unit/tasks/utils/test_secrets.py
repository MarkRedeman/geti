# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import os
from unittest.mock import patch

from geti_types import ID, RequestSource

from jobs_common.tasks.utils.secrets import JobMetadata, env_vars, set_env_vars


class TestSecrets:
    def test_set_env_vars_noop(self) -> None:
        set_env_vars()

    @patch("jobs_common.tasks.utils.secrets.make_session")
    @patch("jobs_common.tasks.utils.secrets.set_env_vars")
    def test_env_vars(self, mock_set_env_vars, mock_make_session) -> None:
        # Arrange
        session_env_vars = {
            "SESSION_ORGANIZATION_ID": "organization_id",
            "SESSION_WORKSPACE_ID": "workspace_id",
        }

        @env_vars
        def test_function():
            pass

        # Act
        with patch.dict(os.environ, session_env_vars):
            test_function()

        # Assert
        mock_set_env_vars.assert_called_once_with()
        mock_make_session.assert_called_once_with(
            organization_id=ID("organization_id"),
            workspace_id=ID("workspace_id"),
            source=RequestSource.INTERNAL,
        )

    def test_job_metadata(self, fxt_job_metadata) -> None:
        # Act
        job_metadata = JobMetadata.from_env_vars()

        # Assert
        assert job_metadata.id == fxt_job_metadata.id
        assert job_metadata.type == fxt_job_metadata.type
        assert job_metadata.name == fxt_job_metadata.name
        assert job_metadata.author == fxt_job_metadata.author
        assert job_metadata.start_time == fxt_job_metadata.start_time
