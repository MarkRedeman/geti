# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE
from datetime import datetime
from unittest.mock import ANY, MagicMock, patch

import pytest
from bson import ObjectId
from flytekit.models.core.workflow import NodeMetadata

from model.job import (
    JobCancellationInfo,
    JobConsumedResource,
    JobCost,
    JobResource,
    JobStepDetails,
    JobTaskExecutionBranch,
)
from model.job_state import JobTaskState
from scheduler.flyte import ExecutionType, Flyte
from scheduler.jobs_templates import JobsTemplates, JobTemplateStep
from scheduler.kafka_handler import ProgressHandler
from scheduler.local_executor import LocalExecutor
from scheduler.state_machine import StateMachine

from geti_kafka_tools import KafkaRawMessage
from geti_types import ID, RequestSource
from iai_core.utils.time_utils import now

ORG = ID(ObjectId())


def mock_job_service(self, *args, **kwargs) -> None:
    return None


def mock_flyte_client(self, *args, **kwargs) -> None:
    self.client = MagicMock()
    self.client.client = MagicMock()


def mock_jobs_templates(self, *args, **kwargs) -> None:
    return None


def mock_progress_handler(self, *args, **kwargs) -> None:
    return None


def reset_singletons() -> None:
    Flyte._instance = None  # type: ignore[attr-defined]
    ProgressHandler._instance = None  # type: ignore[attr-defined]
    StateMachine._instance = None  # type: ignore[attr-defined]
    JobsTemplates._instance = None  # type: ignore[attr-defined]
    LocalExecutor._instance = None  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "headers",
    [
        [],
        {},
        (),
        "test",
        ["test"],
        [()],
        [("test")],
        [("ce_type")],
    ],
)
@patch("scheduler.kafka_handler.make_session", return_value=MagicMock())
@patch.object(LocalExecutor, "get_execution_metadata")
@patch.object(LocalExecutor, "__init__", return_value=None)
@patch.object(Flyte, "__init__", new=mock_flyte_client)
@patch.object(StateMachine, "get_by_id")
@patch.object(StateMachine, "__init__", new=mock_job_service)
@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
@patch.object(ProgressHandler, "handle_task_event")
@patch.object(ProgressHandler, "handle_node_event")
@patch.object(ProgressHandler, "handle_workflow_event_by_type")
def test_on_flyte_event_wrong_event_type(
    mock_handle_workflow_event_by_type,
    mock_handle_node_event,
    mock_handle_task_event,
    mock_sm_get_by_id,
    mock_local_executor_init,
    mock_local_executor_get_metadata,
    mock_make_session,
    headers,
    request,
) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    message: KafkaRawMessage = KafkaRawMessage(
        "test_topic",
        0,
        0,
        int(now().timestamp()),
        0,
        "key",
        {"event": {}},
        headers,
    )

    # Act
    ProgressHandler().on_flyte_event(message)

    # Assert
    mock_make_session.assert_not_called()
    mock_local_executor_get_metadata.assert_not_called()
    mock_sm_get_by_id.assert_not_called()
    mock_handle_workflow_event_by_type.assert_not_called()
    mock_handle_node_event.assert_not_called()
    mock_handle_task_event.assert_not_called()


@pytest.mark.parametrize(
    "value",
    [
        [],
        {},
        (),
        "test",
        ["test"],
    ],
)
@patch("scheduler.kafka_handler.make_session", return_value=MagicMock())
@patch.object(LocalExecutor, "get_execution_metadata")
@patch.object(LocalExecutor, "__init__", return_value=None)
@patch.object(Flyte, "__init__", new=mock_flyte_client)
@patch.object(StateMachine, "get_by_id")
@patch.object(StateMachine, "__init__", new=mock_job_service)
@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
@patch.object(ProgressHandler, "handle_task_event")
@patch.object(ProgressHandler, "handle_node_event")
@patch.object(ProgressHandler, "handle_workflow_event_by_type")
def test_on_flyte_event_missing_event(
    mock_handle_workflow_event_by_type,
    mock_handle_node_event,
    mock_handle_task_event,
    mock_sm_get_by_id,
    mock_local_executor_init,
    mock_local_executor_get_metadata,
    mock_make_session,
    value,
    request,
) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    message: KafkaRawMessage = KafkaRawMessage(
        "test_topic",
        0,
        0,
        int(now().timestamp()),
        0,
        "key",
        value,
        [
            (
                "ce_type",
                b"com.flyte.resource.flyteidl.admin.WorkflowExecutionEventRequest",
            )
        ],
    )

    # Act
    ProgressHandler().on_flyte_event(message)

    # Assert
    mock_make_session.assert_not_called()
    mock_local_executor_get_metadata.assert_not_called()
    mock_sm_get_by_id.assert_not_called()
    mock_handle_workflow_event_by_type.assert_not_called()
    mock_handle_node_event.assert_not_called()
    mock_handle_task_event.assert_not_called()


@patch("scheduler.kafka_handler.make_session", return_value=MagicMock())
@patch.object(LocalExecutor, "get_execution_metadata")
@patch.object(LocalExecutor, "__init__", return_value=None)
@patch.object(Flyte, "__init__", new=mock_flyte_client)
@patch.object(StateMachine, "get_by_id")
@patch.object(StateMachine, "__init__", new=mock_job_service)
@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
@patch.object(ProgressHandler, "handle_task_event")
@patch.object(ProgressHandler, "handle_node_event")
@patch.object(ProgressHandler, "handle_workflow_event_by_type")
def test_on_flyte_event_no_execution(
    mock_handle_workflow_event_by_type,
    mock_handle_node_event,
    mock_handle_task_event,
    mock_sm_get_by_id,
    mock_local_executor_init,
    mock_local_executor_get_metadata,
    mock_make_session,
    request,
) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    message: KafkaRawMessage = KafkaRawMessage(
        "test_topic",
        0,
        0,
        int(now().timestamp()),
        0,
        "key",
        {"event": {"executionId": {"name": "ex-workspace-job"}}},
        [
            (
                "ce_type",
                b"com.flyte.resource.flyteidl.admin.WorkflowExecutionEventRequest",
            )
        ],
    )
    mock_local_executor_get_metadata.return_value = None

    # Act
    ProgressHandler().on_flyte_event(message)

    # Assert
    mock_make_session.assert_not_called()
    mock_local_executor_get_metadata.assert_called_once_with("ex-workspace-job")
    mock_sm_get_by_id.assert_not_called()
    mock_handle_workflow_event_by_type.assert_not_called()
    mock_handle_node_event.assert_not_called()
    mock_handle_task_event.assert_not_called()


@patch("scheduler.kafka_handler.make_session", return_value=MagicMock())
@patch.object(LocalExecutor, "get_execution_metadata")
@patch.object(LocalExecutor, "__init__", return_value=None)
@patch.object(Flyte, "__init__", new=mock_flyte_client)
@patch.object(StateMachine, "get_by_id")
@patch.object(StateMachine, "__init__", new=mock_job_service)
@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
@patch.object(ProgressHandler, "handle_task_event")
@patch.object(ProgressHandler, "handle_node_event")
@patch.object(ProgressHandler, "handle_workflow_event_by_type")
def test_on_flyte_event_no_job(
    mock_handle_workflow_event_by_type,
    mock_handle_node_event,
    mock_handle_task_event,
    mock_sm_get_by_id,
    mock_local_executor_init,
    mock_local_executor_get_metadata,
    mock_make_session,
    request,
) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    message: KafkaRawMessage = KafkaRawMessage(
        "test_topic",
        0,
        0,
        int(now().timestamp()),
        0,
        "key",
        {"event": {"executionId": {"name": "ex-workspace-job"}}},
        [
            (
                "ce_type",
                b"com.flyte.resource.flyteidl.admin.WorkflowExecutionEventRequest",
            )
        ],
    )
    record = MagicMock()
    record.organization_id = str(ORG)
    record.workspace_id = "workspace_id"
    record.job_id = "job_id"
    record.execution_type = ExecutionType.MAIN
    mock_local_executor_get_metadata.return_value = record
    mock_sm_get_by_id.return_value = None

    # Act
    ProgressHandler().on_flyte_event(message)

    # Assert
    mock_make_session.assert_called_once_with(
        organization_id=ORG,
        workspace_id=ID("workspace_id"),
        source=RequestSource.INTERNAL,
    )
    mock_local_executor_get_metadata.assert_called_once_with("ex-workspace-job")
    mock_sm_get_by_id.assert_called_once_with(job_id=ID("job_id"))
    mock_handle_workflow_event_by_type.assert_not_called()
    mock_handle_node_event.assert_not_called()
    mock_handle_task_event.assert_not_called()


