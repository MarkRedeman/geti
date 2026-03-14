# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

from unittest.mock import MagicMock, patch

import pytest
from bson import ObjectId
from flytekit.exceptions.user import FlyteUserException

from model.job import JobStepDetails, JobTaskExecutionBranch
from model.job_state import JobTaskState
from scheduler.flyte import ExecutionType, Flyte
from scheduler.jobs_templates import JobsTemplates, JobTemplateStep
from scheduler.local_executor import LocalExecutor
from scheduler.loops.scheduling import (
    run_scheduling_loop,
    schedule_main_job,
    start_execution,
    start_main_execution,
)
from scheduler.state_machine import StateMachine

from geti_types import ID

ORG = ID(ObjectId())
job_id = ID("test_job")


def mock_flyte_client(self, *args, **kwargs) -> None:
    self.client = MagicMock()
    self.client.client = MagicMock()


def mock_state_machine(self, *args, **kwargs) -> None:
    return None


def mock_jobs_templates(self, *args, **kwargs) -> None:
    return None


def reset_singletons() -> None:
    Flyte._instance = None  # type: ignore[attr-defined]
    StateMachine._instance = None  # type: ignore[attr-defined]
    JobsTemplates._instance = None  # type: ignore[attr-defined]


@patch(
    "scheduler.loops.scheduling.schedule_main_job",
)
@patch.object(StateMachine, "find_and_lock_job_for_scheduling")
@patch.object(StateMachine, "__init__", new=mock_state_machine)
def test_run_revert_scheduling_loop_none(
    mock_find_and_lock_job_for_scheduling,
    mock_schedule_main_job,
    request,
) -> None:
    request.addfinalizer(reset_singletons)

    # Arrange
    mock_find_and_lock_job_for_scheduling.return_value = None

    # Act
    run_scheduling_loop()

    # Assert
    mock_schedule_main_job.assert_not_called()


@patch(
    "scheduler.loops.scheduling.schedule_main_job",
)
@patch.object(StateMachine, "find_and_lock_job_for_scheduling")
@patch.object(StateMachine, "__init__", new=mock_state_machine)
def test_run_scheduling_loop_works(
    mock_find_and_lock_job_for_scheduling,
    mock_schedule_main_job,
    request,
) -> None:
    """The scheduling loop should run and try to find a job."""
    request.addfinalizer(reset_singletons)

    # Arrange: no jobs to schedule
    mock_find_and_lock_job_for_scheduling.return_value = None

    # Act
    run_scheduling_loop()

    # Assert: loop ran and tried to find a job
    mock_find_and_lock_job_for_scheduling.assert_called_once_with()
    mock_schedule_main_job.assert_not_called()


@patch(
    "scheduler.loops.scheduling.schedule_main_job",
)
@patch(
    "scheduler.loops.scheduling.session_context",
)
@patch.object(StateMachine, "find_and_lock_job_for_scheduling")
@patch.object(StateMachine, "__init__", new=mock_state_machine)
def test_run_revert_scheduling_loop_schedule_revert_job(
    mock_find_and_lock_job_for_scheduling,
    mock_session_context,
    mock_schedule_main_job,
    request,
) -> None:
    request.addfinalizer(reset_singletons)

    # Arrange
    job = MagicMock()
    mock_find_and_lock_job_for_scheduling.side_effect = [job, None]

    # Act
    run_scheduling_loop()

    # Assert
    mock_session_context.assert_called_once_with(session=job.session)
    mock_schedule_main_job.assert_called_once_with(job_id=job.id)


@patch.object(JobsTemplates, "get_job_steps")
@patch(
    "scheduler.loops.scheduling.start_main_execution",
)
@patch.object(StateMachine, "set_and_publish_failed_state")
@patch.object(StateMachine, "set_scheduled_state")
@patch.object(StateMachine, "reset_scheduling_job")
@patch.object(StateMachine, "get_by_id")
@patch.object(StateMachine, "__init__", new=mock_state_machine)
def test_schedule_main_job_not_found(
    mock_js_get_by_id,
    mock_js_reset_scheduling_job,
    mock_js_set_scheduled_state,
    mock_js_set_and_publish_failed_state,
    mock_start_main_execution,
    mock_get_job_steps,
    fxt_job,
    request,
) -> None:
    request.addfinalizer(reset_singletons)

    # Arrange
    mock_js_get_by_id.return_value = None

    # Act
    schedule_main_job(job_id=job_id)

    # Assert
    mock_js_get_by_id.assert_called_once_with(job_id=job_id)
    mock_js_reset_scheduling_job.assert_not_called()
    mock_js_set_scheduled_state.assert_not_called()
    mock_js_set_and_publish_failed_state.assert_not_called()
    mock_start_main_execution.assert_not_called()
    mock_get_job_steps.assert_not_called()


