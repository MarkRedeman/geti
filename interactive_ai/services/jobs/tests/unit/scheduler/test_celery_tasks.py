# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import json

import pytest

from scheduler import celery_tasks


def _run_train_job(payload: dict):
    return celery_tasks.run_job_execution.run("execution-1", "train", payload)


def _run_optimize_job(payload: dict):
    return celery_tasks.run_job_execution.run("execution-1", "optimize_pot", payload)


def test_run_job_execution_train_staged_flow_with_finalize(monkeypatch):
    calls: list[str] = []
    prep = {"train_data_json": "{}", "train_output_model_ids_json": "{}"}

    monkeypatch.setattr(
        celery_tasks,
        "_run_import_export_in_container",
        lambda **_: f"noise\nTRAIN_PREP_RESULT={json.dumps(prep)}\n",
    )
    monkeypatch.setattr(
        celery_tasks,
        "_run_train_trainer_container",
        lambda **_: calls.append("trainer"),
    )
    monkeypatch.setattr(celery_tasks, "_should_run_train_finalize", lambda **_: True)
    monkeypatch.setattr(
        celery_tasks,
        "_run_train_finalize_stage",
        lambda **_: calls.append("finalize"),
    )
    monkeypatch.setattr(
        celery_tasks,
        "_run_train_evaluate_stage",
        lambda **_: calls.append("evaluate"),
    )

    response = _run_train_job(payload={"project_id": "project-1"})

    assert response == {"execution_name": "execution-1", "status": "succeeded"}
    assert calls == ["trainer", "finalize", "evaluate"]


def test_run_job_execution_train_skips_finalize_when_not_needed(monkeypatch):
    calls: list[str] = []
    prep = {"train_data_json": "{}", "train_output_model_ids_json": "{}"}

    monkeypatch.setattr(
        celery_tasks,
        "_run_import_export_in_container",
        lambda **_: f"TRAIN_PREP_RESULT={json.dumps(prep)}",
    )
    monkeypatch.setattr(
        celery_tasks,
        "_run_train_trainer_container",
        lambda **_: calls.append("trainer"),
    )
    monkeypatch.setattr(celery_tasks, "_should_run_train_finalize", lambda **_: False)
    monkeypatch.setattr(
        celery_tasks,
        "_run_train_finalize_stage",
        lambda **_: calls.append("finalize"),
    )
    monkeypatch.setattr(
        celery_tasks,
        "_run_train_evaluate_stage",
        lambda **_: calls.append("evaluate"),
    )

    _run_train_job(payload={"project_id": "project-1"})

    assert calls == ["trainer", "evaluate"]


def test_run_job_execution_train_raises_when_prep_result_missing(monkeypatch):
    monkeypatch.setattr(celery_tasks, "_run_import_export_in_container", lambda **_: "no prep marker here")
    trainer_called = {"called": False}
    monkeypatch.setattr(
        celery_tasks,
        "_run_train_trainer_container",
        lambda **_: trainer_called.__setitem__("called", True),
    )

    with pytest.raises(RuntimeError, match="TRAIN_PREP_RESULT"):
        _run_train_job(payload={"project_id": "project-1"})

    assert trainer_called["called"] is False


def test_run_train_trainer_container_requires_runtime_image(monkeypatch):
    monkeypatch.delenv("TRAINER_RUNTIME_IMAGE", raising=False)

    with pytest.raises(RuntimeError, match="Missing trainer runtime image"):
        celery_tasks._run_train_trainer_container(  # noqa: SLF001
            payload={"project_id": "project-1"}, execution_name="exec-1"
        )


