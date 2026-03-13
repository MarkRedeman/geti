# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import json
import sys
import types

import pytest

from scheduler import workflow_runner


@pytest.fixture(autouse=True)
def clear_workflow_env(monkeypatch):
    keys = [
        "WORKFLOW_PAYLOAD_JSON",
        "WORKFLOW_JOB_STAGE",
        "TRAIN_PREP_RESULT_JSON",
        "OPTIMIZE_PREP_RESULT_JSON",
        "WORKFLOW_EVALUATE_STUB",
        "WORKFLOW_EVALUATE_STUB_EVALUATE",
        "WORKFLOW_EVALUATE_STUB_REGISTER",
        "WORKFLOW_EVALUATE_STUB_ACCEPTANCE",
        "WORKFLOW_EVALUATE_STUB_TASK_INFER",
        "WORKFLOW_EVALUATE_STUB_PIPELINE_INFER",
        "WORKFLOW_OPTIMIZE_STUB_EVALUATE",
        "SESSION_ORGANIZATION_ID",
        "JOB_METADATA_ID",
    ]
    for key in keys:
        monkeypatch.delenv(key, raising=False)


def _install_train_stubs(monkeypatch, call_log):
    class DummyTrainData:
        @classmethod
        def from_json(cls, _value):
            return cls()

        def get_model_storage_identifier(self):
            return "storage-id"

    class DummyTrainCtx:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.train_data = kwargs["train_data"]
            self.dataset_id = kwargs["dataset_id"]
            self.train_output_model_ids = kwargs["train_output_model_ids"]

    class DummyTrainOutputModelIds:
        def __init__(self):
            self.base = "base-model-id"
            self.mo_with_xai = "optimized-model-id"

        @classmethod
        def from_json(cls, _value):
            return cls()

    class DummyModel:
        model_status = "SUCCESS"

    class DummyModelRepo:
        def __init__(self, _identifier):
            pass

        def get_by_id(self, _id):
            return DummyModel()

    def fake_evaluate_and_infer(**kwargs):
        call_log.append(("evaluate_and_infer", kwargs))

    job = types.ModuleType("job")
    job_tasks = types.ModuleType("job.tasks")
    job_prepare = types.ModuleType("job.tasks.prepare_and_train")
    job_eval = types.ModuleType("job.tasks.evaluate_and_infer")
    job_utils = types.ModuleType("job.utils")
    job.tasks = job_tasks
    job.tasks.prepare_and_train = job_prepare
    job.tasks.evaluate_and_infer = job_eval
    job.utils = job_utils

    jobs_common = types.ModuleType("jobs_common")
    jobs_common_jobs = types.ModuleType("jobs_common.jobs")
    jobs_common_helpers = types.ModuleType("jobs_common.jobs.helpers")
    jobs_common.jobs = jobs_common_jobs
    jobs_common.jobs.helpers = jobs_common_helpers

    extras = types.ModuleType("jobs_common_extras")
    extras_experiments = types.ModuleType("jobs_common_extras.experiments")
    extras_utils = types.ModuleType("jobs_common_extras.experiments.utils")
    extras.experiments = extras_experiments
    extras.experiments.utils = extras_utils

    eval_module = types.SimpleNamespace(
        evaluate_and_infer=fake_evaluate_and_infer,
        evaluate=lambda *_, **__: (True, "subset-id"),
        finalize_train=lambda *_, **__: None,
        register_models=lambda *_, **__: None,
        post_model_acceptance=lambda *_, **__: None,
        task_infer_on_unannotated=lambda *_, **__: None,
        pipeline_infer_on_unannotated=lambda *_, **__: None,
    )
    job_eval.evaluate_and_infer = eval_module

    module_map = {
        "job": job,
        "job.tasks": job_tasks,
        "job.tasks.prepare_and_train": job_prepare,
        "job.tasks.evaluate_and_infer": job_eval,
        "job.utils": job_utils,
        "jobs_common": jobs_common,
        "jobs_common.jobs": jobs_common_jobs,
        "jobs_common.jobs.helpers": jobs_common_helpers,
        "jobs_common_extras": extras,
        "jobs_common_extras.experiments": extras_experiments,
        "jobs_common_extras.experiments.utils": extras_utils,
        "geti_types": types.SimpleNamespace(ID=lambda x: x),
        "iai_core.entities.model": types.SimpleNamespace(
            ModelStatus=types.SimpleNamespace(TRAINED_NO_STATS="TRAINED_NO_STATS", SUCCESS="SUCCESS")
        ),
        "iai_core.repos": types.SimpleNamespace(ModelRepo=DummyModelRepo),
        "jobs_common.jobs.helpers.project_helpers": types.SimpleNamespace(lock_project=lambda **_: None),
        "job.tasks.prepare_and_train.create_task_train_dataset": types.SimpleNamespace(
            create_task_train_dataset=lambda **_: None
        ),
        "job.tasks.prepare_and_train.get_train_data": types.SimpleNamespace(get_train_data=lambda **_: None),
        "job.tasks.prepare_and_train.train_helpers": types.SimpleNamespace(
            finalize_train=lambda **_: None,
            prepare_train=lambda **_: None,
        ),
        "job.tasks.evaluate_and_infer.evaluate_and_infer": eval_module,
        "job.utils.train_workflow_data": types.SimpleNamespace(
            TrainWorkflowData=DummyTrainData,
            TrainWorkflowDataForFlyteTaskTrainer=DummyTrainCtx,
        ),
        "jobs_common_extras.experiments.utils.train_output_models": types.SimpleNamespace(
            TrainOutputModelIds=DummyTrainOutputModelIds
        ),
    }

    for key, value in module_map.items():
        monkeypatch.setitem(sys.modules, key, value)


