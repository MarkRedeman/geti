# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

"""
Jobs Scheduler Flyte integration
"""

import logging
import os
from typing import TYPE_CHECKING, Any, cast

from model.job import Job
from model.telemetry import Telemetry
from scheduler.execution_type import ExecutionType

from geti_types import Session, Singleton

PROJECT = os.environ.get("FLYTE_PROJECT", "impt-jobs")
DOMAIN = os.environ.get("FLYTE_DOMAIN", "production")
DEPLOYMENT_MODE = os.environ.get("DEPLOYMENT_MODE", "").lower()

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from flytekit.remote import FlyteLaunchPlan, FlyteNode, FlyteTask, FlyteWorkflow, FlyteWorkflowExecution

_FLYTE_SYMBOLS: dict[str, Any] | None = None


def _load_flyte_symbols() -> dict[str, Any]:
    global _FLYTE_SYMBOLS
    if _FLYTE_SYMBOLS is not None:
        return _FLYTE_SYMBOLS

    try:
        from flytekit import Annotations, Labels
        from flytekit.configuration import Config
        from flytekit.exceptions.user import FlyteEntityNotExistException
        from flytekit.models.filters import ValueIn
        from flytekit.remote import (
            FlyteLaunchPlan,
            FlyteNode,
            FlyteRemote,
            FlyteTask,
            FlyteWorkflow,
            FlyteWorkflowExecution,
        )
        from flytekit.remote.entities import FlyteBranchNode
        from flytekit.tools.translator import Options
    except Exception as err:  # pragma: no cover - safety net for broken runtime env
        raise RuntimeError("Flyte runtime dependencies are unavailable") from err

    _FLYTE_SYMBOLS = {
        "Annotations": Annotations,
        "Labels": Labels,
        "Config": Config,
        "FlyteEntityNotExistException": FlyteEntityNotExistException,
        "ValueIn": ValueIn,
        "FlyteLaunchPlan": FlyteLaunchPlan,
        "FlyteNode": FlyteNode,
        "FlyteRemote": FlyteRemote,
        "FlyteTask": FlyteTask,
        "FlyteWorkflow": FlyteWorkflow,
        "FlyteWorkflowExecution": FlyteWorkflowExecution,
        "FlyteBranchNode": FlyteBranchNode,
        "Options": Options,
    }
    return _FLYTE_SYMBOLS


class FlyteUnavailableInComposeError(RuntimeError):
    """Raised when Flyte/Kubernetes-backed execution is requested in compose mode."""


def ensure_flyte_available(operation: str) -> None:
    if DEPLOYMENT_MODE != "compose":
        return
    message = f"Feature unavailable in compose mode: {operation}. This path currently requires Kubernetes/Flyte."
    logger.error(message)
    raise FlyteUnavailableInComposeError(message)


class FlyteClient(metaclass=Singleton):
    """
    Flyte client
    Extends and initializes a Flyte remote instance with endpoint URL from FLYTE_URL environment variable
    Default Flyte project is "impt-jobs".
    Default Flyte domain is "development".
    """

    def __init__(self) -> None:
        ensure_flyte_available(operation="scheduler.flyte_client_init")
        symbols = _load_flyte_symbols()
        endpoint = os.environ.get("FLYTE_URL", "localhost:30003")

        config = symbols["Config"].for_endpoint(endpoint=endpoint, insecure=True)
        self.client = symbols["FlyteRemote"](config=config, default_project=PROJECT, default_domain=DOMAIN)

    def __getattr__(self, attr: str):  # noqa: ANN201
        return getattr(self.client, attr)


