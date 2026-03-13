# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

"""
Module for Flyte events Kafka handler
"""

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from model.job import Job, JobConsumedResource, JobCost
from model.job_state import JobTaskState
from scheduler.context import job_context
from scheduler.flyte import ExecutionType, Flyte, ensure_flyte_available, is_compose_mode
from scheduler.jobs_templates import JobsTemplates
from scheduler.local_executor import LocalExecutor
from scheduler.state_machine import StateMachine

from geti_kafka_tools import BaseKafkaHandler, KafkaRawMessage, TopicSubscription, publish_event
from geti_telemetry_tools import unified_tracing
from geti_types import CTX_SESSION_VAR, ID, RequestSource, Singleton, make_session, session_context
from grpc_interfaces.credit_system.client import CreditSystemClient
from iai_core.session.session_propagation import setup_session_kafka
from iai_core.utils.time_utils import now

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from flytekit.remote import FlyteWorkflowExecution

WORKFLOW_EXECUTION_EVENT_REQUEST = "com.flyte.resource.flyteidl.admin.WorkflowExecutionEventRequest"
TASK_EXECUTION_EVENT_REQUEST = "com.flyte.resource.flyteidl.admin.TaskExecutionEventRequest"
NODE_EXECUTION_EVENT_REQUEST = "com.flyte.resource.flyteidl.admin.NodeExecutionEventRequest"

PHASE_SUCCEEDED = "SUCCEEDED"
PHASE_QUEUED = "QUEUED"
PHASE_RUNNING = "RUNNING"
PHASE_DYNAMIC_RUNNING = "DYNAMIC_RUNNING"
PHASE_FAILED = "FAILED"
PHASE_ABORTED = "ABORTED"


