# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

"""
Local (Docker) executor for compose-mode deployments.

In compose mode Flyte/Kubernetes is not available. This module provides a
LocalExecutor that:

  1. Launches each job workload as a ``docker run`` subprocess.
  2. Maintains an in-process registry mapping execution_name → metadata so
     that the existing Kafka-handler and gRPC-update paths can resolve
     job/workspace/org IDs without a live Flyte connection.
  3. Publishes synthetic ``flyte_event`` Kafka messages on state transitions
     (RUNNING, SUCCEEDED, FAILED/ABORTED) so the existing ProgressHandler
     state-machine transitions are reused unchanged.

Design notes
------------
* Each execution_name is ``ex-<job_id>`` (main) or ``ex-<job_id>-revert``.
* The Docker image and entrypoint to use come from env vars:
    JOB_<TYPE>_DOCKER_IMAGE   – image tag, e.g. "geti/jobs-train:latest"
    JOB_<TYPE>_DOCKER_CMD     – optional JSON-encoded command override
* The container is run with ``--rm`` so it cleans up after itself.
* An internal background thread polls ``docker inspect`` to detect completion
  and publishes the appropriate Kafka event.
* Cancellation sends ``docker stop <container_id>``.

Future migration to Celery
--------------------------
Replace ``_launch_container`` with a Celery ``apply_async`` call, replace
``_monitor_loop`` with a Celery result poller or signal handler, and keep
the rest (registry + Kafka events) unchanged.
"""

import json
import logging
import os
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from geti_kafka_tools import publish_event
from geti_types import CTX_SESSION_VAR, ID, RequestSource, Singleton, make_session, session_context

from scheduler.flyte import ExecutionType
from scheduler.celery_tasks import run_job_execution

logger = logging.getLogger(__name__)

# Polling interval (seconds) between docker-inspect calls for a running container
_POLL_INTERVAL = float(os.environ.get("LOCAL_EXECUTOR_POLL_INTERVAL", "2"))
_SIM_DURATION_SEC = float(os.environ.get("LOCAL_EXECUTOR_SIM_DURATION_SEC", "2"))

# Header name used by Flyte cloud events
_CE_TYPE_HEADER = "ce_type"
_WORKFLOW_EXECUTION_EVENT_REQUEST = "com.flyte.resource.flyteidl.admin.WorkflowExecutionEventRequest"

# Kafka topic consumed by ProgressHandler
_FLYTE_EVENT_TOPIC = "flyte_event"

PHASE_RUNNING = "RUNNING"
PHASE_SUCCEEDED = "SUCCEEDED"
PHASE_FAILED = "FAILED"
PHASE_ABORTED = "ABORTED"


@dataclass
class _ExecutionRecord:
    """Metadata stored per execution while the container is alive (or finished)."""

    execution_name: str
    job_id: str
    workspace_id: str
    organization_id: str
    execution_type: ExecutionType
    container_id: str | None = None
    finished: bool = False
    # Session tuple list for Kafka header propagation
    session_headers: list[tuple[str, bytes]] = field(default_factory=list)
    cancelled: bool = False
    running_published: bool = False


