# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE
from copy import deepcopy
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, call, patch

import pytest
from bson import ObjectId

from model.telemetry import Telemetry
from scheduler.flyte import ExecutionType, Flyte

from geti_types import ID, make_session

if TYPE_CHECKING:
    from flytekit.models.execution import Execution
    from flytekit.remote import FlyteLaunchPlan, FlyteNode, FlyteTask, FlyteWorkflow, FlyteWorkflowExecution
    from flytekit.remote.entities import FlyteBranchNode

ORGANIZATION_ID = str(ObjectId())


def mock_flyte_client(self, *args, **kwargs) -> None:
    self.client = MagicMock()
    self.client.client = MagicMock()


def reset_singletons() -> None:
    Flyte._instance = None  # type: ignore[attr-defined]


@patch.object(Flyte, "__init__", new=mock_flyte_client)
def test_fetch_workflow(request) -> None:
    request.addfinalizer(reset_singletons)

    # Arrange

    # Act
    Flyte().fetch_workflow(
        workflow_name="workflow_name",
        workflow_version="workflow_version",
    )

    # Assert
    Flyte().client.fetch_workflow.assert_called_once_with(name="workflow_name", version="workflow_version")


@pytest.mark.parametrize(
    "workspace_id, project_id, execution_type, values",
    [
        (
            "workspace",
            None,
            ExecutionType.MAIN,
            {
                "workspace_id": "workspace",
                "execution_type": "MAIN",
                "opentelemetry_context": "context",
                "organization_id": ORGANIZATION_ID,
                "report_resources_consumption": "true",
            },
        ),
        (
            "workspace",
            "project",
            ExecutionType.MAIN,
            {
                "workspace_id": "workspace",
                "project_id": "project",
                "execution_type": "MAIN",
                "opentelemetry_context": "context",
                "organization_id": ORGANIZATION_ID,
                "report_resources_consumption": "true",
            },
        ),
        (
            "workspace",
            None,
            ExecutionType.REVERT,
            {
                "workspace_id": "workspace",
                "execution_type": "REVERT",
                "opentelemetry_context": "context",
                "organization_id": ORGANIZATION_ID,
                "report_resources_consumption": "true",
            },
        ),
        (
            "workspace",
            "project",
            ExecutionType.REVERT,
            {
                "workspace_id": "workspace",
                "project_id": "project",
                "execution_type": "REVERT",
                "opentelemetry_context": "context",
                "organization_id": ORGANIZATION_ID,
                "report_resources_consumption": "true",
            },
        ),
    ],
)
@patch.object(Flyte, "__init__", new=mock_flyte_client)
def test_start_workflow_execution(request, workspace_id, project_id, execution_type, values, fxt_job) -> None:
    values["job_id"] = fxt_job.id

    annotations = deepcopy(values)
    annotations["job_type"] = fxt_job.type
    annotations["job_name"] = fxt_job.job_name
    annotations["job_author"] = str(fxt_job.author)
    annotations["job_start_time"] = fxt_job.start_time.isoformat()
    request.addfinalizer(reset_singletons)

    # Arrange
    workflow = MagicMock()  # FlyteWorkflow

    # Patch the lazy-loaded flytekit symbols so no real flytekit import is needed
    mock_labels = MagicMock()
    mock_annotations = MagicMock()
    mock_options_cls = MagicMock()
    mock_options_instance = MagicMock()
    mock_options_cls.return_value = mock_options_instance

    mock_symbols = {
        "Labels": mock_labels,
        "Annotations": mock_annotations,
        "Options": mock_options_cls,
        "FlyteEntityNotExistException": Exception,
        "ValueIn": MagicMock(),
        "FlyteLaunchPlan": MagicMock(),
        "FlyteNode": MagicMock(),
        "FlyteRemote": MagicMock(),
        "FlyteTask": MagicMock(),
        "FlyteWorkflow": MagicMock(),
        "FlyteWorkflowExecution": MagicMock(),
        "FlyteBranchNode": MagicMock(),
        "Config": MagicMock(),
    }

    with patch("scheduler.flyte._load_flyte_symbols", return_value=mock_symbols):
        # Act
        Flyte().start_workflow_execution(
            workspace_id=workspace_id,
            job=fxt_job,
            project_id=project_id,
            execution_type=execution_type,
            execution_name="execution_name",
            workflow=workflow,
            payload={"a": 1, "b": 2, "c": 3, "d": 4},
            telemetry=Telemetry(context=values["opentelemetry_context"]),
            session=make_session(
                organization_id=ID(ORGANIZATION_ID),
            ),
        )

    # Assert
    Flyte().client.execute_remote_wf.assert_called_once_with(
        entity=workflow,
        execution_name="execution_name",
        wait=False,
        inputs={"a": 1, "b": 2, "c": 3, "d": 4},
        options=mock_options_instance,
    )