@patch("scheduler.kafka_handler.make_session", return_value=MagicMock())
@patch.object(LocalExecutor, "get_execution_metadata")
@patch.object(LocalExecutor, "__init__", return_value=None)
@patch.object(Flyte, "__init__", new=mock_flyte_client)
@patch.object(StateMachine, "get_by_id")
@patch.object(StateMachine, "__init__", new=mock_job_service)
@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
@patch.object(ProgressHandler, "handle_task_event")
@patch.object(ProgressHandler, "handle_node_event")
@patch.object(ProgressHandler, "handle_workflow_event_by_type")
def test_on_flyte_workflow_event(
    mock_handle_workflow_event_by_type,
    mock_handle_node_event,
    mock_handle_task_event,
    mock_sm_get_by_id,
    mock_local_executor_init,
    mock_local_executor_get_metadata,
    mock_make_session,
    request,
) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    event = {"executionId": {"name": "ex-workspace-job"}}
    message: KafkaRawMessage = KafkaRawMessage(
        "test_topic",
        0,
        0,
        int(now().timestamp()),
        0,
        "key",
        {"event": event},
        [
            (
                "ce_type",
                b"com.flyte.resource.flyteidl.admin.WorkflowExecutionEventRequest",
            )
        ],
    )
    record = MagicMock()
    record.organization_id = str(ORG)
    record.workspace_id = "workspace_id"
    record.job_id = "job_id"
    record.execution_type = ExecutionType.MAIN
    mock_local_executor_get_metadata.return_value = record

    job = MagicMock()
    mock_sm_get_by_id.return_value = job

    # Act
    ProgressHandler().on_flyte_event(message)

    # Assert
    mock_make_session.assert_called_once_with(
        organization_id=ORG,
        workspace_id=ID("workspace_id"),
        source=RequestSource.INTERNAL,
    )
    mock_local_executor_get_metadata.assert_called_once_with("ex-workspace-job")
    mock_sm_get_by_id.assert_called_once_with(job_id=ID("job_id"))
    mock_handle_workflow_event_by_type.assert_called_once_with(
        event=event,
        execution=None,
        execution_type=ExecutionType.MAIN,
        job=job,
    )
    mock_handle_node_event.assert_not_called()
    mock_handle_task_event.assert_not_called()


@patch("scheduler.kafka_handler.make_session", return_value=MagicMock())
@patch.object(LocalExecutor, "get_execution_metadata")
@patch.object(LocalExecutor, "__init__", return_value=None)
@patch.object(Flyte, "__init__", new=mock_flyte_client)
@patch.object(StateMachine, "get_by_id")
@patch.object(StateMachine, "__init__", new=mock_job_service)
@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
@patch.object(ProgressHandler, "handle_task_event")
@patch.object(ProgressHandler, "handle_node_event")
@patch.object(ProgressHandler, "handle_workflow_event_by_type")
def test_on_flyte_node_event(
    mock_handle_workflow_event_by_type,
    mock_handle_node_event,
    mock_handle_task_event,
    mock_sm_get_by_id,
    mock_local_executor_init,
    mock_local_executor_get_metadata,
    mock_make_session,
    request,
) -> None:
    """NODE_EXECUTION_EVENT_REQUEST returns early – no handlers called."""
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    event = {"id": {"executionId": {"name": "ex-workspace-job"}}}
    message: KafkaRawMessage = KafkaRawMessage(
        "test_topic",
        0,
        0,
        int(now().timestamp()),
        0,
        "key",
        {"event": event},
        [("ce_type", b"com.flyte.resource.flyteidl.admin.NodeExecutionEventRequest")],
    )
    record = MagicMock()
    record.organization_id = str(ORG)
    record.workspace_id = "workspace_id"
    record.job_id = "job_id"
    record.execution_type = ExecutionType.MAIN
    mock_local_executor_get_metadata.return_value = record

    job = MagicMock()
    mock_sm_get_by_id.return_value = job

    # Act
    ProgressHandler().on_flyte_event(message)

    # Assert – node events are not processed in compose mode
    mock_local_executor_get_metadata.assert_called_once_with("ex-workspace-job")
    mock_sm_get_by_id.assert_called_once_with(job_id=ID("job_id"))
    mock_handle_workflow_event_by_type.assert_not_called()
    mock_handle_node_event.assert_not_called()
    mock_handle_task_event.assert_not_called()


@patch("scheduler.kafka_handler.make_session", return_value=MagicMock())
@patch.object(LocalExecutor, "get_execution_metadata")
@patch.object(LocalExecutor, "__init__", return_value=None)
@patch.object(Flyte, "__init__", new=mock_flyte_client)
@patch.object(StateMachine, "get_by_id")
@patch.object(StateMachine, "__init__", new=mock_job_service)
@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
@patch.object(ProgressHandler, "handle_task_event")
@patch.object(ProgressHandler, "handle_node_event")
@patch.object(ProgressHandler, "handle_workflow_event_by_type")
def test_on_flyte_task_event(
    mock_handle_workflow_event_by_type,
    mock_handle_node_event,
    mock_handle_task_event,
    mock_sm_get_by_id,
    mock_local_executor_init,
    mock_local_executor_get_metadata,
    mock_make_session,
    request,
) -> None:
    """TASK_EXECUTION_EVENT_REQUEST returns early – no handlers called."""
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    event = {"parentNodeExecutionId": {"executionId": {"name": "ex-workspace-job"}}}
    message: KafkaRawMessage = KafkaRawMessage(
        "test_topic",
        0,
        0,
        int(now().timestamp()),
        0,
        "key",
        {"event": event},
        [("ce_type", b"com.flyte.resource.flyteidl.admin.TaskExecutionEventRequest")],
    )
    record = MagicMock()
    record.organization_id = str(ORG)
    record.workspace_id = "workspace_id"
    record.job_id = "job_id"
    record.execution_type = ExecutionType.MAIN
    mock_local_executor_get_metadata.return_value = record

    job = MagicMock()
    mock_sm_get_by_id.return_value = job

    # Act
    ProgressHandler().on_flyte_event(message)

    # Assert – task events are not processed in compose mode
    mock_local_executor_get_metadata.assert_called_once_with("ex-workspace-job")
    mock_sm_get_by_id.assert_called_once_with(job_id=ID("job_id"))
    mock_handle_workflow_event_by_type.assert_not_called()
    mock_handle_node_event.assert_not_called()
    mock_handle_task_event.assert_not_called()


@pytest.mark.parametrize(
    "event",
    [
        {},
        {"executionId": {}},
    ],
)
@patch.object(Flyte, "__init__", new=mock_flyte_client)
@patch.object(ProgressHandler, "handle_revert_workflow_event")
@patch.object(ProgressHandler, "handle_main_workflow_event")
@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
def test_handle_workflow_event_by_type_wrong_event(
    mock_ph_handle_main_workflow_event,
    mock_ph_handle_revert_workflow_event,
    event,
    request,
) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    job = MagicMock()

    # Act
    ProgressHandler().handle_workflow_event_by_type(
        event=event, execution=None, execution_type=ExecutionType.MAIN, job=job
    )

    # Assert
    mock_ph_handle_main_workflow_event.assert_not_called()
    mock_ph_handle_revert_workflow_event.assert_not_called()


@patch.object(Flyte, "__init__", new=mock_flyte_client)
@patch.object(ProgressHandler, "handle_revert_workflow_event")
@patch.object(ProgressHandler, "handle_main_workflow_event")
@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
def test_handle_workflow_event_by_type_no_phase(
    mock_ph_handle_main_workflow_event,
    mock_ph_handle_revert_workflow_event,
    request,
) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    job = MagicMock()

    # Act
    ProgressHandler().handle_workflow_event_by_type(
        event={"executionId": {"name": "ex-workspace-job"}},
        execution=None,
        execution_type=ExecutionType.MAIN,
        job=job,
    )

    # Assert
    mock_ph_handle_main_workflow_event.assert_not_called()
    mock_ph_handle_revert_workflow_event.assert_not_called()