def test_run_job_execution_optimize_staged_flow(monkeypatch):
    calls: list[str] = []
    prep = {
        "trainer_ctx_json": "{}",
        "dataset_storage_id": "dataset-storage-id",
        "model_id": "model-id",
    }

    monkeypatch.setattr(
        celery_tasks,
        "_run_import_export_in_container",
        lambda **_: f"noise\nOPTIMIZE_PREP_RESULT={json.dumps(prep)}\n",
    )
    monkeypatch.setattr(
        celery_tasks,
        "_run_optimize_trainer_container",
        lambda **_: calls.append("trainer"),
    )
    monkeypatch.setattr(
        celery_tasks,
        "_run_optimize_finalize_stage",
        lambda **_: calls.append("finalize"),
    )
    monkeypatch.setattr(
        celery_tasks,
        "_run_optimize_evaluate_stage",
        lambda **_: calls.append("evaluate"),
    )

    response = _run_optimize_job(payload={"project_id": "project-1"})

    assert response == {"execution_name": "execution-1", "status": "succeeded"}
    assert calls == ["trainer", "finalize", "evaluate"]


def test_run_job_execution_optimize_raises_when_prep_result_missing(monkeypatch):
    monkeypatch.setattr(celery_tasks, "_run_import_export_in_container", lambda **_: "no prep marker here")
    trainer_called = {"called": False}
    monkeypatch.setattr(
        celery_tasks,
        "_run_optimize_trainer_container",
        lambda **_: trainer_called.__setitem__("called", True),
    )

    with pytest.raises(RuntimeError, match="OPTIMIZE_PREP_RESULT"):
        _run_optimize_job(payload={"project_id": "project-1"})

    assert trainer_called["called"] is False


def test_run_optimize_trainer_container_requires_runtime_image(monkeypatch):
    monkeypatch.delenv("TRAINER_RUNTIME_IMAGE", raising=False)

    with pytest.raises(RuntimeError, match="Missing trainer runtime image"):
        celery_tasks._run_optimize_trainer_container(payload={"project_id": "project-1"})  # noqa: SLF001


def test_run_job_execution_unsupported_type_fails_fast():
    with pytest.raises(RuntimeError, match="Unsupported compose Celery job type"):
        celery_tasks.run_job_execution.run("execution-1", "unknown_job_type", {})


# ---------------------------------------------------------------------------
# Helpers: fail-fast on missing payload keys
# ---------------------------------------------------------------------------


def test_session_org_id_raises_when_missing_from_payload():
    with pytest.raises(KeyError, match="organization_id"):
        celery_tasks._session_org_id({})  # noqa: SLF001


def test_session_workspace_id_raises_when_missing_from_payload():
    with pytest.raises(KeyError, match="workspace_id"):
        celery_tasks._session_workspace_id({})  # noqa: SLF001


def test_job_metadata_id_raises_when_missing_from_payload():
    with pytest.raises(KeyError, match="job_id"):
        celery_tasks._job_metadata_id({})  # noqa: SLF001


def test_job_metadata_name_raises_when_missing_from_payload():
    with pytest.raises(KeyError, match="job_name"):
        celery_tasks._job_metadata_name({})  # noqa: SLF001


def test_job_metadata_author_raises_when_missing_from_payload():
    with pytest.raises(KeyError, match="author"):
        celery_tasks._job_metadata_author({})  # noqa: SLF001


def test_job_metadata_start_time_raises_when_missing_from_payload():
    with pytest.raises(KeyError, match="start_time"):
        celery_tasks._job_metadata_start_time({})  # noqa: SLF001


def test_session_org_id_returns_payload_value(monkeypatch):
    monkeypatch.setenv("SESSION_ORGANIZATION_ID", "scheduler-stub-id")
    assert celery_tasks._session_org_id({"organization_id": "real-org-id"}) == "real-org-id"  # noqa: SLF001


def test_job_metadata_id_returns_payload_value(monkeypatch):
    monkeypatch.setenv("JOB_METADATA_ID", "scheduler-stub-id")
    assert celery_tasks._job_metadata_id({"job_id": "real-job-id"}) == "real-job-id"  # noqa: SLF001


# ---------------------------------------------------------------------------
# SESSION_ / JOB_METADATA_ must not appear in any forward-prefix list
# (guards against re-introducing the scheduler-stub-leak bug)
# ---------------------------------------------------------------------------


