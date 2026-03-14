# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

from unittest.mock import MagicMock, patch

from model.job import JobRevertFlyteExecution
from scheduler.loops.revert_scheduling import (
    run_revert_scheduling_loop,
    schedule_revert_job,
    start_revert_execution,
)
from scheduler.state_machine import StateMachine

from geti_types import ID

job_id = ID("test_job")


def mock_state_machine(self, *args, **kwargs) -> None:
    return None


def reset_singletons() -> None:
    StateMachine._instance = None  # type: ignore[attr-defined]


@patch(
    "scheduler.loops.revert_scheduling.schedule_revert_job",
)
@patch.object(StateMachine, "find_and_lock_job_for_reverting")
@patch.object(StateMachine, "__init__", new=mock_state_machine)
def test_run_revert_scheduling_loop_none(
    mock_find_and_lock_job_for_reverting,
    mock_schedule_revert_job,
    request,
) -> None:
    request.addfinalizer(reset_singletons)

    # Arrange
    mock_find_and_lock_job_for_reverting.return_value = None

    # Act
    run_revert_scheduling_loop()

    # Assert
    mock_schedule_revert_job.assert_not_called()


@patch(
    "scheduler.loops.revert_scheduling.schedule_revert_job",
)
@patch.object(StateMachine, "find_and_lock_job_for_reverting")
@patch.object(StateMachine, "__init__", new=mock_state_machine)
def test_run_revert_scheduling_loop_works(
    mock_find_and_lock_job_for_reverting,
    mock_schedule_revert_job,
    request,
) -> None:
    """The revert scheduling loop should run and try to find a job."""
    request.addfinalizer(reset_singletons)

    # Arrange: no jobs to revert
    mock_find_and_lock_job_for_reverting.return_value = None

    # Act
    run_revert_scheduling_loop()

    # Assert: loop ran and tried to find a job
    mock_find_and_lock_job_for_reverting.assert_called_once_with()
    mock_schedule_revert_job.assert_not_called()


@patch(
    "scheduler.loops.revert_scheduling.schedule_revert_job",
)
@patch(
    "scheduler.loops.revert_scheduling.session_context",
)
@patch.object(StateMachine, "find_and_lock_job_for_reverting")
@patch.object(StateMachine, "__init__", new=mock_state_machine)
def test_run_revert_scheduling_loop_schedule_revert_job(
    mock_find_and_lock_job_for_reverting,
    mock_session_context,
    mock_schedule_revert_job,
    request,
) -> None:
    request.addfinalizer(reset_singletons)

    # Arrange
    job = MagicMock()
    mock_find_and_lock_job_for_reverting.side_effect = [job, None]

    # Act
    run_revert_scheduling_loop()

    # Assert
    mock_session_context.assert_called_once_with(session=job.session)
    mock_schedule_revert_job.assert_called_once_with(job_id=job.id)


@patch(
    "scheduler.loops.revert_scheduling.start_revert_execution",
)
@patch.object(StateMachine, "set_and_publish_failed_state")
@patch.object(StateMachine, "set_and_publish_cancelled_state")
@patch.object(StateMachine, "set_revert_scheduled_state")
@patch.object(StateMachine, "reset_revert_scheduling_job")
@patch.object(StateMachine, "get_by_id")
@patch.object(StateMachine, "__init__", new=mock_state_machine)
def test_schedule_revert_job_not_found(
    mock_js_get_by_id,
    mock_js_reset_revert_scheduling_job,
    mock_js_set_scheduled_state,
    mock_js_set_and_publish_cancelled_state,
    mock_js_set_and_publish_failed_state,
    mock_start_revert_execution,
    fxt_job,
    request,
) -> None:
    request.addfinalizer(reset_singletons)

    # Arrange
    mock_js_get_by_id.return_value = None

    # Act
    schedule_revert_job(job_id=job_id)

    # Assert
    mock_js_get_by_id.assert_called_once_with(job_id=job_id)
    mock_js_reset_revert_scheduling_job.assert_not_called()
    mock_js_set_scheduled_state.assert_not_called()
    mock_js_set_and_publish_cancelled_state.assert_not_called()
    mock_js_set_and_publish_failed_state.assert_not_called()
    mock_start_revert_execution.assert_not_called()