@pytest.mark.parametrize("phase", ["SUCCEEDED", "RUNNING", "FAILED", "ABORTED"])
@patch.object(StateMachine, "__init__", new=mock_job_service)
@patch.object(Flyte, "__init__", new=mock_flyte_client)
@patch.object(ProgressHandler, "handle_revert_workflow_event")
@patch.object(ProgressHandler, "handle_main_workflow_event")
@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
def test_handle_workflow_event_by_type_main_execution(
    mock_ph_handle_main_workflow_event,
    mock_ph_handle_revert_workflow_event,
    request,
    phase,
) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    job = MagicMock()

    # Act
    ProgressHandler().handle_workflow_event_by_type(
        event={"executionId": {"name": "ex-workspace-job"}, "phase": phase},
        execution=None,
        execution_type=ExecutionType.MAIN,
        job=job,
    )

    # Assert
    mock_ph_handle_main_workflow_event.assert_called_once_with(job=job, phase=phase)
    mock_ph_handle_revert_workflow_event.assert_not_called()


@pytest.mark.parametrize("phase", ["SUCCEEDED", "RUNNING", "FAILED", "ABORTED"])
@patch.object(Flyte, "__init__", new=mock_flyte_client)
@patch.object(ProgressHandler, "handle_revert_workflow_event")
@patch.object(ProgressHandler, "handle_main_workflow_event")
@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
def test_handle_workflow_event_by_type_revert_execution(
    mock_ph_handle_main_workflow_event,
    mock_ph_handle_revert_workflow_event,
    request,
    phase,
) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    job = MagicMock()

    # Act
    ProgressHandler().handle_workflow_event_by_type(
        event={"executionId": {"name": "ex-workspace-job"}, "phase": phase},
        execution=None,
        execution_type=ExecutionType.REVERT,
        job=job,
    )

    # Assert
    mock_ph_handle_main_workflow_event.assert_not_called()
    mock_ph_handle_revert_workflow_event.assert_called_once_with(job=job, phase=phase)


@patch.object(Flyte, "__init__", new=mock_flyte_client)
@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
@patch.object(StateMachine, "set_and_publish_cancelled_state")
@patch.object(StateMachine, "set_and_publish_finished_state")
@patch.object(StateMachine, "set_ready_for_revert_state")
@patch.object(StateMachine, "set_running_state")
def test_handle_main_workflow_event_running(
    mock_set_running_state,
    mock_set_ready_for_revert_state,
    mock_set_and_publish_finished_state,
    mock_set_and_publish_cancelled_state,
    request,
) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    job = MagicMock()
    job.id = ID("job")

    # Act
    ProgressHandler().handle_main_workflow_event(job=job, phase="RUNNING")

    # Assert
    mock_set_running_state.assert_called_once_with(job_id=ID("job"))
    mock_set_ready_for_revert_state.assert_not_called()
    mock_set_and_publish_finished_state.assert_not_called()
    mock_set_and_publish_cancelled_state.assert_not_called()


@patch.object(Flyte, "__init__", new=mock_flyte_client)
@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
@patch.object(StateMachine, "set_and_publish_cancelled_state")
@patch.object(StateMachine, "set_and_publish_finished_state")
@patch.object(StateMachine, "set_ready_for_revert_state")
@patch.object(StateMachine, "set_running_state")
def test_handle_main_workflow_event_finished(
    mock_set_running_state,
    mock_set_ready_for_revert_state,
    mock_set_and_publish_finished_state,
    mock_set_and_publish_cancelled_state,
    request,
) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    job = MagicMock()
    job.id = ID("job")

    # Act
    ProgressHandler().handle_main_workflow_event(job=job, phase="SUCCEEDED")

    # Assert
    mock_set_running_state.assert_not_called()
    mock_set_ready_for_revert_state.assert_not_called()
    mock_set_and_publish_finished_state.assert_called_once_with(job_id=ID("job"))
    mock_set_and_publish_cancelled_state.assert_not_called()


@patch.object(Flyte, "__init__", new=mock_flyte_client)
@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
@patch.object(StateMachine, "set_and_publish_cancelled_state")
@patch.object(StateMachine, "set_and_publish_finished_state")
@patch.object(StateMachine, "set_ready_for_revert_state")
@patch.object(StateMachine, "set_running_state")
def test_handle_main_workflow_event_failed(
    mock_set_running_state,
    mock_set_ready_for_revert_state,
    mock_set_and_publish_finished_state,
    request,
) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    job = MagicMock()
    job.id = ID("job")

    # Act
    ProgressHandler().handle_main_workflow_event(job=job, phase="FAILED")

    # Assert
    mock_set_running_state.assert_not_called()
    mock_set_ready_for_revert_state.assert_called_once_with(job_id=ID("job"))
    mock_set_and_publish_finished_state.assert_not_called()


@patch.object(Flyte, "__init__", new=mock_flyte_client)
@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
@patch.object(StateMachine, "set_and_publish_finished_state")
@patch.object(StateMachine, "set_ready_for_revert_state")
@patch.object(StateMachine, "set_running_state")
def test_handle_main_workflow_event_aborted(
    mock_set_running_state,
    mock_set_ready_for_revert_state,
    mock_set_and_publish_finished_state,
    request,
) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    job = MagicMock()
    job.id = ID("job")

    # Act
    ProgressHandler().handle_main_workflow_event(job=job, phase="ABORTED")

    # Assert
    mock_set_running_state.assert_not_called()
    mock_set_ready_for_revert_state.assert_called_once_with(job_id=ID("job"))
    mock_set_and_publish_finished_state.assert_not_called()


@patch.object(Flyte, "__init__", new=mock_flyte_client)
@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
@patch.object(StateMachine, "set_and_publish_failed_state")
@patch.object(StateMachine, "set_and_publish_cancelled_state")
@patch.object(StateMachine, "set_revert_running_state")
def test_handle_revert_workflow_event_running(
    mock_set_revert_running_state,
    mock_set_and_publish_cancelled_state,
    mock_set_and_publish_failed_state,
    request,
) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    job = MagicMock()
    job.id = ID("job")

    # Act
    ProgressHandler().handle_revert_workflow_event(job=job, phase="RUNNING")

    # Assert
    mock_set_revert_running_state.assert_called_once_with(job_id=ID("job"))
    mock_set_and_publish_cancelled_state.assert_not_called()
    mock_set_and_publish_failed_state.assert_not_called()


@pytest.mark.parametrize("phase", ["SUCCEEDED", "FAILED"])
@patch.object(Flyte, "__init__", new=mock_flyte_client)
@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
@patch.object(StateMachine, "set_and_publish_failed_state")
@patch.object(StateMachine, "set_and_publish_cancelled_state")
@patch.object(StateMachine, "set_revert_running_state")
def test_handle_revert_workflow_event_cancelled(
    mock_set_revert_running_state,
    mock_set_and_publish_cancelled_state,
    mock_set_and_publish_failed_state,
    request,
    phase,
) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    job = MagicMock()
    job.id = ID("job")
    job.cancellation_info.is_cancelled = True
    job.cancellation_info.delete_job = False

    # Act
    ProgressHandler().handle_revert_workflow_event(job=job, phase=phase)

    # Assert
    mock_set_revert_running_state.assert_not_called()
    mock_set_and_publish_cancelled_state.assert_called_once_with(job_id=ID("job"))
    mock_set_and_publish_failed_state.assert_not_called()


@pytest.mark.parametrize("phase", ["SUCCEEDED", "FAILED"])
@patch.object(Flyte, "__init__", new=mock_flyte_client)
@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
@patch.object(StateMachine, "set_and_publish_failed_state")
@patch.object(StateMachine, "set_and_publish_cancelled_state")
@patch.object(StateMachine, "set_revert_running_state")
def test_handle_revert_workflow_event_failed(
    mock_set_revert_running_state,
    mock_set_and_publish_cancelled_state,
    mock_set_and_publish_failed_state,
    request,
    phase,
) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    job = MagicMock()
    job.id = ID("job")
    job.cancellation_info.is_cancelled = False

    # Act
    ProgressHandler().handle_revert_workflow_event(job=job, phase=phase)

    # Assert
    mock_set_revert_running_state.assert_not_called()
    mock_set_and_publish_cancelled_state.assert_not_called()
    mock_set_and_publish_failed_state.assert_called_once_with(job_id=ID("job"))