def test_run_train_evaluate_stage_with_destubbed_task_and_pipeline(monkeypatch):
    call_log = []
    _install_train_stubs(monkeypatch, call_log)

    payload = {
        "project_id": "project-id",
        "task_id": "task-id",
        "from_scratch": False,
        "should_activate_model": True,
        "infer_on_pipeline": True,
    }
    prep = {
        "train_data_json": "{}",
        "dataset_id": "dataset-id",
        "train_output_model_ids_json": "{}",
        "organization_id": "org-id",
        "job_id": "job-id",
    }
    monkeypatch.setenv("WORKFLOW_JOB_STAGE", "evaluate")
    monkeypatch.setenv("WORKFLOW_PAYLOAD_JSON", json.dumps(payload))
    monkeypatch.setenv("TRAIN_PREP_RESULT_JSON", json.dumps(prep))
    monkeypatch.setenv("WORKFLOW_EVALUATE_STUB_EVALUATE", "false")
    monkeypatch.setenv("WORKFLOW_EVALUATE_STUB_REGISTER", "false")
    monkeypatch.setenv("WORKFLOW_EVALUATE_STUB_ACCEPTANCE", "false")
    monkeypatch.setenv("WORKFLOW_EVALUATE_STUB_TASK_INFER", "false")
    monkeypatch.setenv("WORKFLOW_EVALUATE_STUB_PIPELINE_INFER", "false")

    workflow_runner._run_job_type("train", payload)  # noqa: SLF001

    assert len(call_log) == 1
    assert call_log[0][0] == "evaluate_and_infer"
    assert call_log[0][1]["infer_on_pipeline"] is True


def test_run_optimize_evaluate_stage_destubbed(monkeypatch):
    called = {}

    class DummyCtx:
        def __init__(self):
            self.project_id = "project-id"
            self.model_storage_id = "storage-id"
            self.model_to_optimize_id = "optimized-id"

        @classmethod
        def from_json(cls, _value):
            return cls()

    def fake_evaluate(**kwargs):
        called.update(kwargs)

    job = types.ModuleType("job")
    job_tasks = types.ModuleType("job.tasks")
    job.tasks = job_tasks

    module_map = {
        "job": job,
        "job.tasks": job_tasks,
        "job.models": types.SimpleNamespace(OptimizationTrainerContext=DummyCtx),
        "job.tasks.constants": types.SimpleNamespace(NULL_COMPILED_DATASET_SHARDS_ID="null-shards"),
        "job.tasks.evaluation_task": types.SimpleNamespace(_evaluate_optimized_model=fake_evaluate),
        "job.tasks.helpers": types.SimpleNamespace(
            finalize_optimize=lambda **_: None,
            prepare_optimize=lambda **_: None,
        ),
    }
    for key, value in module_map.items():
        monkeypatch.setitem(sys.modules, key, value)

    payload = {
        "project_id": "project-id",
        "dataset_storage_id": "dataset-storage-id",
        "model_storage_id": "storage-id",
        "model_id": "model-id",
        "min_annotation_size": 1,
        "max_annotation_size": 10,
        "min_number_of_annotations": 2,
        "max_number_of_annotations": 20,
    }
    prep = {
        "trainer_ctx_json": "{}",
        "dataset_storage_id": "dataset-storage-id",
        "model_id": "model-id",
    }
    monkeypatch.setenv("WORKFLOW_JOB_STAGE", "evaluate")
    monkeypatch.setenv("OPTIMIZE_PREP_RESULT_JSON", json.dumps(prep))
    monkeypatch.setenv("WORKFLOW_OPTIMIZE_STUB_EVALUATE", "false")

    workflow_runner._run_job_type("optimize_pot", payload)  # noqa: SLF001

    assert called["project_id"] == "project-id"
    assert called["dataset_storage_id"] == "dataset-storage-id"
    assert called["model_storage_id"] == "storage-id"
    assert called["model_id"] == "model-id"
    assert called["optimized_model_id"] == "optimized-id"