@patch(
    "scheduler.loops.revert_scheduling.start_revert_execution",
    side_effect=Exception("Failed to start execution"),
)
@patch.object(StateMachine, "set_and_publish_failed_state")
@patch.object(StateMachine, "set_and_publish_cancelled_state")
@patch.object(StateMachine, "set_revert_scheduled_state")
@patch.object(StateMachine, "reset_revert_scheduling_job")
@patch.object(StateMachine, "get_by_id")
@patch.object(StateMachine, "__init__", new=mock_state_machine)
def test_schedule_revert_job_failure(
    mock_js_get_by_id,
    mock_js_reset_revert_scheduling_job,
    mock_js_set_revert_scheduled_state,
    mock_js_set_and_publish_cancelled_state,
    mock_js_set_and_publish_failed_state,
    mock_start_revert_execution,
    fxt_job,
    request,
) -> None:
    request.addfinalizer(reset_singletons)

    # Arrange
    mock_js_get_by_id.return_value = fxt_job

    # Act
    schedule_revert_job(job_id=job_id)

    # Assert
    mock_js_get_by_id.assert_called_once_with(job_id=job_id)
    mock_js_reset_revert_scheduling_job.assert_called_once_with(job_id=job_id)
    mock_js_set_revert_scheduled_state.assert_not_called()
    mock_js_set_and_publish_cancelled_state.assert_not_called()
    mock_js_set_and_publish_failed_state.assert_not_called()
    mock_start_revert_execution.assert_called_once_with(job=fxt_job)


@patch("scheduler.loops.revert_scheduling.start_revert_execution")
@patch.object(StateMachine, "set_and_publish_failed_state")
@patch.object(StateMachine, "set_and_publish_cancelled_state")
@patch.object(StateMachine, "set_revert_scheduled_state")
@patch.object(StateMachine, "reset_revert_scheduling_job")
@patch.object(StateMachine, "get_by_id")
@patch.object(StateMachine, "__init__", new=mock_state_machine)
def test_schedule_revert_job_no_revert_cancelled(
    mock_js_get_by_id,
    mock_js_reset_revert_scheduling_job,
    mock_js_set_revert_scheduled_state,
    mock_js_set_and_publish_cancelled_state,
    mock_js_set_and_publish_failed_state,
    mock_start_revert_execution,
    fxt_job,
    request,
) -> None:
    request.addfinalizer(reset_singletons)

    # Arrange
    fxt_job.cancellation_info.is_cancelled = True
    mock_js_get_by_id.return_value = fxt_job

    mock_start_revert_execution.return_value = None

    # Act
    schedule_revert_job(job_id=job_id)

    # Assert
    mock_js_get_by_id.assert_called_once_with(job_id=job_id)
    mock_js_reset_revert_scheduling_job.assert_not_called()
    mock_js_set_revert_scheduled_state.assert_not_called()
    mock_js_set_and_publish_cancelled_state.assert_called_once_with(job_id=job_id)
    mock_js_set_and_publish_failed_state.assert_not_called()
    mock_start_revert_execution.assert_called_once_with(job=fxt_job)