@pytest.mark.parametrize(
    "event",
    [
        {},
        {"parentNodeExecutionId": {}},
        {"parentNodeExecutionId": {"executionId": {}}},
        {"parentNodeExecutionId": {"executionId": {"name": "ex-workspace-job"}}},
        {"parentNodeExecutionId": {"executionId": {}, "nodeId": "n0"}},
    ],
)
@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
@patch.object(StateMachine, "set_step_details")
@patch.object(StateMachine, "__init__", new=mock_job_service)
@patch.object(Flyte, "__init__", new=mock_flyte_client)
def test_handle_task_event_wrong_event(mock_sm_set_step_details, event, request) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    execution = MagicMock()
    job = MagicMock()

    # Act
    ProgressHandler().handle_task_event(event=event, execution=execution, job=job)

    # Assert
    mock_sm_set_step_details.assert_not_called()


@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
@patch.object(StateMachine, "set_step_details")
@patch.object(StateMachine, "__init__", new=mock_job_service)
@patch.object(Flyte, "__init__", new=mock_flyte_client)
def test_handle_task_event_missing_phase(mock_sm_set_step_details, request) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    execution = MagicMock()
    job = MagicMock()

    # Act
    ProgressHandler().handle_task_event(
        event={
            "parentNodeExecutionId": {
                "executionId": {"name": "ex-workspace-job"},
                "nodeId": "n0",
            }
        },
        execution=execution,
        job=job,
    )

    # Assert
    mock_sm_set_step_details.assert_not_called()


@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
@patch.object(StateMachine, "set_step_details")
@patch.object(StateMachine, "__init__", new=mock_job_service)
@patch.object(Flyte, "__init__", new=mock_flyte_client)
def test_handle_task_event_revert(mock_sm_set_step_details, request) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    execution = MagicMock()
    execution.spec.annotations.values = {
        "execution_type": "REVERT",
    }
    job = MagicMock()

    # Act
    ProgressHandler().handle_task_event(
        event={
            "parentNodeExecutionId": {"executionId": {"name": "ex-workspace-job"}},
            "taskId": {"name": "task_id"},
            "phase": "RUNNING",
        },
        execution=execution,
        job=job,
    )

    # Assert
    mock_sm_set_step_details.assert_not_called()


@pytest.mark.parametrize(
    "phase, state, error, message",
    [
        ("RUNNING", JobTaskState.RUNNING, None, None),
        ("SUCCEEDED", JobTaskState.FINISHED, None, None),
        ("FAILED", JobTaskState.FAILED, None, None),
        (
            "FAILED",
            JobTaskState.FAILED,
            {"code": "OOMKilled"},
            "The job failed due to insufficient memory. "
            "This may happen if the chosen model is too large for the available hardware, "
            "or if there is an internal bug in the training pipeline. Please try again with a more "
            "lightweight model if possible: if the problem persists, please report the issue.",
        ),
        (
            "FAILED",
            JobTaskState.FAILED,
            {"message": "Pod has been OOM-killed"},
            "The job failed due to insufficient memory. "
            "This may happen if the chosen model is too large for the available hardware, "
            "or if there is an internal bug in the training pipeline. Please try again with a more "
            "lightweight model if possible: if the problem persists, please report the issue.",
        ),
    ],
)
@patch("scheduler.kafka_handler.now", return_value=datetime(2020, 1, 1))
@patch("scheduler.kafka_handler.make_session", return_value=MagicMock())
@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
@patch.object(StateMachine, "set_step_details")
@patch.object(StateMachine, "__init__", new=mock_job_service)
@patch.object(JobsTemplates, "get_job_steps")
@patch.object(JobsTemplates, "__init__", new=mock_jobs_templates)
@patch.object(Flyte, "__init__", new=mock_flyte_client)
def test_handle_task_event_main(
    mock_jt_get_job_steps,
    mock_sm_set_step_details,
    mock_make_session,
    mock_now,
    request,
    phase,
    state,
    error,
    message,
) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    execution = MagicMock()
    execution.spec.annotations.values = {
        "organization_id": str(ORG),
        "workspace_id": "workspace_id",
        "job_id": "job_id",
        "execution_type": "MAIN",
    }
    job = MagicMock()
    job.workspace_id = ID("workspace_id")
    job.id = ID("job_id")

    mock_jt_get_job_steps.return_value = [JobTemplateStep(name="Test task", task_id="task_id")]

    # Act
    event = {
        "parentNodeExecutionId": {"executionId": {"name": "ex-workspace-job"}},
        "taskId": {"name": "task_id"},
        "phase": phase,
    }
    if error is not None:
        event["error"] = error
    ProgressHandler().handle_task_event(event=event, execution=execution, job=job)

    # Assert

    mock_sm_set_step_details.assert_called_once_with(
        job_id=ID("job_id"),
        task_id="task_id",
        state=state,
        start_time=datetime(2020, 1, 1) if state == JobTaskState.RUNNING else None,
        end_time=datetime(2020, 1, 1) if state != JobTaskState.RUNNING else None,
        message=message,
        progress=100.0 if state == JobTaskState.FINISHED else None,
    )


@pytest.mark.parametrize(
    "phase, state, error, message",
    [
        ("RUNNING", JobTaskState.RUNNING, None, "Start message"),
        ("SUCCEEDED", JobTaskState.FINISHED, None, "Finish message"),
        ("FAILED", JobTaskState.FAILED, None, "Failure message"),
    ],
)
@patch("scheduler.kafka_handler.now", return_value=datetime(2020, 1, 1))
@patch("scheduler.kafka_handler.make_session", return_value=MagicMock())
@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
@patch.object(StateMachine, "set_step_details")
@patch.object(StateMachine, "__init__", new=mock_job_service)
@patch.object(JobsTemplates, "get_job_steps")
@patch.object(JobsTemplates, "__init__", new=mock_jobs_templates)
@patch.object(Flyte, "__init__", new=mock_flyte_client)
def test_handle_task_event_main_message_from_template(
    mock_jt_get_job_steps,
    mock_sm_set_step_details,
    mock_make_session,
    mock_now,
    request,
    phase,
    state,
    error,
    message,
) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    execution = MagicMock()
    execution.spec.annotations.values = {
        "organization_id": str(ORG),
        "workspace_id": "workspace_id",
        "job_id": "job_id",
        "execution_type": "MAIN",
    }
    job = MagicMock()
    job.workspace_id = ID("workspace_id")
    job.id = ID("job_id")

    mock_jt_get_job_steps.return_value = [
        JobTemplateStep(
            name="Test task",
            task_id="task_id",
            start_message="Start message",
            finish_message="Finish message",
            failure_message="Failure message",
        )
    ]

    # Act
    event = {
        "parentNodeExecutionId": {"executionId": {"name": "ex-workspace-job"}},
        "taskId": {"name": "task_id"},
        "phase": phase,
    }
    if error is not None:
        event["error"] = error
    ProgressHandler().handle_task_event(event=event, execution=execution, job=job)

    # Assert

    mock_sm_set_step_details.assert_called_once_with(
        job_id=ID("job_id"),
        task_id="task_id",
        state=state,
        start_time=datetime(2020, 1, 1) if state == JobTaskState.RUNNING else None,
        end_time=datetime(2020, 1, 1) if state != JobTaskState.RUNNING else None,
        message=f"{message} (ID: {job.id})" if state == JobTaskState.FAILED else message,
        progress=100.0 if state == JobTaskState.FINISHED else None,
    )