@pytest.mark.parametrize(
    "execution_type, result",
    [
        ("MAIN", ExecutionType.MAIN),
        ("REVERT", ExecutionType.REVERT),
    ],
)
def test_get_execution_type(execution_type, result) -> None:
    # Arrange
    execution = MagicMock()  # FlyteWorkflowExecution
    execution.spec.annotations.values = {"execution_type": execution_type}

    # Act
    execution_type = Flyte.get_execution_type(execution)

    # Assert
    assert execution_type == result


def test_get_execution_workspace_id() -> None:
    # Arrange
    execution = MagicMock()  # FlyteWorkflowExecution
    execution.spec.annotations.values = {"workspace_id": "workspace"}

    # Act
    workspace_id = Flyte.get_execution_workspace_id(execution)

    # Assert
    assert workspace_id == "workspace"


def test_get_execution_job_id() -> None:
    # Arrange
    execution = MagicMock()  # FlyteWorkflowExecution
    execution.spec.annotations.values = {"job_id": "job"}

    # Act
    job_id = Flyte.get_execution_job_id(execution)

    # Assert
    assert job_id == "job"


@patch.object(Flyte, "__init__", new=mock_flyte_client)
def test_cancel_workflow_execution(request) -> None:
    request.addfinalizer(reset_singletons)

    # Arrange
    execution = MagicMock()  # FlyteWorkflowExecution

    # Act
    Flyte().cancel_workflow_execution(execution=execution)

    # Assert
    Flyte().client.terminate.assert_called_once_with(execution=execution, cause="Canceling execution")


@patch.object(Flyte, "__init__", new=mock_flyte_client)
def test_fetch_execution_not_found(request) -> None:
    request.addfinalizer(reset_singletons)

    # Arrange – use a unique sentinel exception type so isinstance check in runtime passes
    class _FlyteEntityNotExistException(Exception):
        pass

    mock_symbols = {"FlyteEntityNotExistException": _FlyteEntityNotExistException}
    Flyte().client.fetch_execution.side_effect = _FlyteEntityNotExistException()

    with patch("scheduler.flyte._load_flyte_symbols", return_value=mock_symbols):
        # Act
        found_execution = Flyte().fetch_workflow_execution(execution_name="execution_name")

    # Assert
    Flyte().client.fetch_execution.assert_called_once_with(name="execution_name")
    assert found_execution is None


@patch.object(Flyte, "__init__", new=mock_flyte_client)
def test_fetch_execution_found(request) -> None:
    request.addfinalizer(reset_singletons)

    # Arrange
    execution = MagicMock()  # Execution
    Flyte().client.fetch_execution.return_value = execution

    mock_symbols = {"FlyteEntityNotExistException": Exception}

    with patch("scheduler.flyte._load_flyte_symbols", return_value=mock_symbols):
        # Act
        found_execution = Flyte().fetch_workflow_execution(execution_name="execution_name")

    # Assert
    Flyte().client.fetch_execution.assert_called_once_with(name="execution_name")
    Flyte().client.sync_execution.assert_not_called()
    assert found_execution == execution


@patch.object(Flyte, "__init__", new=mock_flyte_client)
def test_list_workflow_executions_empty_list(request) -> None:
    request.addfinalizer(reset_singletons)

    # Arrange
    client = MagicMock()
    Flyte().client.client = client

    # Act
    executions = Flyte().list_workflow_executions(execution_names=[])

    # Assert
    client.list_executions_paginated.assert_not_called()
    assert executions == []


@patch.object(Flyte, "__init__", new=mock_flyte_client)
def test_list_workflow_executions(request) -> None:
    request.addfinalizer(reset_singletons)

    # Arrange
    execution = MagicMock()
    client = MagicMock()
    Flyte().client.client = client
    client.list_executions_paginated.return_value = ([execution], "")

    mock_value_in_cls = MagicMock()
    mock_value_in_instance = MagicMock()
    mock_value_in_cls.return_value = mock_value_in_instance

    mock_fwe_cls = MagicMock()
    promoted = MagicMock()
    promoted.id = execution.id
    mock_fwe_cls.promote_from_model.return_value = promoted

    mock_symbols = {
        "ValueIn": mock_value_in_cls,
        "FlyteWorkflowExecution": mock_fwe_cls,
    }

    with patch("scheduler.flyte._load_flyte_symbols", return_value=mock_symbols):
        # Act
        executions = Flyte().list_workflow_executions(execution_names=["execution_name"])

    # Assert
    client.list_executions_paginated.assert_called_once_with(
        project="impt-jobs",
        domain="production",
        filters=[mock_value_in_instance],
    )
    assert len(executions) == 1
    assert executions[0].id == execution.id