@patch("scheduler.loops.revert_scheduling.start_revert_execution")
@patch.object(StateMachine, "set_and_publish_failed_state")
@patch.object(StateMachine, "set_and_publish_cancelled_state")
@patch.object(StateMachine, "set_revert_scheduled_state")
@patch.object(StateMachine, "reset_revert_scheduling_job")
@patch.object(StateMachine, "get_by_id")
@patch.object(StateMachine, "__init__", new=mock_state_machine)
def test_schedule_revert_job_no_revert_failed(
    mock_js_get_by_id,
    mock_js_reset_revert_scheduling_job,
    mock_js_set_revert_scheduled_state,
    mock_js_set_and_publish_cancelled_state,
    mock_js_set_and_publish_failed_state,
    mock_start_revert_execution,
    fxt_job,
    request,
) -> None:
    request.addfinalizer(reset_singletons)

    # Arrange
    fxt_job.cancellation_info.is_cancelled = False
    mock_js_get_by_id.return_value = fxt_job

    mock_start_revert_execution.return_value = None

    # Act
    schedule_revert_job(job_id=job_id)

    # Assert
    mock_js_get_by_id.assert_called_once_with(job_id=job_id)
    mock_js_reset_revert_scheduling_job.assert_not_called()
    mock_js_set_revert_scheduled_state.assert_not_called()
    mock_js_set_and_publish_cancelled_state.assert_not_called()
    mock_js_set_and_publish_failed_state.assert_called_once_with(job_id=job_id)
    mock_start_revert_execution.assert_called_once_with(job=fxt_job)


@patch("scheduler.loops.revert_scheduling.start_revert_execution")
@patch.object(StateMachine, "set_and_publish_failed_state")
@patch.object(StateMachine, "set_and_publish_cancelled_state")
@patch.object(StateMachine, "set_revert_scheduled_state")
@patch.object(StateMachine, "reset_revert_scheduling_job")
@patch.object(StateMachine, "get_by_id")
@patch.object(StateMachine, "__init__", new=mock_state_machine)
def test_schedule_revert_job_revert(
    mock_js_get_by_id,
    mock_js_reset_revert_scheduling_job,
    mock_js_set_revert_scheduled_state,
    mock_js_set_and_publish_cancelled_state,
    mock_js_set_and_publish_failed_state,
    mock_start_revert_execution,
    fxt_job,
    request,
) -> None:
    request.addfinalizer(reset_singletons)

    # Arrange
    fxt_job.cancellation_info.is_cancelled = False
    mock_js_get_by_id.return_value = fxt_job

    mock_start_revert_execution.return_value = "execution-id"

    # Act
    schedule_revert_job(job_id=job_id)

    # Assert
    mock_js_get_by_id.assert_called_once_with(job_id=job_id)
    mock_js_reset_revert_scheduling_job.assert_not_called()
    mock_js_set_revert_scheduled_state.assert_called_once_with(
        job_id=job_id,
        execution_id="execution-id",
    )
    mock_js_set_and_publish_cancelled_state.assert_not_called()
    mock_js_set_and_publish_failed_state.assert_not_called()
    mock_start_revert_execution.assert_called_once_with(job=fxt_job)


@patch("scheduler.loops.revert_scheduling.start_revert_execution")
@patch.object(StateMachine, "set_and_publish_failed_state")
@patch.object(StateMachine, "set_and_publish_cancelled_state")
@patch.object(StateMachine, "set_revert_scheduled_state")
@patch.object(StateMachine, "reset_revert_scheduling_job")
@patch.object(StateMachine, "get_by_id")
@patch.object(StateMachine, "__init__", new=mock_state_machine)
def test_schedule_revert_job_max_retry_counter_cancelled(
    mock_js_get_by_id,
    mock_js_reset_revert_scheduling_job,
    mock_js_set_revert_scheduled_state,
    mock_js_set_and_publish_cancelled_state,
    mock_js_set_and_publish_failed_state,
    mock_start_revert_execution,
    fxt_job,
    request,
) -> None:
    request.addfinalizer(reset_singletons)

    # Arrange
    fxt_job.executions.revert = JobRevertFlyteExecution(start_retry_counter=10)
    fxt_job.cancellation_info.is_cancelled = True
    mock_js_get_by_id.return_value = fxt_job

    execution = MagicMock()
    mock_start_revert_execution.return_value = execution

    # Act
    schedule_revert_job(job_id=job_id)

    # Assert
    mock_js_get_by_id.assert_called_once_with(job_id=job_id)
    mock_js_reset_revert_scheduling_job.assert_not_called()
    mock_js_set_revert_scheduled_state.assert_not_called()
    mock_js_set_and_publish_failed_state.assert_not_called()
    mock_js_set_and_publish_cancelled_state.assert_called_once_with(job_id=job_id)
    mock_start_revert_execution.assert_not_called()