@patch("scheduler.kafka_handler.now", return_value=datetime(2020, 1, 1))
@patch("scheduler.kafka_handler.make_session", return_value=MagicMock())
@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
@patch.object(StateMachine, "set_step_details")
@patch.object(StateMachine, "__init__", new=mock_job_service)
@patch.object(JobsTemplates, "get_job_steps")
@patch.object(JobsTemplates, "__init__", new=mock_jobs_templates)
@patch.object(Flyte, "__init__", new=mock_flyte_client)
def test_handle_task_event_main_task_not_initiated(
    mock_jt_get_job_steps,
    mock_sm_set_step_details,
    mock_make_session,
    mock_now,
    request,
) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    execution = MagicMock()
    execution.spec.annotations.values = {
        "organization_id": str(ORG),
        "workspace_id": "workspace_id",
        "job_id": "job_id",
        "execution_type": "MAIN",
    }
    job = MagicMock()
    job.workspace_id = ID("workspace_id")
    job.id = ID("job_id")
    job.step_details = (
        JobStepDetails(
            index=0,
            task_id="task_id",
            step_name="Test step",
            state=JobTaskState.WAITING,
        ),
    )

    mock_jt_get_job_steps.return_value = [JobTemplateStep(name="Test task", task_id="task_id")]

    # Act
    event = {
        "parentNodeExecutionId": {"executionId": {"name": "ex-workspace-job"}},
        "taskId": {"name": "task_id"},
        "phase": "FAILED",
    }
    ProgressHandler().handle_task_event(event=event, execution=execution, job=job)

    # Assert

    mock_sm_set_step_details.assert_called_once_with(
        job_id=ID("job_id"),
        task_id="task_id",
        state=JobTaskState.FAILED,
        start_time=None,
        end_time=datetime(2020, 1, 1),
        message=(
            "An issue was encountered while initializing this workload. Please retry or reach out to "
            "us on GitHub if problem persists."
        ),
        progress=None,
    )


@pytest.mark.parametrize(
    "event",
    [
        {},
        {"phase": "SUCCEEDED"},
        {"phase": "RUNNING"},
        {"phase": "FAILED"},
        {"phase": "ABORTED"},
        {"phase": "QUEUED", "id": {}},
        {"phase": "QUEUED", "id": {"executionId": {}}},
    ],
)
@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
@patch.object(StateMachine, "set_step_details")
@patch.object(StateMachine, "__init__", new=mock_job_service)
@patch.object(JobsTemplates, "get_job_steps")
@patch.object(Flyte, "get_workflow_branch_nodes")
@patch.object(Flyte, "__init__", new=mock_flyte_client)
def test_handle_node_event_wrong_event(
    mock_flyte_get_workflow_branch_nodes,
    mock_get_job_steps,
    mock_sm_set_step_details,
    request,
    event,
) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    execution = MagicMock()
    job = MagicMock()

    # Act
    ProgressHandler().handle_node_event(event=event, execution=execution, job=job)

    # Assert
    mock_flyte_get_workflow_branch_nodes.assert_not_called()
    mock_get_job_steps.assert_not_called()
    mock_sm_set_step_details.assert_not_called()


@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
@patch.object(StateMachine, "set_step_details")
@patch.object(StateMachine, "__init__", new=mock_job_service)
@patch.object(JobsTemplates, "get_job_steps")
@patch.object(Flyte, "get_workflow_branch_nodes")
@patch.object(Flyte, "fetch_workflow_execution")
@patch.object(Flyte, "__init__", new=mock_flyte_client)
def test_handle_node_event_revert(
    mock_flyte_get_workflow_branch_nodes,
    mock_get_job_steps,
    mock_sm_set_step_details,
    request,
) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    execution = MagicMock()
    execution.spec.annotations.values = {
        "organization_id": str(ORG),
        "workspace_id": "workspace_id",
        "job_id": "job_id",
        "execution_type": "REVERT",
    }
    job = MagicMock()

    # Act
    ProgressHandler().handle_node_event(
        event={
            "id": {
                "executionId": {"name": "ex-workspace-job"},
            },
            "phase": "QUEUED",
            "nodeName": "n0-n0",
        },
        execution=execution,
        job=job,
    )

    # Assert
    mock_flyte_get_workflow_branch_nodes.assert_not_called()
    mock_get_job_steps.assert_not_called()
    mock_sm_set_step_details.assert_not_called()


@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
@patch.object(StateMachine, "set_step_details")
@patch.object(StateMachine, "__init__", new=mock_job_service)
@patch.object(JobsTemplates, "get_job_steps")
@patch.object(JobsTemplates, "__init__", new=mock_jobs_templates)
@patch.object(Flyte, "get_workflow_branch_nodes")
@patch.object(Flyte, "__init__", new=mock_flyte_client)
def test_handle_node_event_main_set_step_details(
    mock_flyte_get_workflow_branch_nodes,
    mock_get_job_steps,
    mock_sm_set_step_details,
    request,
) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    execution = MagicMock()
    execution.spec.annotations.values = {
        "organization_id": str(ORG),
        "workspace_id": "workspace_id",
        "job_id": "job_id",
        "execution_type": "MAIN",
    }
    job = MagicMock()
    job.workspace_id = ID("workspace_id")
    job.id = ID("job_id")
    job.type = "test_job"
    job.step_details = [
        JobStepDetails(
            index=1,
            task_id="test_task",
            step_name="Test task",
            state=JobTaskState.WAITING,
            branches=(JobTaskExecutionBranch(condition="condition", branch="branch1"),),
        )
    ]

    workflow = MagicMock()
    execution.flyte_workflow = workflow
    branch_node = MagicMock()
    branch_node.metadata = NodeMetadata(name="condition")
    mock_flyte_get_workflow_branch_nodes.return_value = {"branch2": branch_node}

    mock_get_job_steps.return_value = [
        JobTemplateStep(
            name="Test task",
            task_id="test_task",
            branches=[
                {
                    "condition": "condition",
                    "branch": "branch1",
                    "skip_message": "Skipped",
                }
            ],
        )
    ]

    # Act
    ProgressHandler().handle_node_event(
        event={
            "id": {
                "executionId": {"name": "ex-workspace-job"},
            },
            "phase": "QUEUED",
            "nodeName": "branch2",
        },
        execution=execution,
        job=job,
    )

    # Assert
    mock_flyte_get_workflow_branch_nodes.assert_called_once_with(workflow=workflow)
    mock_get_job_steps.assert_called_once_with(job_type="test_job")
    mock_sm_set_step_details.assert_called_once_with(
        job_id=ID("job_id"),
        task_id="test_task",
        state=JobTaskState.SKIPPED,
        message="Skipped",
    )


@patch.object(LocalExecutor, "get_execution_metadata")
@patch.object(LocalExecutor, "__init__", return_value=None)
@patch.object(Flyte, "__init__", new=mock_flyte_client)
@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
@patch.object(StateMachine, "set_step_details")
def test_on_job_step_details_missing_execution_id(
    mock_sm_set_step_details,
    mock_local_executor_init,
    mock_local_executor_get_metadata,
    request,
) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    message: KafkaRawMessage = KafkaRawMessage(
        "test_topic",
        0,
        0,
        int(now().timestamp()),
        0,
        "key",
        {},
        [
            ("organization_id", b"000000000000000000000001"),
            ("workspace_id", b"63b183d00000000000000001"),
        ],
    )

    # Act
    ProgressHandler().on_job_step_details(message)

    # Assert
    mock_local_executor_get_metadata.assert_not_called()
    mock_sm_set_step_details.assert_not_called()


@patch.object(LocalExecutor, "get_execution_metadata")
@patch.object(LocalExecutor, "__init__", return_value=None)
@patch.object(Flyte, "__init__", new=mock_flyte_client)
@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
@patch.object(StateMachine, "set_step_details")
def test_on_job_step_details_missing_execution(
    mock_sm_set_step_details,
    mock_local_executor_init,
    mock_local_executor_get_metadata,
    request,
) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    message: KafkaRawMessage = KafkaRawMessage(
        "test_topic",
        0,
        0,
        int(now().timestamp()),
        0,
        "key",
        {"execution_id": "execution"},
        [
            ("organization_id", b"000000000000000000000001"),
            ("workspace_id", b"63b183d00000000000000001"),
        ],
    )

    mock_local_executor_get_metadata.return_value = None

    # Act
    ProgressHandler().on_job_step_details(message)

    # Assert
    mock_local_executor_get_metadata.assert_called_once_with("execution")
    mock_sm_set_step_details.assert_not_called()