@patch.object(Flyte, "__init__", new=mock_flyte_client)
def test_fetch_task_not_found(request) -> None:
    request.addfinalizer(reset_singletons)

    # Arrange
    class _FlyteEntityNotExistException(Exception):
        pass

    mock_symbols = {"FlyteEntityNotExistException": _FlyteEntityNotExistException}
    Flyte().client.fetch_task.side_effect = _FlyteEntityNotExistException()

    with patch("scheduler.flyte._load_flyte_symbols", return_value=mock_symbols):
        # Act
        found_execution = Flyte().fetch_task(name="step_name", version="task_version")

    # Assert
    Flyte().client.fetch_task.assert_called_once_with(
        project="impt-jobs",
        domain="production",
        name="step_name",
        version="task_version",
    )
    assert found_execution is None


@patch.object(Flyte, "__init__", new=mock_flyte_client)
def test_fetch_task_found(request) -> None:
    request.addfinalizer(reset_singletons)

    # Arrange
    task = MagicMock()  # FlyteTask
    Flyte().client.fetch_task.return_value = task

    mock_symbols = {"FlyteEntityNotExistException": Exception}

    with patch("scheduler.flyte._load_flyte_symbols", return_value=mock_symbols):
        # Act
        found_task = Flyte().fetch_task(name="step_name", version="task_version")

    # Assert
    Flyte().client.fetch_task.assert_called_once_with(
        project="impt-jobs",
        domain="production",
        name="step_name",
        version="task_version",
    )
    assert found_task == task


@patch("scheduler.flyte.Flyte.get_node_branch_nodes")
def test_get_workflow_branch_nodes(mock_get_node_branch_nodes) -> None:
    # Arrange
    workflow = MagicMock()  # FlyteWorkflow
    node1 = MagicMock()  # FlyteNode
    node2 = MagicMock()  # FlyteNode

    workflow.flyte_nodes = [node1, node2]

    mock_get_node_branch_nodes.side_effect = [{"n1": node1}, {"n2": node2}]

    # Act
    branch_nodes = Flyte.get_workflow_branch_nodes(workflow=workflow)

    # Assert
    mock_get_node_branch_nodes.assert_has_calls(
        [call(node=node1)],
        [call(node=node2)],
    )
    assert branch_nodes == {"n1": node1, "n2": node2}


def test_get_node_branch_nodes_task_node() -> None:
    # Arrange – task node: flyte_entity is not a workflow/launch_plan/branch_node
    # Use a unique class so isinstance checks in runtime don't match
    class _FlyteTask:
        pass

    class _FlyteWorkflow:
        pass

    class _FlyteLaunchPlan:
        pass

    class _FlyteBranchNode:
        pass

    mock_symbols = {
        "FlyteWorkflow": _FlyteWorkflow,
        "FlyteLaunchPlan": _FlyteLaunchPlan,
        "FlyteBranchNode": _FlyteBranchNode,
    }

    node = MagicMock()
    node.flyte_entity = _FlyteTask()

    with patch("scheduler.flyte._load_flyte_symbols", return_value=mock_symbols):
        # Act
        branch_nodes = Flyte.get_node_branch_nodes(node=node)

    # Assert
    assert branch_nodes == {}


@patch("scheduler.flyte.Flyte.get_workflow_branch_nodes")
def test_get_node_branch_nodes_workflow_node(mock_get_workflow_branch_nodes) -> None:
    # Arrange
    class _FlyteWorkflow:
        pass

    class _FlyteLaunchPlan:
        pass

    class _FlyteBranchNode:
        pass

    mock_symbols = {
        "FlyteWorkflow": _FlyteWorkflow,
        "FlyteLaunchPlan": _FlyteLaunchPlan,
        "FlyteBranchNode": _FlyteBranchNode,
    }

    node = MagicMock()
    workflow = _FlyteWorkflow()
    node.flyte_entity = workflow

    branch_node = MagicMock()
    mock_get_workflow_branch_nodes.return_value = {"n0": branch_node}

    with patch("scheduler.flyte._load_flyte_symbols", return_value=mock_symbols):
        # Act
        branch_nodes = Flyte.get_node_branch_nodes(node=node)

    # Assert
    mock_get_workflow_branch_nodes.assert_called_once_with(workflow=workflow)
    assert branch_nodes == {"n0": branch_node}