def _captured_docker_args(monkeypatch, stage_fn, *args, **kwargs) -> list[str]:
    """Run *stage_fn* with a fake subprocess and return the docker cmd args."""
    captured: list[list[str]] = []

    def fake_run(cmd, **_):  # noqa: ANN001, ANN202
        captured.append(cmd)

    monkeypatch.setattr(celery_tasks.subprocess, "run", fake_run)
    stage_fn(*args, **kwargs)
    assert captured, "subprocess.run was never called"
    return captured[0]


_REAL_PAYLOAD = {
    "organization_id": "real-org",
    "workspace_id": "real-ws",
    "project_id": "real-proj",
    "job_id": "real-job",
    "job_name": "real-job-name",
    "author": "real-author",
    "start_time": "2025-01-01T00:00:00",
}

def _assert_no_stub_leakage(cmd: list[str], monkeypatch) -> None:
    """
    Verify that name-only env-forward entries (i.e. '--env KEY' without '=value')
    do not exist for SESSION_ORGANIZATION_ID, SESSION_WORKSPACE_ID, or JOB_METADATA_ID.

    The correct form is always '--env KEY=real-value'.
    """
    for i, arg in enumerate(cmd):
        if arg == "--env" and i + 1 < len(cmd):
            token = cmd[i + 1]
            # A name-only forward has no '=' — that would forward the scheduler stub value
            assert token not in (
                "SESSION_ORGANIZATION_ID",
                "SESSION_WORKSPACE_ID",
                "JOB_METADATA_ID",
                "JOB_METADATA_TYPE",
                "JOB_METADATA_NAME",
                "JOB_METADATA_AUTHOR",
                "JOB_METADATA_START_TIME",
            ), f"Name-only env forward found in docker cmd: '--env {token}'"


def test_run_optimize_finalize_stage_no_stub_leakage(monkeypatch):
    monkeypatch.setenv("OPTIMIZE_WORKFLOW_IMAGE", "optimize-img:latest")
    monkeypatch.setenv("SESSION_ORGANIZATION_ID", "stub-org")
    monkeypatch.setenv("JOB_METADATA_ID", "stub-job")
    cmd = _captured_docker_args(
        monkeypatch,
        celery_tasks._run_optimize_finalize_stage,  # noqa: SLF001
        payload=_REAL_PAYLOAD,
        prep_result={},
    )
    _assert_no_stub_leakage(cmd, monkeypatch)
    # Correct explicit values must be present
    assert "--env" in cmd
    assert f"SESSION_ORGANIZATION_ID={_REAL_PAYLOAD['organization_id']}" in cmd
    assert f"JOB_METADATA_ID={_REAL_PAYLOAD['job_id']}" in cmd
    assert f"JOB_METADATA_NAME={_REAL_PAYLOAD['job_name']}" in cmd
    assert f"JOB_METADATA_AUTHOR={_REAL_PAYLOAD['author']}" in cmd
    assert f"JOB_METADATA_START_TIME={_REAL_PAYLOAD['start_time']}" in cmd


def test_run_optimize_evaluate_stage_no_stub_leakage(monkeypatch):
    monkeypatch.setenv("OPTIMIZE_WORKFLOW_IMAGE", "optimize-img:latest")
    monkeypatch.setenv("SESSION_ORGANIZATION_ID", "stub-org")
    monkeypatch.setenv("JOB_METADATA_ID", "stub-job")
    cmd = _captured_docker_args(
        monkeypatch,
        celery_tasks._run_optimize_evaluate_stage,  # noqa: SLF001
        payload=_REAL_PAYLOAD,
        prep_result={},
    )
    _assert_no_stub_leakage(cmd, monkeypatch)
    assert f"SESSION_ORGANIZATION_ID={_REAL_PAYLOAD['organization_id']}" in cmd
    assert f"JOB_METADATA_ID={_REAL_PAYLOAD['job_id']}" in cmd
    assert f"JOB_METADATA_NAME={_REAL_PAYLOAD['job_name']}" in cmd
    assert f"JOB_METADATA_AUTHOR={_REAL_PAYLOAD['author']}" in cmd
    assert f"JOB_METADATA_START_TIME={_REAL_PAYLOAD['start_time']}" in cmd