@patch.object(LocalExecutor, "get_execution_metadata")
@patch.object(LocalExecutor, "__init__", return_value=None)
@patch.object(Flyte, "__init__", new=mock_flyte_client)
@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
@patch.object(StateMachine, "set_step_details")
@patch.object(StateMachine, "get_by_id")
def test_on_job_step_details(
    mock_sm_get_by_id,
    mock_sm_set_step_details,
    mock_local_executor_init,
    mock_local_executor_get_metadata,
    request,
) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    message: KafkaRawMessage = KafkaRawMessage(
        "test_topic",
        0,
        0,
        int(now().timestamp()),
        0,
        "key",
        {
            "execution_id": "execution",
            "task_id": "task_id",
            "progress": 45,
            "message": "Custom message",
        },
        [
            ("organization_id", b"000000000000000000000001"),
            ("workspace_id", b"63b183d00000000000000001"),
        ],
    )

    record = MagicMock()
    record.job_id = "job_id"
    mock_local_executor_get_metadata.return_value = record

    job = MagicMock()
    job.cancellation_info = JobCancellationInfo(is_cancelled=False)
    mock_sm_get_by_id.return_value = job

    # Act
    ProgressHandler().on_job_step_details(message)

    # Assert
    mock_local_executor_get_metadata.assert_called_once_with("execution")
    mock_sm_set_step_details.assert_called_once_with(
        job_id=ID("job_id"),
        state=None,
        task_id="task_id",
        progress=45,
        message="Custom message",
        warning=None,
    )


@patch.object(LocalExecutor, "get_execution_metadata")
@patch.object(LocalExecutor, "__init__", return_value=None)
@patch.object(Flyte, "__init__", new=mock_flyte_client)
@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
@patch.object(StateMachine, "set_step_details")
@patch.object(StateMachine, "get_by_id")
def test_on_job_step_details_cancelled(
    mock_sm_get_by_id,
    mock_sm_set_step_details,
    mock_local_executor_init,
    mock_local_executor_get_metadata,
    request,
) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    message: KafkaRawMessage = KafkaRawMessage(
        "test_topic",
        0,
        0,
        int(now().timestamp()),
        0,
        "key",
        {
            "execution_id": "execution",
            "task_id": "task_id",
            "progress": 45,
            "message": "Custom message",
        },
        [
            ("organization_id", b"000000000000000000000001"),
            ("workspace_id", b"63b183d00000000000000001"),
        ],
    )

    record = MagicMock()
    record.job_id = "job_id"
    mock_local_executor_get_metadata.return_value = record

    job = MagicMock()
    job.cancellation_info = JobCancellationInfo(is_cancelled=True)
    mock_sm_get_by_id.return_value = job

    # Act
    ProgressHandler().on_job_step_details(message)

    # Assert
    mock_local_executor_get_metadata.assert_called_once_with("execution")
    mock_sm_set_step_details.assert_not_called()


@patch.object(LocalExecutor, "get_execution_metadata")
@patch.object(LocalExecutor, "__init__", return_value=None)
@patch.object(Flyte, "__init__", new=mock_flyte_client)
@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
@patch.object(StateMachine, "update_metadata")
def test_on_job_update_missing_execution_id(
    mock_sm_update_metadata,
    mock_local_executor_init,
    mock_local_executor_get_metadata,
    request,
) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    message: KafkaRawMessage = KafkaRawMessage(
        "test_topic",
        0,
        0,
        int(now().timestamp()),
        0,
        "key",
        {},
        [
            ("organization_id", b"000000000000000000000001"),
            ("workspace_id", b"63b183d00000000000000001"),
        ],
    )

    # Act
    ProgressHandler().on_job_update(message)

    # Assert
    mock_local_executor_get_metadata.assert_not_called()
    mock_sm_update_metadata.assert_not_called()


@patch.object(LocalExecutor, "get_execution_metadata")
@patch.object(LocalExecutor, "__init__", return_value=None)
@patch.object(Flyte, "__init__", new=mock_flyte_client)
@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
@patch.object(StateMachine, "update_metadata")
def test_on_job_update_missing_execution(
    mock_sm_update_metadata,
    mock_local_executor_init,
    mock_local_executor_get_metadata,
    request,
) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    message: KafkaRawMessage = KafkaRawMessage(
        "test_topic",
        0,
        0,
        int(now().timestamp()),
        0,
        "key",
        {"execution_id": "execution"},
        [
            ("organization_id", b"000000000000000000000001"),
            ("workspace_id", b"63b183d00000000000000001"),
        ],
    )

    mock_local_executor_get_metadata.return_value = None

    # Act
    ProgressHandler().on_job_update(message)

    # Assert
    mock_local_executor_get_metadata.assert_called_once_with("execution")
    mock_sm_update_metadata.assert_not_called()


@patch.object(LocalExecutor, "get_execution_metadata")
@patch.object(LocalExecutor, "__init__", return_value=None)
@patch.object(Flyte, "__init__", new=mock_flyte_client)
@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
@patch.object(StateMachine, "update_metadata")
def test_on_job_update_metadata(
    mock_sm_update_metadata,
    mock_local_executor_init,
    mock_local_executor_get_metadata,
    request,
) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    message: KafkaRawMessage = KafkaRawMessage(
        "test_topic",
        0,
        0,
        int(now().timestamp()),
        0,
        "key",
        {"execution_id": "execution", "metadata": {"key": "value"}},
        [
            ("organization_id", b"000000000000000000000001"),
            ("workspace_id", b"63b183d00000000000000001"),
        ],
    )

    record = MagicMock()
    record.job_id = "job_id"
    mock_local_executor_get_metadata.return_value = record

    # Act
    ProgressHandler().on_job_update(message)

    # Assert
    mock_local_executor_get_metadata.assert_called_once_with("execution")
    mock_sm_update_metadata.assert_called_once_with(
        job_id=ID("job_id"),
        metadata={"key": "value"},
    )


@patch.object(LocalExecutor, "get_execution_metadata")
@patch.object(LocalExecutor, "__init__", return_value=None)
@patch.object(Flyte, "__init__", new=mock_flyte_client)
@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
@patch.object(StateMachine, "update_cost_consumed")
def test_on_job_update_consumed_cost(
    mock_sm_update_cost_consumed,
    mock_local_executor_init,
    mock_local_executor_get_metadata,
    request,
) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    message: KafkaRawMessage = KafkaRawMessage(
        "test_topic",
        0,
        0,
        int(now().timestamp()),
        0,
        "key",
        {
            "execution_id": "execution",
            "cost": {
                "consumed": [
                    {
                        "amount": 100,
                        "unit": "images",
                        "consuming_date": "2024-01-01T00:00:01",
                        "service": "training",
                    }
                ]
            },
        },
        [
            ("organization_id", b"000000000000000000000001"),
            ("workspace_id", b"63b183d00000000000000001"),
        ],
    )

    record = MagicMock()
    record.job_id = "job_id"
    mock_local_executor_get_metadata.return_value = record

    # Act
    ProgressHandler().on_job_update(message)

    # Assert
    mock_local_executor_get_metadata.assert_called_once_with("execution")
    mock_sm_update_cost_consumed.assert_called_once_with(
        job_id=ID("job_id"),
        consumed_resources=[
            JobConsumedResource(
                amount=100,
                unit="images",
                consuming_date=datetime(2024, 1, 1, 0, 0, 1),
                service="training",
            )
        ],
    )


@patch.object(LocalExecutor, "get_execution_metadata")
@patch.object(LocalExecutor, "__init__", return_value=None)
@patch.object(Flyte, "__init__", new=mock_flyte_client)
@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
@patch.object(StateMachine, "set_gpu_state_released")
def test_on_job_update_release_gpu(
    mock_sm_set_gpu_state_released,
    mock_local_executor_init,
    mock_local_executor_get_metadata,
    request,
) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    message: KafkaRawMessage = KafkaRawMessage(
        "test_topic",
        0,
        0,
        int(now().timestamp()),
        0,
        "key",
        {"execution_id": "execution", "gpu": "release"},
        [
            ("organization_id", b"000000000000000000000001"),
            ("workspace_id", b"63b183d00000000000000001"),
        ],
    )

    record = MagicMock()
    record.job_id = "job_id"
    mock_local_executor_get_metadata.return_value = record

    # Act
    ProgressHandler().on_job_update(message)

    # Assert
    mock_local_executor_get_metadata.assert_called_once_with("execution")
    mock_sm_set_gpu_state_released.assert_called_once_with(job_id=ID("job_id"))


