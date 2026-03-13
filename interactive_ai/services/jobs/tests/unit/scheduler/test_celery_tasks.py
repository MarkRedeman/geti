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

    with pytest.raises(RuntimeError, match="TRAINER_RUNTIME_IMAGE"):
        celery_tasks._run_train_trainer_container(payload={"project_id": "project-1"})  # noqa: SLF001


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

    with pytest.raises(RuntimeError, match="TRAINER_RUNTIME_IMAGE"):
        celery_tasks._run_optimize_trainer_container(payload={"project_id": "project-1"})  # noqa: SLF001
