# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

"""
Module for job execution events Kafka handler
"""

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from model.job import Job, JobConsumedResource, JobCost
from scheduler.context import job_context
from scheduler.execution_type import ExecutionType
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
    """KafkaHandler for job execution cloud events"""

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

        # In compose mode look up execution metadata from the local registry
        # instead of fetching it from a remote orchestrator.
        record = LocalExecutor().get_execution_metadata(execution_name)
        if record is None:
            logger.error(f"[compose mode] Unable to find execution {execution_name} in local registry")
            return

        organization_id = ID(record.organization_id)
        workspace_id = ID(record.workspace_id)
        job_id = record.job_id
        execution_type = record.execution_type
        execution = None  # no remote execution object in compose mode

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
                    # Compose mode: execution_type already resolved from local registry
                    ProgressHandler.handle_workflow_event_by_type(
                        event=event,
                        execution=execution,
                        execution_type=execution_type,
                        job=job,
                    )

                elif event_type == TASK_EXECUTION_EVENT_REQUEST:
                    # task-level events are not used in compose mode
                    return

                elif event_type == NODE_EXECUTION_EVENT_REQUEST:
                    # node/branch events are not used in compose mode
                    return

    @staticmethod
    def get_execution_name(event_type: str, event: dict) -> str:
        if event_type == WORKFLOW_EXECUTION_EVENT_REQUEST:
            return event["executionId"]["name"]
        if event_type == TASK_EXECUTION_EVENT_REQUEST:
            return event["parentNodeExecutionId"]["executionId"]["name"]
        return event["id"]["executionId"]["name"]

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
        the local path (where ``execution`` is None and metadata comes from the
        LocalExecutor registry) and any future remote execution path.
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
            logger.critical(f"Revert execution failed: job_id={job.id}")

        if job.cancellation_info.is_cancelled:
            # If job has been cancelled by user, setting final CANCELLED state
            logger.info(f"Job changes applied: job_id={job.id}, state=CANCELLED")
            StateMachine().set_and_publish_cancelled_state(job_id=job.id)
        else:
            # If job has not been cancelled by user, setting final FAILED state
            logger.info(f"Job changes applied: job_id={job.id}, state=FAILED")
            StateMachine().set_and_publish_failed_state(job_id=job.id)

    @staticmethod
    @setup_session_kafka
    @unified_tracing
    def on_job_step_details(raw_message: KafkaRawMessage) -> None:
        value: dict = raw_message.value

        if "execution_id" not in value:
            logger.error("Missing execution ID")
            return

        execution_name = value["execution_id"]

        record = LocalExecutor().get_execution_metadata(execution_name)
        if record is None:
            logger.error(f"[compose mode] Unable to find execution {execution_name} in local registry")
            return
        job_id = record.job_id

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

        record = LocalExecutor().get_execution_metadata(execution_name)
        if record is None:
            logger.error(f"[compose mode] Unable to find execution {execution_name} in local registry")
            return
        job_id = record.job_id

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