@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
@patch.object(StateMachine, "mark_cancelled_and_deleted")
@patch.object(StateMachine, "find_jobs_ids_by_project_id")
def test_on_project_deleted_not_found(
    mock_sm_find_jobs_ids_by_project_id, mock_sm_mark_cancelled_and_deleted, request
) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    message: KafkaRawMessage = KafkaRawMessage(
        "test_topic",
        0,
        0,
        int(now().timestamp()),
        0,
        "key",
        {"project_id": "project_id"},
        [
            ("organization_id", b"000000000000000000000001"),
            ("workspace_id", b"63b183d00000000000000001"),
        ],
    )
    mock_sm_find_jobs_ids_by_project_id.return_value = ()

    # Act
    ProgressHandler().on_project_deleted(message)

    # Assert
    mock_sm_find_jobs_ids_by_project_id.assert_called_once_with(project_id="project_id")
    mock_sm_mark_cancelled_and_deleted.assert_not_called()


@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
@patch.object(StateMachine, "mark_cancelled_and_deleted")
@patch.object(StateMachine, "find_jobs_ids_by_project_id")
def test_on_project_deleted_found(
    mock_sm_find_jobs_ids_by_project_id, mock_sm_mark_cancelled_and_deleted, request
) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    message: KafkaRawMessage = KafkaRawMessage(
        "test_topic",
        0,
        0,
        int(now().timestamp()),
        0,
        "key",
        {"project_id": "project_id"},
        [
            ("organization_id", b"000000000000000000000001"),
            ("workspace_id", b"63b183d00000000000000001"),
        ],
    )
    job_id = ID("job_id")
    mock_sm_find_jobs_ids_by_project_id.return_value = (job_id,)

    # Act
    ProgressHandler().on_project_deleted(message)

    # Assert
    mock_sm_find_jobs_ids_by_project_id.assert_called_once_with(project_id="project_id")
    mock_sm_mark_cancelled_and_deleted.assert_called_once_with(job_id=job_id)


@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
@patch.object(StateMachine, "set_cost_reported")
@patch.object(StateMachine, "get_by_id")
@patch("scheduler.kafka_handler.CreditSystemClient", autospec=True)
def test_on_job_failed_job_not_found(
    mock_credits_service_client, mock_sm_get_by_id, mock_sm_set_cost_reported, request
) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    message: KafkaRawMessage = KafkaRawMessage(
        "test_topic",
        0,
        0,
        int(now().timestamp()),
        0,
        b"job_id",
        {"project_id": "project_id"},
        [
            ("organization_id", b"000000000000000000000001"),
            ("workspace_id", b"63b183d00000000000000001"),
        ],
    )
    job_id = ID("job_id")
    mock_sm_get_by_id.return_value = None

    client = MagicMock()
    mock_credits_service_client.return_value = client
    client.__enter__.return_value = client

    # Act
    with pytest.raises(ValueError):
        ProgressHandler().on_job_failed(message)

    # Assert
    mock_sm_get_by_id.assert_called_once_with(job_id=job_id)
    mock_credits_service_client.assert_not_called()
    mock_sm_set_cost_reported.assert_not_called()


@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
@patch.object(StateMachine, "set_cost_reported")
@patch.object(StateMachine, "get_by_id")
@patch("scheduler.kafka_handler.CreditSystemClient", autospec=True)
def test_on_job_failed_no_cost(
    mock_credits_service_client, mock_sm_get_by_id, mock_sm_set_cost_reported, request
) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    message: KafkaRawMessage = KafkaRawMessage(
        "test_topic",
        0,
        0,
        int(now().timestamp()),
        0,
        b"job_id",
        {"project_id": "project_id"},
        [
            ("organization_id", b"000000000000000000000001"),
            ("workspace_id", b"63b183d00000000000000001"),
        ],
    )
    job_id = ID("job_id")
    job = MagicMock()
    job.cost = None
    mock_sm_get_by_id.return_value = job

    client = MagicMock()
    mock_credits_service_client.return_value = client
    client.__enter__.return_value = client

    # Act
    ProgressHandler().on_job_failed(message)

    # Assert
    mock_sm_get_by_id.assert_called_once_with(job_id=job_id)
    mock_credits_service_client.assert_not_called()
    mock_sm_set_cost_reported.assert_not_called()


@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
@patch.object(StateMachine, "set_cost_reported")
@patch.object(StateMachine, "get_by_id")
@patch("scheduler.kafka_handler.CreditSystemClient", autospec=True)
def test_on_job_failed_cancel_lease(
    mock_credits_service_client, mock_sm_get_by_id, mock_sm_set_cost_reported, request
) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    message: KafkaRawMessage = KafkaRawMessage(
        "test_topic",
        0,
        0,
        int(now().timestamp()),
        0,
        b"job_id",
        {"project_id": "project_id"},
        [
            ("organization_id", b"000000000000000000000001"),
            ("workspace_id", b"63b183d00000000000000001"),
        ],
    )
    job_id = ID("job_id")
    job = MagicMock()
    job.cost = JobCost(
        requests=(JobResource(amount=100, unit="image"),),
        lease_id="lease_id",
        consumed=(JobConsumedResource(amount=100, unit="image", consuming_date=now(), service="training"),),
        reported=False,
    )
    mock_sm_get_by_id.return_value = job

    client = MagicMock()
    mock_credits_service_client.return_value = client
    client.__enter__.return_value = client

    # Act
    ProgressHandler().on_job_failed(message)

    # Assert
    mock_sm_get_by_id.assert_called_once_with(job_id=job_id)
    mock_credits_service_client.assert_called_once()
    client.cancel_lease.assert_called_once_with(lease_id="lease_id")
    mock_sm_set_cost_reported.assert_called_once_with(job_id=job_id)


@patch.object(StateMachine, "set_cost_reported")
@patch.object(StateMachine, "get_by_id")
@patch.object(ProgressHandler, "send_metering_event")
@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
def test_on_job_finished_no_job_found(
    mock_ph_send_metering_event, mock_sm_get_by_id, mock_sm_set_cost_reported, request
) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    message: KafkaRawMessage = KafkaRawMessage(
        "test_topic",
        0,
        0,
        int(now().timestamp()),
        0,
        b"job_id",
        {"project_id": "project_id"},
        [
            ("organization_id", b"000000000000000000000001"),
            ("workspace_id", b"63b183d00000000000000001"),
        ],
    )

    mock_sm_get_by_id.return_value = None

    # Act
    with pytest.raises(ValueError):
        ProgressHandler().on_job_finished(message)

    # Assert
    mock_ph_send_metering_event.assert_not_called()
    mock_sm_set_cost_reported.assert_not_called()


@patch.object(StateMachine, "set_cost_reported")
@patch.object(StateMachine, "get_by_id")
@patch.object(ProgressHandler, "send_metering_event")
@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
def test_on_job_finished_no_cost(
    mock_ph_send_metering_event, mock_sm_get_by_id, mock_sm_set_cost_reported, request
) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    message: KafkaRawMessage = KafkaRawMessage(
        "test_topic",
        0,
        0,
        int(now().timestamp()),
        0,
        b"job_id",
        {"project_id": "project_id"},
        [
            ("organization_id", b"000000000000000000000001"),
            ("workspace_id", b"63b183d00000000000000001"),
        ],
    )

    job = MagicMock()
    job.cost = None
    mock_sm_get_by_id.return_value = job

    # Act
    ProgressHandler().on_job_finished(message)

    # Assert
    mock_ph_send_metering_event.assert_not_called()
    mock_sm_set_cost_reported.assert_not_called()


@patch.object(StateMachine, "set_cost_reported")
@patch.object(StateMachine, "get_by_id")
@patch.object(ProgressHandler, "send_metering_event")
@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
def test_on_job_finished_no_consumed_resources(
    mock_ph_send_metering_event, mock_sm_get_by_id, mock_sm_set_cost_reported, request
) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    message: KafkaRawMessage = KafkaRawMessage(
        "test_topic",
        0,
        0,
        int(now().timestamp()),
        0,
        b"job_id",
        {"project_id": "project_id"},
        [
            ("organization_id", b"000000000000000000000001"),
            ("workspace_id", b"63b183d00000000000000001"),
        ],
    )

    job = MagicMock()
    job.cost = JobCost(
        requests=(JobResource(amount=100, unit="image"),),
        lease_id="lease_id",
        consumed=(),
        reported=False,
    )
    mock_sm_get_by_id.return_value = job

    # Act
    ProgressHandler().on_job_finished(message)

    # Assert
    mock_ph_send_metering_event.assert_not_called()
    mock_sm_set_cost_reported.assert_called_once_with(job_id=ID("job_id"))


