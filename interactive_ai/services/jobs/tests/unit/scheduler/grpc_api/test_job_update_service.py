# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import datetime
from unittest.mock import MagicMock, patch

import grpc
import pandas  # noqa: F401 this import is needed to make freezegun work correctly with pandas
import pytest
from pymongo.errors import ServerSelectionTimeoutError

from model.job import JobConsumedResource
from scheduler.grpc_api.job_update_service import JobUpdateService
from scheduler.state_machine import StateMachine

from geti_types import ID
from grpc_interfaces.job_update.pb.job_update_service_pb2 import (
    EXECUTION_NOT_FOUND,
    INVALID_METADATA_UPDATE,
    JobUpdateRequest,
)


@pytest.fixture
def fxt_job_update_service():
    yield JobUpdateService()


@pytest.fixture
def fxt_grpc_context():
    yield MagicMock()


class TestJobUpdateService:
    @patch("scheduler.grpc_api.job_update_service.is_compose_mode", return_value=False)
    def test_job_update_non_compose_returns_unimplemented(
        self, mock_is_compose_mode, fxt_job_update_service, fxt_grpc_context
    ) -> None:
        # Act
        request = JobUpdateRequest(execution_id="execution_id", metadata='{"foo": "bar"}')
        fxt_job_update_service.job_update(request, fxt_grpc_context)

        # Assert
        mock_is_compose_mode.assert_called_once_with()
        fxt_grpc_context.abort.assert_called_once()

    @patch("scheduler.grpc_api.job_update_service.LocalExecutor")
    @patch("scheduler.grpc_api.job_update_service.is_compose_mode", return_value=True)
    def test_job_update_no_execution(
        self, mock_is_compose_mode, mock_local_executor, request, fxt_job_update_service, fxt_grpc_context
    ) -> None:
        mock_local_executor.return_value.get_execution_metadata.return_value = None

        # Act
        request = JobUpdateRequest(execution_id="execution_id", metadata="foobar")
        response = fxt_job_update_service.job_update(request, fxt_grpc_context)

        # Assert
        mock_is_compose_mode.assert_called_once_with()
        mock_local_executor.return_value.get_execution_metadata.assert_called_once_with("execution_id")
        assert (
            response.HasField("error") and response.error.code == EXECUTION_NOT_FOUND and not response.HasField("empty")
        )

    @patch("scheduler.grpc_api.job_update_service.LocalExecutor")
    @patch("scheduler.grpc_api.job_update_service.is_compose_mode", return_value=True)
    def test_job_update_corrupted_metadata(
        self, mock_is_compose_mode, mock_local_executor, request, fxt_job_update_service, fxt_grpc_context
    ) -> None:
        record = MagicMock()
        record.job_id = "job_id"
        mock_local_executor.return_value.get_execution_metadata.return_value = record

        # Act
        with (
            patch.object(StateMachine, "update_metadata") as mock_update_metadata,
            patch.object(StateMachine, "update_cost_consumed") as mock_update_cost_consumed,
            patch.object(StateMachine, "set_gpu_state_released") as mock_set_gpu_state_released,
        ):
            request = JobUpdateRequest(execution_id="execution_id", metadata="foobar")
            response = fxt_job_update_service.job_update(request, fxt_grpc_context)

        # Assert
        mock_update_metadata.assert_not_called()
        mock_update_cost_consumed.assert_not_called()
        mock_set_gpu_state_released.assert_not_called()
        assert (
            response.HasField("error")
            and response.error.code == INVALID_METADATA_UPDATE
            and not response.HasField("empty")
        )

    @patch("scheduler.grpc_api.job_update_service.LocalExecutor")
    @patch("scheduler.grpc_api.job_update_service.is_compose_mode", return_value=True)
    @pytest.mark.freeze_time("2024-01-01 00:00:01")
    def test_job_update(
        self, mock_is_compose_mode, mock_local_executor, request, fxt_job_update_service, fxt_grpc_context
    ) -> None:
        record = MagicMock()
        record.job_id = "job_id"
        mock_local_executor.return_value.get_execution_metadata.return_value = record

        # Act
        with (
            patch.object(StateMachine, "update_metadata") as mock_update_metadata,
            patch.object(StateMachine, "update_cost_consumed") as mock_update_cost_consumed,
            patch.object(StateMachine, "set_gpu_state_released") as mock_set_gpu_state_released,
        ):
            request = JobUpdateRequest(
                execution_id="execution_id",
                metadata='{"foo": "bar"}',
                cost=JobUpdateRequest.Cost(
                    consumed=[
                        JobUpdateRequest.Cost.Consumed(
                            amount=100,
                            unit="image",
                            consuming_date=int(datetime.datetime.now().timestamp()),
                            service="training",
                        )
                    ]
                ),
                gpu=JobUpdateRequest.Gpu(action=JobUpdateRequest.Gpu.RELEASE),
            )
            response = fxt_job_update_service.job_update(request, fxt_grpc_context)

        # Assert
        mock_update_metadata.assert_called_once_with(job_id=ID("job_id"), metadata={"foo": "bar"})
        mock_update_cost_consumed.assert_called_once_with(
            job_id=ID("job_id"),
            consumed_resources=[
                JobConsumedResource(
                    amount=100, unit="image", consuming_date=datetime.datetime.now(), service="training"
                )
            ],
        )
        mock_set_gpu_state_released.assert_called_once_with(job_id=ID("job_id"))

        assert response.HasField("empty") and not response.HasField("error")

    @patch("scheduler.grpc_api.job_update_service.LocalExecutor")
    @patch("scheduler.grpc_api.job_update_service.is_compose_mode", return_value=True)
    @pytest.mark.freeze_time("2024-01-01 00:00:01")
    def test_job_update_mongo_not_available(
        self, mock_is_compose_mode, mock_local_executor, request, fxt_job_update_service, fxt_grpc_context
    ) -> None:
        record = MagicMock()
        record.job_id = "job_id"
        mock_local_executor.return_value.get_execution_metadata.return_value = record

        # Act
        with patch.object(
            StateMachine, "update_metadata", side_effect=ServerSelectionTimeoutError()
        ) as mock_update_metadata:
            request = JobUpdateRequest(execution_id="execution_id", metadata='{"foo": "bar"}')
            fxt_job_update_service.job_update(request, fxt_grpc_context)

        # Assert
        mock_update_metadata.assert_called_once_with(job_id=ID("job_id"), metadata={"foo": "bar"})
        fxt_grpc_context.abort.assert_called_once_with(
            code=grpc.StatusCode.UNAVAILABLE, details="Database connection has been lost"
        )