def test_run_train_finalize_stage_no_stub_leakage(monkeypatch):
    monkeypatch.setenv("TRAIN_WORKFLOW_IMAGE", "train-img:latest")
    monkeypatch.setenv("SESSION_ORGANIZATION_ID", "stub-org")
    monkeypatch.setenv("JOB_METADATA_ID", "stub-job")
    cmd = _captured_docker_args(
        monkeypatch,
        celery_tasks._run_train_finalize_stage,  # noqa: SLF001
        payload=_REAL_PAYLOAD,
        prep_result={},
        execution_name="exec-1",
    )
    _assert_no_stub_leakage(cmd, monkeypatch)
    assert f"SESSION_ORGANIZATION_ID={_REAL_PAYLOAD['organization_id']}" in cmd
    assert f"JOB_METADATA_ID={_REAL_PAYLOAD['job_id']}" in cmd
    assert f"JOB_METADATA_NAME={_REAL_PAYLOAD['job_name']}" in cmd
    assert f"JOB_METADATA_AUTHOR={_REAL_PAYLOAD['author']}" in cmd
    assert f"JOB_METADATA_START_TIME={_REAL_PAYLOAD['start_time']}" in cmd


def test_run_train_evaluate_stage_no_stub_leakage(monkeypatch):
    monkeypatch.setenv("TRAIN_WORKFLOW_IMAGE", "train-img:latest")
    monkeypatch.setenv("SESSION_ORGANIZATION_ID", "stub-org")
    monkeypatch.setenv("JOB_METADATA_ID", "stub-job")
    cmd = _captured_docker_args(
        monkeypatch,
        celery_tasks._run_train_evaluate_stage,  # noqa: SLF001
        payload=_REAL_PAYLOAD,
        prep_result={},
        execution_name="exec-1",
    )
    _assert_no_stub_leakage(cmd, monkeypatch)
    assert f"SESSION_ORGANIZATION_ID={_REAL_PAYLOAD['organization_id']}" in cmd
    assert f"JOB_METADATA_ID={_REAL_PAYLOAD['job_id']}" in cmd
    assert f"JOB_METADATA_NAME={_REAL_PAYLOAD['job_name']}" in cmd
    assert f"JOB_METADATA_AUTHOR={_REAL_PAYLOAD['author']}" in cmd
    assert f"JOB_METADATA_START_TIME={_REAL_PAYLOAD['start_time']}" in cmd


def test_run_import_export_in_container_no_stub_leakage(monkeypatch):
    """
    Verifies that _run_import_export_in_container passes SESSION_* and
    JOB_METADATA_* as explicit KEY=value entries (not name-only forwards).
    """
    monkeypatch.setenv("OPTIMIZE_WORKFLOW_IMAGE", "optimize-img:latest")
    monkeypatch.setenv("SESSION_ORGANIZATION_ID", "stub-org")
    monkeypatch.setenv("JOB_METADATA_ID", "stub-job")
    captured: list[list[str]] = []

    class FakeResult:
        stdout = ""

    def fake_run(cmd, **_):  # noqa: ANN001, ANN202
        captured.append(cmd)
        return FakeResult()

    monkeypatch.setattr(celery_tasks.subprocess, "run", fake_run)
    celery_tasks._run_import_export_in_container(  # noqa: SLF001
        job_type="optimize_pot", payload=_REAL_PAYLOAD
    )
    assert captured
    cmd = captured[0]
    _assert_no_stub_leakage(cmd, monkeypatch)
    assert f"SESSION_ORGANIZATION_ID={_REAL_PAYLOAD['organization_id']}" in cmd
    assert f"JOB_METADATA_ID={_REAL_PAYLOAD['job_id']}" in cmd
    assert f"JOB_METADATA_NAME={_REAL_PAYLOAD['job_name']}" in cmd
    assert f"JOB_METADATA_AUTHOR={_REAL_PAYLOAD['author']}" in cmd
    assert f"JOB_METADATA_START_TIME={_REAL_PAYLOAD['start_time']}" in cmd