def test_get_node_branch_nodes_launch_plan_node_none_workflow() -> None:
    # Arrange
    class _FlyteWorkflow:
        pass

    class _FlyteLaunchPlan:
        pass

    class _FlyteBranchNode:
        pass

    mock_symbols = {
        "FlyteWorkflow": _FlyteWorkflow,
        "FlyteLaunchPlan": _FlyteLaunchPlan,
        "FlyteBranchNode": _FlyteBranchNode,
    }

    node = MagicMock()
    launch_plan = _FlyteLaunchPlan()
    launch_plan.flyte_workflow = None  # type: ignore[attr-defined]
    node.flyte_entity = launch_plan

    with patch("scheduler.flyte._load_flyte_symbols", return_value=mock_symbols):
        # Act
        branch_nodes = Flyte.get_node_branch_nodes(node=node)

    # Assert
    assert branch_nodes == {}


@patch("scheduler.flyte.Flyte.get_workflow_branch_nodes")
def test_get_node_branch_nodes_launch_plan_node_workflow(
    mock_get_workflow_branch_nodes,
) -> None:
    # Arrange
    class _FlyteWorkflow:
        pass

    class _FlyteLaunchPlan:
        pass

    class _FlyteBranchNode:
        pass

    mock_symbols = {
        "FlyteWorkflow": _FlyteWorkflow,
        "FlyteLaunchPlan": _FlyteLaunchPlan,
        "FlyteBranchNode": _FlyteBranchNode,
    }

    node = MagicMock()
    launch_plan = _FlyteLaunchPlan()
    workflow = _FlyteWorkflow()
    launch_plan.flyte_workflow = workflow  # type: ignore[attr-defined]
    node.flyte_entity = launch_plan

    branch_node = MagicMock()
    mock_get_workflow_branch_nodes.return_value = {"n0": branch_node}

    with patch("scheduler.flyte._load_flyte_symbols", return_value=mock_symbols):
        # Act
        branch_nodes = Flyte.get_node_branch_nodes(node=node)

    # Assert
    mock_get_workflow_branch_nodes.assert_called_once_with(workflow=workflow)
    assert branch_nodes == {"n0": branch_node}


def test_get_node_branch_nodes_branch_node() -> None:
    # Arrange
    class _FlyteWorkflow:
        pass

    class _FlyteLaunchPlan:
        pass

    class _FlyteBranchNode:
        pass

    mock_symbols = {
        "FlyteWorkflow": _FlyteWorkflow,
        "FlyteLaunchPlan": _FlyteLaunchPlan,
        "FlyteBranchNode": _FlyteBranchNode,
    }

    flyte_node = MagicMock()
    flyte_node.metadata.name = "condition"

    branch_node_entity = _FlyteBranchNode()

    then_node = MagicMock()
    then_node.metadata.name = "then"
    branch_node_entity.if_else = MagicMock()  # type: ignore[attr-defined]
    branch_node_entity.if_else.case.then_node = then_node
    else_node = MagicMock()
    else_node.metadata.name = "else"
    branch_node_entity.if_else.else_node = else_node

    flyte_node.flyte_entity = branch_node_entity

    original_get_node_branch_nodes = Flyte.get_node_branch_nodes
    with patch("scheduler.flyte.Flyte.get_node_branch_nodes") as mock_get_node_branch_nodes:

        def side_effect(node):
            if node == flyte_node:
                with patch("scheduler.flyte._load_flyte_symbols", return_value=mock_symbols):
                    return original_get_node_branch_nodes(node=node)
            return {}

        mock_get_node_branch_nodes.side_effect = side_effect

        with patch("scheduler.flyte._load_flyte_symbols", return_value=mock_symbols):
            # Act
            branch_nodes = Flyte.get_node_branch_nodes(node=flyte_node)

        # Assert
        mock_get_node_branch_nodes.assert_has_calls(
            [
                call(node=flyte_node),
                call(node=then_node),
                call(node=else_node),
            ],
        )
        assert branch_nodes == {
            "then": flyte_node,
            "else": flyte_node,
        }