@patch.object(JobsTemplates, "get_job_steps")
@patch(
    "scheduler.loops.scheduling.start_main_execution",
    side_effect=FlyteUserException("Failed to start execution"),
)
@patch.object(StateMachine, "set_and_publish_failed_state")
@patch.object(StateMachine, "set_scheduled_state")
@patch.object(StateMachine, "reset_scheduling_job")
@patch.object(StateMachine, "get_by_id")
@patch.object(StateMachine, "__init__", new=mock_state_machine)
def test_schedule_main_job_failure(
    mock_js_get_by_id,
    mock_js_reset_scheduling_job,
    mock_js_set_scheduled_state,
    mock_js_set_and_publish_failed_state,
    mock_start_main_execution,
    mock_get_job_steps,
    fxt_job,
    request,
) -> None:
    request.addfinalizer(reset_singletons)

    # Arrange
    mock_js_get_by_id.return_value = fxt_job

    # Act
    schedule_main_job(job_id=job_id)

    # Assert
    mock_js_get_by_id.assert_called_once_with(job_id=job_id)
    mock_js_reset_scheduling_job.assert_called_once_with(job_id=job_id)
    mock_js_set_scheduled_state.assert_not_called()
    mock_js_set_and_publish_failed_state.assert_not_called()
    mock_start_main_execution.assert_called_once_with(job=fxt_job)
    mock_get_job_steps.assert_not_called()


@patch.object(JobsTemplates, "get_job_steps")
@patch.object(JobsTemplates, "__init__", new=mock_jobs_templates)
@patch("scheduler.loops.scheduling.start_main_execution")
@patch.object(StateMachine, "set_and_publish_failed_state")
@patch.object(StateMachine, "set_scheduled_state")
@patch.object(StateMachine, "reset_scheduling_job")
@patch.object(StateMachine, "get_by_id")
@patch.object(StateMachine, "__init__", new=mock_state_machine)
def test_schedule_main_job_success(
    mock_js_get_by_id,
    mock_js_reset_scheduling_job,
    mock_js_set_scheduled_state,
    mock_js_set_and_publish_failed_state,
    mock_start_main_execution,
    mock_get_job_steps,
    fxt_job,
    request,
) -> None:
    request.addfinalizer(reset_singletons)

    # Arrange
    mock_js_get_by_id.return_value = fxt_job

    execution_name = "ex-test-job"
    launch_plan_id = "lp-test-job"
    mock_start_main_execution.return_value = execution_name, launch_plan_id

    step_details = [
        JobTemplateStep(name="Test task 1", task_id="task_id_1"),
        JobTemplateStep(
            name="Test task 2",
            task_id="task_id_2",
            branches=[
                {
                    "condition": "condition",
                    "branch": "branch",
                    "skip_message": "Step is skipped",
                }
            ],
        ),
    ]
    mock_get_job_steps.return_value = step_details

    # Act
    schedule_main_job(job_id=job_id)

    # Assert
    mock_js_get_by_id.assert_called_once_with(job_id=job_id)
    mock_js_reset_scheduling_job.assert_not_called()
    mock_js_set_scheduled_state.assert_called_once_with(
        job_id=job_id,
        launch_plan_id=launch_plan_id,
        execution_id=execution_name,
        step_details=[
            JobStepDetails(
                index=1,
                task_id="task_id_1",
                step_name="Test task 1",
                state=JobTaskState.WAITING,
                progress=-1,
            ),
            JobStepDetails(
                index=2,
                task_id="task_id_2",
                step_name="Test task 2",
                state=JobTaskState.WAITING,
                branches=(JobTaskExecutionBranch(condition="condition", branch="branch"),),
                progress=-1,
            ),
        ],
    )
    mock_js_set_and_publish_failed_state.assert_not_called()
    mock_start_main_execution.assert_called_once_with(job=fxt_job)
    mock_get_job_steps.assert_called_once_with(job_type=fxt_job.type)