@patch("scheduler.loops.revert_scheduling.start_revert_execution")
@patch.object(StateMachine, "set_and_publish_failed_state")
@patch.object(StateMachine, "set_and_publish_cancelled_state")
@patch.object(StateMachine, "set_revert_scheduled_state")
@patch.object(StateMachine, "reset_revert_scheduling_job")
@patch.object(StateMachine, "get_by_id")
@patch.object(StateMachine, "__init__", new=mock_state_machine)
def test_schedule_revert_job_max_retry_counter_failed(
    mock_js_get_by_id,
    mock_js_reset_revert_scheduling_job,
    mock_js_set_revert_scheduled_state,
    mock_js_set_and_publish_cancelled_state,
    mock_js_set_and_publish_failed_state,
    mock_start_revert_execution,
    fxt_job,
    request,
) -> None:
    request.addfinalizer(reset_singletons)

    # Arrange
    fxt_job.executions.revert = JobRevertFlyteExecution(start_retry_counter=10)
    fxt_job.cancellation_info.is_cancelled = False
    mock_js_get_by_id.return_value = fxt_job

    execution = MagicMock()
    mock_start_revert_execution.return_value = execution

    # Act
    schedule_revert_job(job_id=job_id)

    # Assert
    mock_js_get_by_id.assert_called_once_with(job_id=job_id)
    mock_js_reset_revert_scheduling_job.assert_not_called()
    mock_js_set_revert_scheduled_state.assert_not_called()
    mock_js_set_and_publish_failed_state.assert_called_once_with(job_id=job_id)
    mock_js_set_and_publish_cancelled_state.assert_not_called()
    mock_start_revert_execution.assert_not_called()


@patch("scheduler.loops.revert_scheduling.LocalExecutor")
@patch(
    "scheduler.loops.revert_scheduling.get_revert_execution_name",
)
def test_start_revert_execution_no_workflow(
    mock_get_revert_execution_name,
    mock_local_executor_cls,
    fxt_job,
    request,
) -> None:
    request.addfinalizer(reset_singletons)

    # Arrange: resolve_revert_job returns None → no execution started
    mock_get_revert_execution_name.return_value = "execution_name"
    with patch("scheduler.loops.revert_scheduling.resolve_revert_job", return_value=None):
        # Act
        result = start_revert_execution(job=fxt_job)

    mock_get_revert_execution_name.assert_called_once_with(job_id=fxt_job.id)
    mock_local_executor_cls.return_value.start_execution.assert_not_called()
    assert result is None


@patch("scheduler.loops.revert_scheduling.LocalExecutor")
@patch(
    "scheduler.loops.revert_scheduling.get_revert_execution_name",
)
def test_start_revert_execution(
    mock_get_revert_execution_name,
    mock_local_executor_cls,
    fxt_job,
    request,
) -> None:
    request.addfinalizer(reset_singletons)

    # Arrange: resolve_revert_job returns a value → execution is started
    mock_get_revert_execution_name.return_value = "execution_name"
    mock_local_executor_cls.return_value.start_execution.return_value = "container_id"
    with patch(
        "scheduler.loops.revert_scheduling.resolve_revert_job", return_value=("workflow_name", "workflow_version")
    ):
        # Act
        result = start_revert_execution(job=fxt_job)

    mock_get_revert_execution_name.assert_called_once_with(job_id=fxt_job.id)
    mock_local_executor_cls.return_value.start_execution.assert_called_once()
    assert result == "execution_name"