class Flyte(metaclass=Singleton):
    """
    Flyte service
    Contains all required methods to start and cancel workflow executions
    """

    def __init__(self) -> None:
        self.client = FlyteClient()

    def fetch_workflow(self, workflow_name: str, workflow_version: str) -> "FlyteWorkflow | None":
        """
        Returns Flyte workflow by it's name and version.

        :param workflow_name: Flyte workflow name
        :param workflow_version: Flyte workflow version
        :return: Flyte workflow object
        """
        try:
            return self.client.fetch_workflow(name=workflow_name, version=workflow_version)
        except Exception as err:
            if isinstance(err, _load_flyte_symbols()["FlyteEntityNotExistException"]):
                return None
            raise
        return None

    def start_workflow_execution(  # noqa: PLR0913
        self,
        workspace_id: str,
        job: Job,
        project_id: str | None,
        execution_type: ExecutionType,
        execution_name: str,
        workflow: "FlyteWorkflow",
        payload: dict,
        telemetry: Telemetry,
        session: Session,
    ) -> "FlyteWorkflowExecution":
        symbols = _load_flyte_symbols()
        labels = symbols["Labels"]
        annotations = symbols["Annotations"]
        options = symbols["Options"]

        session_dict = dict(session.as_tuple())
        metadata = {
            "workspace_id": workspace_id,
            "job_id": job.id,
            "execution_type": execution_type.value,
            "opentelemetry_context": telemetry.context,
            "report_resources_consumption": str(job.cost is not None).lower(),
            "organization_id": session_dict["organization_id"],
        }
        if project_id is not None:
            metadata["project_id"] = project_id

        metadata_labels = labels(metadata)
        metadata_extended = {
            "job_type": job.type,
            "job_name": job.job_name,
            "job_author": str(job.author),
            "job_start_time": job.start_time.isoformat() if job.start_time else "null",
        }
        metadata_extended.update(metadata)
        metadata_annotations = annotations(metadata_extended)

        return self.client.execute_remote_wf(
            entity=workflow,
            execution_name=execution_name,
            wait=False,
            inputs=payload,
            options=options(labels=metadata_labels, annotations=metadata_annotations),
        )

    @staticmethod
    def get_execution_type(execution: "FlyteWorkflowExecution") -> ExecutionType:
        """
        Returns the type of execution: MAIN or REVERT
        :param execution: Flyte workflow execution instance
        :return: ExecutionType execution type
        """
        annotations = execution.spec.annotations.values
        return ExecutionType(annotations["execution_type"])

    @staticmethod
    def get_execution_workspace_id(execution: "FlyteWorkflowExecution") -> str:
        """
        Returns the workspace execution belongs to
        :param execution: Flyte workflow execution instance
        :return: str workspace ID
        """
        annotations = execution.spec.annotations.values
        return annotations["workspace_id"]

    @staticmethod
    def get_execution_organization_id(execution: "FlyteWorkflowExecution") -> str:
        """
        Returns the organization execution belongs to
        :param execution: Flyte workflow execution instance
        :return: str organization ID
        """
        annotations = execution.spec.annotations.values
        return annotations["organization_id"]

    @staticmethod
    def get_execution_job_id(execution: "FlyteWorkflowExecution") -> str:
        """
        Returns the job execution belongs to
        :param execution: Flyte workflow execution instance
        :return: str job ID
        """
        annotations = execution.spec.annotations.values
        return annotations["job_id"]

    def fetch_workflow_execution(self, execution_name: str) -> "FlyteWorkflowExecution | None":
        """
        Fetches Flyte workflow execution by name.
        :param execution_name: Execution name
        :return: Flyte workflow execution object or None if it's not found
        """
        try:
            return self.client.fetch_execution(name=execution_name)
        except Exception as err:
            if isinstance(err, _load_flyte_symbols()["FlyteEntityNotExistException"]):
                return None
            raise

    def list_workflow_executions(self, execution_names: list[str]) -> list["FlyteWorkflowExecution"]:
        """
        Fetches Flyte workflow executions by names.
        :param execution_names: Execution names
        :return: Flyte workflow executions list
        """
        logger.debug(f"Getting workflows executions list with names {execution_names}")
        if len(execution_names) == 0:
            return []
        symbols = _load_flyte_symbols()
        (executions_list, _) = self.client.client.list_executions_paginated(
            project=PROJECT,
            domain=DOMAIN,
            filters=[symbols["ValueIn"](key="execution_name", values=execution_names)],
        )
        return [symbols["FlyteWorkflowExecution"].promote_from_model(ex) for ex in executions_list]

    def fetch_task(self, name: str, version: str) -> "FlyteTask | None":
        """
        Fetches Flyte task by name and version.
        :param name: Task name
        :param version: Task version
        :return: Flyte task object or None if it's not found
        """
        try:
            return self.client.fetch_task(project=PROJECT, domain=DOMAIN, name=name, version=version)
        except Exception as err:
            if isinstance(err, _load_flyte_symbols()["FlyteEntityNotExistException"]):
                return None
            raise

    def cancel_workflow_execution(self, execution: "FlyteWorkflowExecution") -> None:
        """
        Cancels Flyte workflow execution.

        :param execution: workflow execution
        """
        self.client.terminate(execution=execution, cause="Canceling execution")

    @staticmethod
    def get_workflow_branch_nodes(workflow: "FlyteWorkflow") -> dict[str, "FlyteNode"]:
        """
        Returns a dict with all branch nodes in a workflow (and all nested sub-workflows and branches).
        Dict key is a node ID (i.e. n6-0-n6-n0-0-n0) which is being used in Flyte, dict value is a branch node itself.
        :param workflow: workflow to traverse
        :return Dict[str, FlyteNode]: branch nodes dict
        """
        result = {}
        for node in workflow.flyte_nodes:
            result.update(Flyte.get_node_branch_nodes(node=node))
        return result

    @staticmethod
    def get_node_branch_nodes(node: "FlyteNode") -> dict[str, "FlyteNode"]:
        """
        Returns a dict with all branch nodes in a node (and all nested sub-workflows and branches).
        Dict key is a node ID (i.e. n6-0-n6-n0-0-n0) which is being used in Flyte, dict value is a branch node itself.
        :param node: node to traverse
        :return Dict[str, FlyteNode]: branch nodes dict
        """
        symbols = _load_flyte_symbols()
        flyte_workflow = symbols["FlyteWorkflow"]
        flyte_launch_plan = symbols["FlyteLaunchPlan"]
        flyte_branch_node = symbols["FlyteBranchNode"]

        if isinstance(node.flyte_entity, flyte_workflow):
            # Sub-workflow node, need to process sub-workflow to fetch its nodes
            workflow = node.flyte_entity
            return Flyte.get_workflow_branch_nodes(workflow=workflow)

        if isinstance(node.flyte_entity, flyte_launch_plan):
            # Launch plan reference node, need to process Launch plan workflow to fetch its nodes
            launch_plan = node.flyte_entity
            return (
                Flyte.get_workflow_branch_nodes(workflow=launch_plan.flyte_workflow)
                if launch_plan.flyte_workflow is not None
                else {}
            )

        if isinstance(node.flyte_entity, flyte_branch_node):
            # Branch node (conditional), need to process further both branches nodes
            branch_node = node.flyte_entity
            result = {}

            # "then" branch
            case_node = cast("FlyteNode", branch_node.if_else.case.then_node)
            result[case_node.metadata.name] = node
            result.update(Flyte.get_node_branch_nodes(node=case_node))

            # "else" branch
            else_node = cast("FlyteNode", branch_node.if_else.else_node)
            result[else_node.metadata.name] = node
            result.update(Flyte.get_node_branch_nodes(node=else_node))

            return result

        return {}