@patch.object(StateMachine, "set_cost_reported")
@patch.object(StateMachine, "get_by_id")
@patch.object(ProgressHandler, "send_metering_event")
@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
def test_on_job_finished_consumed_resources(
    mock_ph_send_metering_event, mock_sm_get_by_id, mock_sm_set_cost_reported, request
) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    message: KafkaRawMessage = KafkaRawMessage(
        "test_topic",
        0,
        0,
        int(now().timestamp()),
        0,
        b"job_id",
        {"project_id": "project_id"},
        [
            ("organization_id", b"000000000000000000000001"),
            ("workspace_id", b"63b183d00000000000000001"),
        ],
    )

    cost = JobCost(
        requests=(JobResource(amount=100, unit="image"),),
        lease_id="lease_id",
        consumed=(JobConsumedResource(amount=100, unit="image", consuming_date=now(), service="training"),),
        reported=False,
    )
    job = MagicMock()
    job.id = ID("job_id")
    job.type = "train"
    job.cost = cost
    job.project_id = None
    mock_sm_get_by_id.return_value = job

    # Act
    ProgressHandler().on_job_finished(message)

    # Assert
    mock_ph_send_metering_event.assert_called_once_with(id=ID("job_id"), type="train", cost=cost, project_id=None)
    mock_sm_set_cost_reported.assert_called_once_with(job_id=ID("job_id"))


@patch.object(StateMachine, "set_cost_reported")
@patch.object(StateMachine, "get_by_id")
@patch.object(ProgressHandler, "send_metering_event")
@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
@patch("scheduler.kafka_handler.CreditSystemClient", autospec=True)
def test_on_job_cancelled_no_job_found(
    mock_credits_service_client,
    mock_ph_send_metering_event,
    mock_sm_get_by_id,
    mock_sm_set_cost_reported,
    request,
) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    message: KafkaRawMessage = KafkaRawMessage(
        "test_topic",
        0,
        0,
        int(now().timestamp()),
        0,
        b"job_id",
        {"project_id": "project_id"},
        [
            ("organization_id", b"000000000000000000000001"),
            ("workspace_id", b"63b183d00000000000000001"),
        ],
    )

    mock_sm_get_by_id.return_value = None

    client = MagicMock()
    mock_credits_service_client.return_value = client
    client.__enter__.return_value = client

    # Act
    with pytest.raises(ValueError):
        ProgressHandler().on_job_cancelled(message)

    # Assert
    mock_ph_send_metering_event.assert_not_called()
    mock_credits_service_client.assert_not_called()
    client.cancel_lease.assert_not_called()
    mock_sm_set_cost_reported.assert_not_called()


@patch.object(StateMachine, "set_cost_reported")
@patch.object(StateMachine, "get_by_id")
@patch.object(ProgressHandler, "send_metering_event")
@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
@patch("scheduler.kafka_handler.CreditSystemClient", autospec=True)
def test_on_job_cancelled_no_cost(
    mock_credits_service_client,
    mock_ph_send_metering_event,
    mock_sm_get_by_id,
    mock_sm_set_cost_reported,
    request,
) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    message: KafkaRawMessage = KafkaRawMessage(
        "test_topic",
        0,
        0,
        int(now().timestamp()),
        0,
        b"job_id",
        {"project_id": "project_id"},
        [
            ("organization_id", b"000000000000000000000001"),
            ("workspace_id", b"63b183d00000000000000001"),
        ],
    )

    job = MagicMock()
    job.cost = None
    mock_sm_get_by_id.return_value = job

    client = MagicMock()
    mock_credits_service_client.return_value = client
    client.__enter__.return_value = client

    # Act
    ProgressHandler().on_job_cancelled(message)

    # Assert
    mock_ph_send_metering_event.assert_not_called()
    mock_credits_service_client.assert_not_called()
    client.cancel_lease.assert_not_called()
    mock_sm_set_cost_reported.assert_not_called()


@patch.object(StateMachine, "set_cost_reported")
@patch.object(StateMachine, "get_by_id")
@patch.object(ProgressHandler, "send_metering_event")
@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
@patch("scheduler.kafka_handler.CreditSystemClient", autospec=True)
def test_on_job_cancelled_no_consumed_resources(
    mock_credits_service_client,
    mock_ph_send_metering_event,
    mock_sm_get_by_id,
    mock_sm_set_cost_reported,
    request,
) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    message: KafkaRawMessage = KafkaRawMessage(
        "test_topic",
        0,
        0,
        int(now().timestamp()),
        0,
        b"job_id",
        {"project_id": "project_id"},
        [
            ("organization_id", b"000000000000000000000001"),
            ("workspace_id", b"63b183d00000000000000001"),
        ],
    )

    job = MagicMock()
    job.cost = JobCost(
        requests=(JobResource(amount=100, unit="image"),),
        lease_id="lease_id",
        consumed=(),
        reported=False,
    )
    mock_sm_get_by_id.return_value = job

    client = MagicMock()
    mock_credits_service_client.return_value = client
    client.__enter__.return_value = client

    # Act
    ProgressHandler().on_job_cancelled(message)

    # Assert
    mock_ph_send_metering_event.assert_not_called()
    mock_credits_service_client.assert_called_once()
    client.cancel_lease.assert_called_once_with(lease_id="lease_id")
    mock_sm_set_cost_reported.assert_called_once_with(job_id=ID("job_id"))


@patch.object(StateMachine, "set_cost_reported")
@patch.object(StateMachine, "get_by_id")
@patch.object(ProgressHandler, "send_metering_event")
@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
@patch("scheduler.kafka_handler.CreditSystemClient", autospec=True)
def test_on_job_cancelled_consumed_resources(
    mock_credits_service_client,
    mock_ph_send_metering_event,
    mock_sm_get_by_id,
    mock_sm_set_cost_reported,
    request,
) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    message: KafkaRawMessage = KafkaRawMessage(
        "test_topic",
        0,
        0,
        int(now().timestamp()),
        0,
        b"job_id",
        {"project_id": "project_id"},
        [
            ("organization_id", b"000000000000000000000001"),
            ("workspace_id", b"63b183d00000000000000001"),
        ],
    )

    cost = JobCost(
        requests=(JobResource(amount=100, unit="image"),),
        lease_id="lease_id",
        consumed=(JobConsumedResource(amount=100, unit="image", consuming_date=now(), service="training"),),
        reported=False,
    )
    job = MagicMock()
    job.id = ID("job_id")
    job.type = "train"
    job.cost = cost
    job.project_id = None
    mock_sm_get_by_id.return_value = job

    client = MagicMock()
    mock_credits_service_client.return_value = client
    client.__enter__.return_value = client

    # Act
    ProgressHandler().on_job_cancelled(message)

    # Assert
    mock_ph_send_metering_event.assert_called_once_with(id=ID("job_id"), type="train", cost=cost, project_id=None)
    mock_credits_service_client.assert_not_called()
    client.cancel_lease.assert_not_called()
    mock_sm_set_cost_reported.assert_called_once_with(job_id=ID("job_id"))


@patch("scheduler.kafka_handler.now", return_value=datetime(2024, 1, 1, 0, 0, 1))
@patch("scheduler.kafka_handler.publish_event")
@patch.object(ProgressHandler, "__init__", new=mock_progress_handler)
def test_send_metering_event(mock_publish, mock_now, request) -> None:
    request.addfinalizer(lambda: reset_singletons())

    # Arrange
    frozen_now = datetime(2024, 1, 1, 0, 0, 1)

    # Act
    ProgressHandler().send_metering_event(
        id=ID("job_id"),
        type="training",
        cost=JobCost(
            requests=(JobResource(amount=100, unit="image"),),
            lease_id="lease_id",
            consumed=(JobConsumedResource(amount=100, unit="image", consuming_date=frozen_now, service="training"),),
            reported=False,
        ),
        project_id="project_123",
    )

    # Assert
    mock_publish.assert_called_once_with(
        topic="credits_lease",
        body={
            "service_name": "training",
            "project_id": "project_123",
            "lease_id": "lease_id",
            "consumption": [{"amount": 100, "unit": "image"}],
            "date": frozen_now.timestamp() * 1000,
        },
        key=b"job_id",
        headers_getter=ANY,
    )