class ProgressHandler(BaseKafkaHandler, metaclass=Singleton):
    """KafkaHandler for Flyte cloud events"""

    def __init__(self) -> None:
        super().__init__(group_id="job_scheduler")

    @property
    def topics_subscriptions(self) -> list[TopicSubscription]:
        return [
            TopicSubscription(topic="flyte_event", callback=self.on_flyte_event),
            TopicSubscription(topic="job_step_details", callback=self.on_job_step_details),
            TopicSubscription(topic="job_update", callback=self.on_job_update),
            TopicSubscription(topic="project_deletions", callback=self.on_project_deleted),
            TopicSubscription(topic="on_job_failed", callback=self.on_job_failed),
            TopicSubscription(topic="on_job_cancelled", callback=self.on_job_cancelled),
            TopicSubscription(topic="on_job_finished", callback=self.on_job_finished),
        ]

    @staticmethod
    @unified_tracing
    def on_flyte_event(raw_message: KafkaRawMessage) -> None:
        event = raw_message.value["event"] if raw_message.value is not None and "event" in raw_message.value else None
        if event is None:
            return
        event_type = next(
            (h[1].decode("ascii") for h in raw_message.headers if len(h) > 1 and h[0] == "ce_type"),
            None,
        )
        if event_type not in (
            WORKFLOW_EXECUTION_EVENT_REQUEST,
            NODE_EXECUTION_EVENT_REQUEST,
            TASK_EXECUTION_EVENT_REQUEST,
        ):
            return

        logger.info(f"Event type: {event_type}")

        execution_name = ProgressHandler.get_execution_name(event_type=event_type, event=event)
        if execution_name is None:
            logger.error("Unable to determine execution_name")
            return

        if is_compose_mode():
            # In compose mode look up execution metadata from the local registry
            # instead of fetching it from Flyte.
            record = LocalExecutor().get_execution_metadata(execution_name)
            if record is None:
                logger.error(f"[compose mode] Unable to find execution {execution_name} in local registry")
                return

            organization_id = ID(record.organization_id)
            workspace_id = ID(record.workspace_id)
            job_id = record.job_id
            execution_type = record.execution_type
            execution = None  # no Flyte object in compose mode
        else:
            ensure_flyte_available(operation="jobs.on_flyte_event")
            execution = Flyte().fetch_workflow_execution(execution_name=execution_name)
            if execution is None:
                logger.error(f"Unable to fetch execution {execution_name}")
                return

            organization_id = ID(Flyte.get_execution_organization_id(execution))
            workspace_id = ID(Flyte.get_execution_workspace_id(execution))
            job_id = Flyte.get_execution_job_id(execution)
            execution_type = Flyte.get_execution_type(execution)

        with session_context(
            session=make_session(
                organization_id=organization_id,
                workspace_id=workspace_id,
                source=RequestSource.INTERNAL,
            )
        ):
            job = StateMachine().get_by_id(job_id=ID(job_id))
            if job is None:
                logger.error(f"Unable to find job by it's ID {job_id}")
                return

            with job_context(job=job, span_name="on_flyte_event"):
                if event_type == WORKFLOW_EXECUTION_EVENT_REQUEST:
                    if execution is not None:
                        # Flyte mode: use handle_workflow_event (resolves execution_type internally)
                        ProgressHandler.handle_workflow_event(event=event, execution=execution, job=job)
                    else:
                        # Compose mode: execution_type already resolved from local registry
                        ProgressHandler.handle_workflow_event_by_type(
                            event=event,
                            execution=execution,
                            execution_type=execution_type,
                            job=job,
                        )

                elif event_type == TASK_EXECUTION_EVENT_REQUEST:
                    if execution is not None:
                        ProgressHandler.handle_task_event(event=event, execution=execution, job=job)
                    # task-level events are not published in compose mode (no Flyte task graph)

                elif event_type == NODE_EXECUTION_EVENT_REQUEST:
                    if execution is not None:
                        ProgressHandler.handle_node_event(event=event, execution=execution, job=job)
                    # node/branch events are not published in compose mode

    @staticmethod
    def get_execution_name(event_type: str, event: dict) -> str:
        if event_type == WORKFLOW_EXECUTION_EVENT_REQUEST:
            return event["executionId"]["name"]
        if event_type == TASK_EXECUTION_EVENT_REQUEST:
            return event["parentNodeExecutionId"]["executionId"]["name"]
        return event["id"]["executionId"]["name"]

    @staticmethod
    def handle_workflow_event(event: dict, execution: "FlyteWorkflowExecution", job: Job) -> None:
        logger.info(f"Handling workflow event {event}")

        if "phase" not in event:
            logger.error("Unable to obtain execution phase from event")
            return

        execution_type = Flyte.get_execution_type(execution)
        ProgressHandler.handle_workflow_event_by_type(
            event=event,
            execution=execution,
            execution_type=execution_type,
            job=job,
        )

    @staticmethod
    def handle_workflow_event_by_type(
        event: dict,
        execution: "FlyteWorkflowExecution | None",
        execution_type: ExecutionType,
        job: Job,
    ) -> None:
        """
        Handle a workflow-level phase change.

        Accepts a pre-resolved *execution_type* so it can be called both from
        the Flyte path (where ``execution`` is a real FlyteWorkflowExecution) and
        from the compose/local path (where ``execution`` is None and metadata comes
        from the LocalExecutor registry).
        """
        logger.info(f"Handling workflow event {event}")

        if "phase" not in event:
            logger.error("Unable to obtain execution phase from event")
            return

        if execution_type == ExecutionType.MAIN:
            ProgressHandler.handle_main_workflow_event(job=job, phase=event["phase"])
        elif execution_type == ExecutionType.REVERT:
            ProgressHandler.handle_revert_workflow_event(job=job, phase=event["phase"])

    @staticmethod
    def handle_main_workflow_event(job: Job, phase: str) -> None:
        if phase == PHASE_RUNNING:
            # Main execution is running, setting job status to RUNNING
            logger.info(f"Job changes applied: job_id={job.id}, state=RUNNING")
            StateMachine().set_running_state(job_id=job.id)
        elif phase == PHASE_SUCCEEDED:
            logger.info(f"Job changes applied: job_id={job.id}, state=FINISHED")
            StateMachine().set_and_publish_finished_state(job_id=job.id)

        elif phase in (PHASE_FAILED, PHASE_ABORTED):
            logger.info(f"Job changes applied: job_id={job.id}, state=READY_FOR_REVERT")
            StateMachine().set_ready_for_revert_state(job_id=job.id)

    @staticmethod
    def handle_revert_workflow_event(job: Job, phase: str) -> None:
        if phase == PHASE_RUNNING:
            logger.info(f"Job changes applied: job_id={job.id}, state=READY_FOR_REVERT")
            StateMachine().set_revert_running_state(job_id=job.id)

        if phase not in (PHASE_SUCCEEDED, PHASE_FAILED):
            return

        if phase == PHASE_FAILED:
            logger.critical(f"Revert workflow execution failed: job_id={job.id}")

        if job.cancellation_info.is_cancelled:
            # If job has been cancelled by user, setting final CANCELLED state
            logger.info(f"Job changes applied: job_id={job.id}, state=CANCELLED")
            StateMachine().set_and_publish_cancelled_state(job_id=job.id)
        else:
            # If job has not been cancelled by user, setting final FAILED state
            logger.info(f"Job changes applied: job_id={job.id}, state=FAILED")
            StateMachine().set_and_publish_failed_state(job_id=job.id)

    @staticmethod
    def handle_task_event(event: dict, execution: "FlyteWorkflowExecution", job: Job) -> None:
        logger.info(f"Handling task event {event}")

        phase_state_map = {
            PHASE_RUNNING: JobTaskState.RUNNING,
            PHASE_DYNAMIC_RUNNING: JobTaskState.RUNNING,  # Map PHASE_DYNAMIC_RUNNING to JobTaskState.RUNNING too
            PHASE_SUCCEEDED: JobTaskState.FINISHED,
            PHASE_FAILED: JobTaskState.FAILED,
            PHASE_ABORTED: JobTaskState.CANCELLED,
        }

        phase = event.get("phase")
        if phase not in phase_state_map:
            # Do not handle states other than RUNNING, FINISHED, FAILED OR CANCELLED
            return

        state = phase_state_map.get(phase)
        error_code = event.get("error", {}).get("code", None)
        error_message = event.get("error", {}).get("message", None)
        oom = (error_code is not None and "OOMKilled" in error_code) or (
            error_message is not None and "OOM-killed" in error_message
        )
        message = (
            (
                "The job failed due to insufficient memory. "
                "This may happen if the chosen model is too large for the available hardware, "
                "or if there is an internal bug in the training pipeline. Please try again with a more "
                "lightweight model if possible: if the problem persists, please report the issue."
            )
            if state == JobTaskState.FAILED and oom
            else None
        )

        try:
            task_id = event["taskId"]["name"]
        except KeyError:
            logger.warning("Unable to obtain task ID from event")
            return

        task = next((step for step in list(job.step_details) if step.task_id == task_id), None)
        if state == JobTaskState.FAILED and message is None and task is not None and task.message is None:
            message = (
                "An issue was encountered while initializing this workload. Please retry or reach out to "
                "us on GitHub if problem persists."
            )

        execution_type = Flyte.get_execution_type(execution)
        if execution_type == ExecutionType.REVERT:
            # Do not handle revert tasks progress
            return

        steps = JobsTemplates().get_job_steps(job_type=job.type)
        step = next((step for step in steps if step.task_id == task_id), None)
        if message is None and step is not None:
            if state == JobTaskState.RUNNING and step.start_message is not None:
                message = step.start_message
            elif state == JobTaskState.FINISHED and step.finish_message is not None:
                message = step.finish_message
            elif state == JobTaskState.FAILED and step.failure_message is not None:
                message = f"{step.failure_message} (ID: {job.id})"

        logger.info(f"Job changes applied: job_id={job.id}, task_id={task_id}, state={state}, message={message}")
        StateMachine().set_step_details(
            job_id=job.id,
            task_id=task_id,
            state=state,
            start_time=now() if state == JobTaskState.RUNNING else None,
            end_time=now() if state != JobTaskState.RUNNING else None,
            message=message,
            progress=100.0 if state == JobTaskState.FINISHED else None,
        )

    @staticmethod
    def handle_node_event(event: dict, execution: "FlyteWorkflowExecution", job: Job) -> None:
        logger.info(f"Handling node event {event}")

        phase = event.get("phase")
        if phase != PHASE_QUEUED:
            # Do not handle states other than QUEUED
            return

        try:
            node_name = event["nodeName"]
        except KeyError:
            # Skip, if there is no information about parent node or node name
            logger.debug("Unable to process event data, skipping")
            return

        execution_type = Flyte.get_execution_type(execution)
        if execution_type == ExecutionType.REVERT:
            # Do not handle revert tasks progress
            return

        workflow = execution.flyte_workflow

        branch_nodes = Flyte.get_workflow_branch_nodes(workflow=workflow)
        condition_node = branch_nodes.get(node_name)

        if condition_node is None:
            logger.warning("Unable to calculate branch node")
            return

        condition = condition_node.metadata.name

        steps = JobsTemplates().get_job_steps(job_type=job.type)
        for step in steps:
            branch = step.get_branch(condition)

            if branch is not None and branch.branch != node_name:
                skip_message = branch.skip_message
                logger.info(
                    f"Job changes applied: job_id={job.id}, task_id={step.task_id}, "
                    f"state={JobTaskState.SKIPPED.value}, message={skip_message}"
                )
                StateMachine().set_step_details(
                    job_id=job.id,
                    task_id=step.task_id,
                    state=JobTaskState.SKIPPED,
                    message=skip_message,
                )

    @staticmethod
    @setup_session_kafka
    @unified_tracing
    def on_job_step_details(raw_message: KafkaRawMessage) -> None:
        value: dict = raw_message.value

        if "execution_id" not in value:
            logger.error("Missing execution ID")
            return

        execution_name = value["execution_id"]

        if is_compose_mode():
            record = LocalExecutor().get_execution_metadata(execution_name)
            if record is None:
                logger.error(f"[compose mode] Unable to find execution {execution_name} in local registry")
                return
            job_id = record.job_id
        else:
            ensure_flyte_available(operation="jobs.on_job_step_details")
            execution = Flyte().fetch_workflow_execution(execution_name=execution_name)
            if execution is None:
                logger.error(f"Unable to fetch execution {execution_name}")
                return
            job_id = Flyte.get_execution_job_id(execution)

        job = StateMachine().get_by_id(job_id=ID(job_id))
        if job is None:
            logger.error(f"Unable to find job by it's ID {job_id}")
            return
        if job.cancellation_info.is_cancelled:
            return

        progress: float | None = value.get("progress")
        message: str | None = value.get("message")
        warning: str | None = value.get("warning")

        StateMachine().set_step_details(
            job_id=ID(job_id),
            state=None,
            task_id=value["task_id"],
            progress=progress,
            message=message,
            warning=warning,
        )

    @staticmethod
    @setup_session_kafka
    @unified_tracing
    def on_job_update(raw_message: KafkaRawMessage) -> None:
        value: dict = raw_message.value

        if "execution_id" not in value:
            logger.error("Missing execution ID")
            return

        execution_name = value["execution_id"]

        if is_compose_mode():
            record = LocalExecutor().get_execution_metadata(execution_name)
            if record is None:
                logger.error(f"[compose mode] Unable to find execution {execution_name} in local registry")
                return
            job_id = record.job_id
        else:
            ensure_flyte_available(operation="jobs.on_job_update")
            execution = Flyte().fetch_workflow_execution(execution_name=execution_name)
            if execution is None:
                logger.error(f"Unable to fetch execution {execution_name}")
                return
            job_id = Flyte.get_execution_job_id(execution)

        if "metadata" in value:
            StateMachine().update_metadata(job_id=ID(job_id), metadata=value["metadata"])

        if "cost" in value and "consumed" in value["cost"]:
            consumed_resources = [
                JobConsumedResource(
                    amount=consumed["amount"],
                    unit=consumed["unit"],
                    consuming_date=datetime.fromisoformat(consumed["consuming_date"]),
                    service=consumed["service"],
                )
                for consumed in value["cost"]["consumed"]
            ]
            StateMachine().update_cost_consumed(job_id=ID(job_id), consumed_resources=consumed_resources)

        if "gpu" in value and value["gpu"] == "release":
            StateMachine().set_gpu_state_released(job_id=ID(job_id))

    @staticmethod
    @setup_session_kafka
    @unified_tracing
    def on_project_deleted(raw_message: KafkaRawMessage) -> None:
        value: dict = raw_message.value
        project_id = ID(value["project_id"])

        logger.info(f"Project {project_id} is deleted, cancelling and removing project jobs")

        jobs_ids = StateMachine().find_jobs_ids_by_project_id(project_id=project_id)
        logger.info(f"Number of project jobs found: {len(jobs_ids)}")
        for job_id in jobs_ids:
            logger.info(f"Canceling and removing job {job_id}")
            StateMachine().mark_cancelled_and_deleted(job_id=job_id)

    @staticmethod
    @setup_session_kafka
    @unified_tracing
    def on_job_failed(raw_message: KafkaRawMessage) -> None:
        job_id: str = raw_message.key.decode()

        job = StateMachine().get_by_id(job_id=ID(job_id))
        if not job:
            raise ValueError(f"Job {job_id} not found")
        if not job.cost:
            logger.debug(f"Job {job_id} doesn't have cost defined, skipping")
            return

        logger.info(f"Job {job_id} has failed, cancelling credit lease {job.cost.lease_id}")
        with CreditSystemClient(metadata_getter=lambda: ()) as client:
            client.cancel_lease(lease_id=job.cost.lease_id)
        StateMachine().set_cost_reported(job_id=ID(job_id))

    @staticmethod
    def send_metering_event(id: ID, type: str, cost: JobCost, project_id: str | None) -> None:
        body = {
            "service_name": type,
            "lease_id": cost.lease_id,
            "consumption": [{"amount": consumed.amount, "unit": consumed.unit} for consumed in cost.consumed],
            "date": now().timestamp() * 1000,
        }
        if project_id is not None:
            body["project_id"] = project_id
        publish_event(
            topic="credits_lease",
            body=body,
            key=id.encode(),
            headers_getter=lambda: CTX_SESSION_VAR.get().as_list_bytes(),
        )

    @staticmethod
    @setup_session_kafka
    @unified_tracing
    def on_job_cancelled(raw_message: KafkaRawMessage) -> None:
        job_id: str = raw_message.key.decode()
        job = StateMachine().get_by_id(job_id=ID(job_id))
        if not job:
            raise ValueError(f"Job {job_id} not found")
        if not job.cost:
            logger.debug(f"Job {job_id} doesn't have cost defined, skipping")
            return
        if len(job.cost.consumed) == 0:
            logger.debug(f"Job {job_id} doesn't have paid resources consumed, cancelling the lease")
            with CreditSystemClient(metadata_getter=lambda: ()) as client:
                client.cancel_lease(lease_id=job.cost.lease_id)
        else:
            ProgressHandler.send_metering_event(id=job.id, type=job.type, cost=job.cost, project_id=job.project_id)
        StateMachine().set_cost_reported(job_id=ID(job_id))

    @staticmethod
    @setup_session_kafka
    @unified_tracing
    def on_job_finished(raw_message: KafkaRawMessage) -> None:
        job_id: str = raw_message.key.decode()
        job = StateMachine().get_by_id(job_id=ID(job_id))
        if not job:
            raise ValueError(f"Job {job_id} not found")
        if not job.cost:
            logger.debug(f"Job {job_id} doesn't have cost defined, skipping")
            return
        if len(job.cost.consumed) == 0:
            logger.error(
                f"Job {job_id} has cost defined, but no resources has been reported consumed during the execution"
            )
        else:
            ProgressHandler.send_metering_event(id=job.id, type=job.type, cost=job.cost, project_id=job.project_id)
        StateMachine().set_cost_reported(job_id=ID(job_id))