@patch.object(JobsTemplates, "get_job_steps")
@patch("scheduler.loops.scheduling.start_main_execution")
@patch.object(StateMachine, "set_and_publish_failed_state")
@patch.object(StateMachine, "set_scheduled_state")
@patch.object(StateMachine, "reset_scheduling_job")
@patch.object(StateMachine, "get_by_id")
@patch.object(StateMachine, "__init__", new=mock_state_machine)
def test_schedule_main_job_max_retry_counter(
    mock_js_get_by_id,
    mock_js_reset_scheduling_job,
    mock_js_set_scheduled_state,
    mock_js_set_and_publish_failed_state,
    mock_start_main_execution,
    mock_get_job_steps,
    fxt_job,
    request,
) -> None:
    request.addfinalizer(reset_singletons)

    # Arrange
    fxt_job.executions.main.start_retry_counter = 10
    mock_js_get_by_id.return_value = fxt_job

    execution = MagicMock()
    mock_start_main_execution.return_value = execution

    # Act
    schedule_main_job(job_id=job_id)

    # Assert
    mock_js_get_by_id.assert_called_once_with(job_id=job_id)
    mock_js_reset_scheduling_job.assert_not_called()
    mock_js_set_scheduled_state.assert_not_called()
    mock_js_set_and_publish_failed_state.assert_called_once_with(job_id=job_id)
    mock_start_main_execution.assert_not_called()
    mock_get_job_steps.assert_not_called()


@patch("scheduler.loops.scheduling.LocalExecutor")
@patch(
    "scheduler.loops.scheduling.get_main_execution_name",
)
def test_start_main_execution_no_workflow(
    mock_get_main_execution_name,
    mock_local_executor_cls,
    fxt_job,
    request,
) -> None:
    request.addfinalizer(reset_singletons)

    # Arrange
    mock_get_main_execution_name.return_value = "execution_name"
    mock_local_executor_cls.return_value.start_execution.return_value = "container_id"

    # Act
    result = start_main_execution(job=fxt_job)

    # Assert
    mock_get_main_execution_name.assert_called_once_with(job_id=fxt_job.id)
    mock_local_executor_cls.return_value.start_execution.assert_called_once()
    assert result == ("execution_name", "execution_name")


@patch("scheduler.loops.scheduling.LocalExecutor")
@patch(
    "scheduler.loops.scheduling.get_main_execution_name",
)
def test_start_main_execution(
    mock_get_main_execution_name,
    mock_local_executor_cls,
    fxt_job,
    request,
) -> None:
    request.addfinalizer(reset_singletons)

    # Arrange
    mock_get_main_execution_name.return_value = "execution_name"
    mock_local_executor_cls.return_value.start_execution.return_value = "container_id"

    # Act
    result = start_main_execution(job=fxt_job)

    # Assert
    mock_get_main_execution_name.assert_called_once_with(job_id=fxt_job.id)
    mock_local_executor_cls.return_value.start_execution.assert_called_once()
    assert result == ("execution_name", "execution_name")


@patch.object(Flyte, "start_workflow_execution")
@patch.object(Flyte, "fetch_workflow_execution")
@patch.object(Flyte, "__init__", new=mock_flyte_client)
def test_start_execution_existing(
    mock_flyte_fetch_workflow_execution,
    mock_flyte_start_workflow_execution,
    fxt_job,
    request,
) -> None:
    request.addfinalizer(reset_singletons)

    # Act / Assert
    with pytest.raises(RuntimeError, match="outside compose mode"):
        start_execution(
            job=fxt_job,
            workflow=MagicMock(),
            execution_type=ExecutionType.MAIN,
            execution_name="execution_name",
            payload={"key": "value"},
        )

    mock_flyte_fetch_workflow_execution.assert_not_called()
    mock_flyte_start_workflow_execution.assert_not_called()


@patch.object(Flyte, "start_workflow_execution")
@patch.object(Flyte, "fetch_workflow_execution")
@patch.object(Flyte, "__init__", new=mock_flyte_client)
def test_start_execution_new(
    mock_flyte_fetch_workflow_execution,
    mock_flyte_start_workflow_execution,
    fxt_job,
    request,
) -> None:
    request.addfinalizer(reset_singletons)

    # Act / Assert
    with pytest.raises(RuntimeError, match="outside compose mode"):
        start_execution(
            job=fxt_job,
            workflow=MagicMock(),
            execution_type=ExecutionType.MAIN,
            execution_name="execution_name",
            payload={"key": "value"},
        )

    mock_flyte_fetch_workflow_execution.assert_not_called()
    mock_flyte_start_workflow_execution.assert_not_called()