class LocalExecutor(metaclass=Singleton):
    """
    Thin Docker-based executor for compose-mode.

    All public methods mirror the ``Flyte`` singleton's interface where needed
    so call-sites can dispatch with a simple ``if is_compose_mode()`` guard.
    """

    def __init__(self) -> None:
        # execution_name → _ExecutionRecord
        self._registry: dict[str, _ExecutionRecord] = {}
        self._lock = threading.Lock()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name="local-executor-monitor",
            daemon=True,
        )
        self._stop_event = threading.Event()
        self._monitor_thread.start()
        logger.info("LocalExecutor started (compose mode)")

    # ------------------------------------------------------------------
    # Public API – scheduling
    # ------------------------------------------------------------------

    def start_execution(  # noqa: PLR0913
        self,
        execution_name: str,
        job_id: str,
        workspace_id: str,
        organization_id: str,
        execution_type: ExecutionType,
        job_type: str,
        payload: dict[str, Any],
        session_headers: list[tuple[str, bytes]],
    ) -> str:
        """
        Launch a Docker container for *execution_name* and return the container ID.

        If an execution with the same name is already registered (idempotent
        re-schedule), return the existing container_id.

        :param execution_name: unique execution identifier (``ex-<job_id>`` etc.)
        :param job_id: owning job ID
        :param workspace_id: owning workspace ID
        :param organization_id: owning organisation ID
        :param execution_type: MAIN or REVERT
        :param job_type: e.g. "train", "optimize"
        :param payload: job payload dict (passed as JSON env var to container)
        :param session_headers: session header bytes for Kafka propagation
        :return: Docker container ID (short or full)
        """
        with self._lock:
            existing = self._registry.get(execution_name)
            if existing is not None and not existing.finished:
                logger.info(
                    f"[LocalExecutor] Reusing already running execution {execution_name} "
                    f"(container_id={existing.container_id})"
                )
                return existing.container_id or execution_name

        record = _ExecutionRecord(
            execution_name=execution_name,
            job_id=job_id,
            workspace_id=workspace_id,
            organization_id=organization_id,
            execution_type=execution_type,
            session_headers=session_headers,
        )

        if self._run_mode == "simulate":
            container_id = f"sim-{execution_name}"
            self._start_simulated_execution(record=record)
        elif self._run_mode == "celery":
            result = self._start_celery_execution(execution_name=execution_name, payload=payload, record=record)
            container_id = f"celery-{result.id}"
        else:
            container_id = self._launch_container(
                execution_name=execution_name,
                job_type=job_type,
                payload=payload,
                record=record,
            )
        record.container_id = container_id

        with self._lock:
            self._registry[execution_name] = record

        logger.info(
            f"[LocalExecutor] Launched execution {execution_name} (job_id={job_id}, container_id={container_id})"
        )
        return container_id

    @property
    def _run_mode(self) -> str:
        return os.environ.get("LOCAL_EXECUTOR_MODE", "simulate").lower()

    def _start_simulated_execution(self, record: _ExecutionRecord) -> None:
        def _simulate() -> None:
            self._publish_workflow_event(record, phase=PHASE_RUNNING)
            time.sleep(_SIM_DURATION_SEC)
            with self._lock:
                if record.cancelled:
                    return
                record.finished = True
            self._publish_workflow_event(record, phase=PHASE_SUCCEEDED)

        threading.Thread(target=_simulate, name=f"local-exec-sim-{record.execution_name}", daemon=True).start()

    def _start_celery_execution(self, execution_name: str, payload: dict[str, Any], record: _ExecutionRecord):  # noqa: ANN001
        self._publish_workflow_event(record, phase=PHASE_RUNNING)
        task_payload = dict(payload)
        task_payload.setdefault("sim_duration_sec", _SIM_DURATION_SEC)
        async_result = run_job_execution.apply_async(args=[execution_name, task_payload])

        def _watch_result() -> None:
            try:
                async_result.get(timeout=max(60, int(_SIM_DURATION_SEC * 10)))
                with self._lock:
                    if record.cancelled:
                        return
                    record.finished = True
                self._publish_workflow_event(record, phase=PHASE_SUCCEEDED)
            except Exception:
                logger.exception(f"[LocalExecutor] Celery execution failed: {execution_name}")
                with self._lock:
                    if record.cancelled:
                        return
                    record.finished = True
                self._publish_workflow_event(record, phase=PHASE_FAILED)

        threading.Thread(target=_watch_result, name=f"local-exec-celery-{execution_name}", daemon=True).start()
        return async_result

    # ------------------------------------------------------------------
    # Public API – cancellation
    # ------------------------------------------------------------------

    def cancel_execution(self, execution_name: str) -> None:
        """
        Stop the Docker container associated with *execution_name*.

        :param execution_name: execution to cancel
        """
        with self._lock:
            record = self._registry.get(execution_name)

        if record is None or record.container_id is None:
            logger.warning(f"[LocalExecutor] cancel_execution called for unknown/unstarted execution {execution_name}")
            return

        if record.finished:
            logger.info(f"[LocalExecutor] Execution {execution_name} already finished, nothing to cancel")
            return

        if self._run_mode in {"simulate", "celery"}:
            with self._lock:
                record.cancelled = True
                record.finished = True
            self._publish_workflow_event(record, phase=PHASE_ABORTED)
            return

        logger.info(f"[LocalExecutor] Stopping container {record.container_id} for execution {execution_name}")
        try:
            subprocess.run(  # noqa: S603
                ["docker", "stop", record.container_id],
                check=False,
                capture_output=True,
                timeout=30,
            )
        except Exception:
            logger.exception(f"[LocalExecutor] Failed to stop container {record.container_id}")

    # ------------------------------------------------------------------
    # Public API – registry lookup (used instead of Flyte().fetch_workflow_execution)
    # ------------------------------------------------------------------

    def get_execution_metadata(self, execution_name: str) -> _ExecutionRecord | None:
        """
        Return the stored metadata for *execution_name*, or None if unknown.

        This is the compose-mode replacement for
        ``Flyte().fetch_workflow_execution(execution_name)``.
        """
        with self._lock:
            return self._registry.get(execution_name)

    # ------------------------------------------------------------------
    # Internal – Docker launch
    # ------------------------------------------------------------------

    def _launch_container(
        self,
        execution_name: str,
        job_type: str,
        payload: dict[str, Any],
        record: _ExecutionRecord,
    ) -> str:
        """
        Run ``docker run -d …`` and return the container ID.

        Environment variables passed to the container:
          JOB_PAYLOAD_JSON   – full payload serialised as JSON
          JOB_ID             – job ID
          EXECUTION_NAME     – execution name
          EXECUTION_TYPE     – MAIN or REVERT

        The Docker image is read from ``JOB_<TYPE>_DOCKER_IMAGE``.
        An optional command override is read from ``JOB_<TYPE>_DOCKER_CMD``
        (JSON-encoded list, e.g. ``'["python", "-m", "train"]'``).
        """
        image_env_var = f"JOB_{job_type.upper()}_DOCKER_IMAGE"
        image = os.environ.get(image_env_var)
        if not image:
            raise RuntimeError(
                f"[LocalExecutor] Docker image not configured for job type '{job_type}'. Set env var {image_env_var}."
            )

        cmd_env_var = f"JOB_{job_type.upper()}_DOCKER_CMD"
        cmd_override_raw = os.environ.get(cmd_env_var)
        cmd_override: list[str] = json.loads(cmd_override_raw) if cmd_override_raw else []

        docker_cmd = [
            "docker",
            "run",
            "--rm",
            "--detach",
            "--name",
            execution_name,
            # Pass job context
            "--env",
            f"JOB_ID={record.job_id}",
            "--env",
            f"EXECUTION_NAME={execution_name}",
            "--env",
            f"EXECUTION_TYPE={record.execution_type.value}",
            "--env",
            f"JOB_PAYLOAD_JSON={json.dumps(payload)}",
        ]

        # Forward all host env vars whose names start with known prefixes so
        # the workflow container can connect to MongoDB, S3, etc.
        _FORWARD_PREFIXES = (
            "MONGODB_",
            "S3_",
            "MINIO_",
            "KAFKA_",
            "REDIS_",
            "FEATURE_FLAGS_",
            "GETI_",
            "IAI_",
            "OBJECT_STORAGE_",
        )
        for key, val in os.environ.items():
            if any(key.startswith(p) for p in _FORWARD_PREFIXES):
                docker_cmd += ["--env", f"{key}={val}"]

        docker_cmd.append(image)
        docker_cmd.extend(cmd_override)

        logger.debug(f"[LocalExecutor] docker run command: {docker_cmd}")

        result = subprocess.run(  # noqa: S603
            docker_cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        container_id = result.stdout.strip()
        return container_id

    # ------------------------------------------------------------------
    # Internal – monitor loop
    # ------------------------------------------------------------------

    def _monitor_loop(self) -> None:
        """Background thread: polls running containers, publishes Kafka events on completion."""
        while not self._stop_event.is_set():
            try:
                if self._run_mode != "simulate":
                    self._poll_all()
            except Exception:
                logger.exception("[LocalExecutor] Unexpected error in monitor loop")
            time.sleep(_POLL_INTERVAL)

    def _poll_all(self) -> None:
        """Check every tracked, unfinished execution once."""
        with self._lock:
            records = [r for r in self._registry.values() if not r.finished and r.container_id]

        for record in records:
            try:
                self._poll_one(record)
            except Exception:
                logger.exception(f"[LocalExecutor] Error polling execution {record.execution_name}")

    def _poll_one(self, record: _ExecutionRecord) -> None:
        """Inspect a single container and publish Kafka event if state changed."""
        container_id = record.container_id
        if container_id is None:
            return

        result = subprocess.run(  # noqa: S603
            [
                "docker",
                "inspect",
                "--format",
                "{{.State.Status}} {{.State.ExitCode}}",
                container_id,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            # Container not found (already removed); treat as failed
            logger.warning(
                f"[LocalExecutor] Container {record.container_id} not found, "
                f"treating execution {record.execution_name} as failed"
            )
            self._mark_finished(record)
            self._publish_workflow_event(record, phase=PHASE_FAILED)
            return

        parts = result.stdout.strip().split()
        if not parts:
            return

        status = parts[0]
        exit_code = int(parts[1]) if len(parts) > 1 else -1

        if status == "running":
            # If we haven't published RUNNING yet, do it now
            if not record.running_published:
                record.running_published = True
                self._publish_workflow_event(record, phase=PHASE_RUNNING)
        elif status in ("exited", "dead"):
            self._mark_finished(record)
            phase = PHASE_SUCCEEDED if exit_code == 0 else PHASE_FAILED
            self._publish_workflow_event(record, phase=phase)
        elif status in ("removing", "created"):
            pass  # transient state, wait next poll
        # "paused" etc. — ignore

    def _mark_finished(self, record: _ExecutionRecord) -> None:
        with self._lock:
            record.finished = True

    # ------------------------------------------------------------------
    # Internal – Kafka event publishing
    # ------------------------------------------------------------------

    def _publish_workflow_event(self, record: _ExecutionRecord, phase: str) -> None:
        """
        Publish a synthetic ``flyte_event`` Kafka message that mimics a Flyte
        WorkflowExecutionEventRequest so the existing ProgressHandler picks it up.

        The message body follows the shape that ProgressHandler.on_flyte_event()
        and handle_workflow_event() expect:

            {
                "event": {
                    "executionId": {"name": "<execution_name>"},
                    "phase": "<RUNNING|SUCCEEDED|FAILED|ABORTED>"
                }
            }

        The ``ce_type`` Kafka header is set to WORKFLOW_EXECUTION_EVENT_REQUEST.
        """
        logger.info(f"[LocalExecutor] Publishing workflow event: execution={record.execution_name}, phase={phase}")
        body = {
            "event": {
                "executionId": {"name": record.execution_name},
                "phase": phase,
            }
        }
        try:
            # Build a session context so publish_event headers_getter works
            session = make_session(
                organization_id=ID(record.organization_id),
                workspace_id=ID(record.workspace_id),
                source=RequestSource.INTERNAL,
            )
            with session_context(session=session):
                publish_event(
                    topic=_FLYTE_EVENT_TOPIC,
                    body=body,
                    key=record.execution_name.encode(),
                    headers_getter=lambda: (
                        [(_CE_TYPE_HEADER, _WORKFLOW_EXECUTION_EVENT_REQUEST.encode())]
                        + list(CTX_SESSION_VAR.get().as_list_bytes())
                    ),
                )
        except Exception:
            logger.exception(f"[LocalExecutor] Failed to publish Kafka event for {record.execution_name}")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def stop(self) -> None:
        """Signal the monitor thread to stop (called on scheduler shutdown)."""
        self._stop_event.set()
