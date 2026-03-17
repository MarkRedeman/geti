# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import json
import os
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch

_TRAIN_PREP_RESULT_PREFIX = "TRAIN_PREP_RESULT="
_OPTIMIZE_PREP_RESULT_PREFIX = "OPTIMIZE_PREP_RESULT="


def _bool_env(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.lower() == "true"


def _is_train_ready_for_evaluate(train_data, train_output_model_ids) -> bool:  # noqa: ANN001
    from geti_types import ID
    from iai_core.entities.model import ModelStatus
    from iai_core.repos import ModelRepo

    model_repo = ModelRepo(train_data.get_model_storage_identifier())
    base_model = model_repo.get_by_id(ID(train_output_model_ids.base))
    return base_model.model_status in {ModelStatus.TRAINED_NO_STATS, ModelStatus.SUCCESS}


def _load_payload() -> dict:
    return json.loads(os.environ["WORKFLOW_PAYLOAD_JSON"])


def _resolve_compiled_dataset_shards_id_for_optimize(payload: dict) -> str:
    """Resolve compiled dataset shards id for optimize compose flow.

    Mirrors optimize workflow semantics:
    - when enable_optimize_from_dataset_shard=true, create shards from filtered train dataset
    - otherwise use empty sentinel id
    """
    null_compiled_dataset_shards_id = ""
    if not payload.get("enable_optimize_from_dataset_shard", False):
        return null_compiled_dataset_shards_id

    from geti_types import ID
    from iai_core.entities.model_storage import ModelStorageIdentifier
    from iai_core.repos import ModelRepo, ProjectRepo
    from jobs_common.utils.annotation_filter import AnnotationFilter
    from jobs_common_extras.shard_dataset.tasks.shard_dataset import shard_dataset

    project_id = ID(payload["project_id"])
    project = ProjectRepo().get_by_id(project_id)
    model_storage_identifier = ModelStorageIdentifier(
        workspace_id=project.workspace_id,
        project_id=project_id,
        model_storage_id=ID(payload["model_storage_id"]),
    )
    model = ModelRepo(model_storage_identifier).get_by_id(ID(payload["model_id"]))

    filtered_train_dataset = AnnotationFilter.apply_annotation_filters(
        dataset=model.get_train_dataset(),
        min_annotation_size=payload.get("min_annotation_size"),
        max_annotation_size=payload.get("max_annotation_size"),
        min_number_of_annotations=payload.get("min_number_of_annotations"),
        max_number_of_annotations=payload.get("max_number_of_annotations"),
    )

    return shard_dataset(
        project=project,
        label_schema=model.get_label_schema(),
        train_dataset=filtered_train_dataset,
        max_shard_size=payload.get("max_shard_size", 1000),
        num_image_pulling_threads=payload.get("num_image_pulling_threads", 10),
        num_upload_threads=payload.get("num_upload_threads", 2),
    )


def _compose_execution_id() -> str:
    if execution_id := os.environ.get("WORKFLOW_EXECUTION_ID"):
        return execution_id
    if job_id := os.environ.get("JOB_METADATA_ID"):
        return f"ex-{job_id}"
    return "compose-execution"


def _compose_task_id(job_type: str, stage: str | None = None) -> str:
    if job_type == "export_dataset":
        return "job.tasks.export_tasks.export_dataset_task.export_dataset_task"
    if job_type == "prepare_import_to_new_project":
        return "job.tasks.import_tasks.parse_dataset_new_project.parse_dataset_for_import_to_new_project"
    if job_type == "perform_import_to_new_project":
        return "job.tasks.import_tasks.create_project_from_dataset.create_project_from_dataset"
    if job_type == "prepare_import_to_existing_project":
        return "job.tasks.import_tasks.parse_dataset_existing_project.parse_dataset_for_import_to_existing_project"
    if job_type == "perform_import_to_existing_project":
        return "job.tasks.import_tasks.import_dataset_to_project.import_dataset_to_project"
    if job_type == "export_project":
        return "job.tasks.export_project.export_project"
    if job_type == "import_project":
        return "job.tasks.import_project.import_project"
    if job_type == "test":
        return "job.tasks.model_testing.run_model_test"
    if job_type == "train":
        if stage == "evaluate":
            return "job.tasks.evaluate_and_infer.evaluate_and_infer.evaluate_and_infer"
        if stage == "finalize":
            return "train"
        return "job.tasks.prepare_and_train.prepare_data_and_train.prepare_training_data_model_and_start_training"
    if job_type == "optimize_pot":
        if stage == "evaluate":
            return "job.tasks.evaluation_task.evaluate_optimized_model_pot"
        if stage == "finalize":
            return "job.tasks.helpers.finalize_optimize"
        return "job.tasks.optimization_task.shard_dataset_prepare_models_and_start_optimization"
    return f"compose.{job_type}"


def _run_job_type(job_type: str, payload: dict) -> None:
    if job_type == "export_dataset":
        from job.tasks.export_tasks.export_dataset_task import export_dataset_task

        export_dataset_task(
            organization_id=payload["organization_id"],
            project_id=payload["project_id"],
            dataset_storage_id=payload["dataset_storage_id"],
            include_unannotated=payload.get("include_unannotated", False),
            export_format=payload["export_format"],
            save_video_as_images=payload.get("save_video_as_images", False),
        )
        return

    if job_type == "prepare_import_to_new_project":
        from job.tasks.import_tasks.parse_dataset_new_project import parse_dataset_for_import_to_new_project

        parse_dataset_for_import_to_new_project(import_id=payload["import_id"])
        return

    if job_type == "prepare_import_to_existing_project":
        from job.tasks.import_tasks.parse_dataset_existing_project import parse_dataset_for_import_to_existing_project

        parse_dataset_for_import_to_existing_project(import_id=payload["import_id"], project_id=payload["project_id"])
        return

    if job_type == "perform_import_to_new_project":
        from job.tasks.import_tasks.create_project_from_dataset import create_project_from_dataset

        create_project_from_dataset(
            import_id=payload["import_id"],
            name=payload["name"],
            project_type_str=payload["project_type_str"],
            label_names=payload["label_names"],
            color_by_label=payload["color_by_label"],
            keypoint_structure=payload["keypoint_structure"],
            user_id=payload["user_id"],
        )
        return

    if job_type == "perform_import_to_existing_project":
        from job.tasks.import_tasks.import_dataset_to_project import import_dataset_to_project

        label_ids_map = payload.get("label_ids_map", payload.get("labels_map"))
        if label_ids_map is None:
            raise KeyError("label_ids_map")

        import_dataset_to_project(
            project_id=payload["project_id"],
            import_id=payload["import_id"],
            label_ids_map=label_ids_map,
            dataset_storage_id=payload["dataset_storage_id"],
            dataset_name=payload["dataset_name"],
            user_id=payload["user_id"],
        )
        return

    if job_type == "export_project":
        from job.tasks.export_project import export_project

        export_project(project_id=payload["project_id"], include_models=payload.get("include_models", "all"))
        return

    if job_type == "import_project":
        from job.tasks.import_project import import_project

        import_project(
            file_id=payload["file_id"],
            keep_original_dates=payload.get("keep_original_dates", False),
            project_name=payload["project_name"],
            user_id=payload["user_id"],
        )
        return

    if job_type == "test":
        from job.tasks.model_testing import run_model_test

        run_model_test(
            project_id=payload["project_id"],
            model_test_result_id=payload["model_test_result_id"],
            min_annotation_size=payload.get("min_annotation_size"),
            max_annotation_size=payload.get("max_annotation_size"),
            min_number_of_annotations=payload.get("min_number_of_annotations"),
            max_number_of_annotations=payload.get("max_number_of_annotations"),
        )
        return

    if job_type == "train":
        from geti_types import ID
        from jobs_common.tasks.utils.progress import report_progress
        from jobs_common.jobs.helpers.project_helpers import lock_project
        from job.tasks.prepare_and_train.create_task_train_dataset import create_task_train_dataset
        from job.tasks.prepare_and_train.get_train_data import get_train_data
        from job.tasks.prepare_and_train.shard_dataset import shard_dataset_for_train
        from job.tasks.prepare_and_train.train_helpers import finalize_train, prepare_train
        from job.tasks.evaluate_and_infer.evaluate_and_infer import evaluate_and_infer
        from job.utils.train_workflow_data import TrainWorkflowData
        from job.utils.train_workflow_data import TrainWorkflowDataForFlyteTaskTrainer
        from jobs_common_extras.experiments.utils.train_output_models import TrainOutputModelIds

        stage = os.environ.get("WORKFLOW_JOB_STAGE", "prepare")

        if stage == "finalize":
            serialized = os.environ.get("TRAIN_PREP_RESULT_JSON")
            if not serialized:
                raise RuntimeError("TRAIN_PREP_RESULT_JSON is required for train finalize stage")
            prep = json.loads(serialized)
            train_data = TrainWorkflowData.from_json(prep["train_data_json"])
            train_output_model_ids = TrainOutputModelIds.from_json(prep["train_output_model_ids_json"])
            finalize_train(
                train_data=train_data,
                train_output_model_ids=train_output_model_ids,
                retain_training_artifacts=payload.get("retain_training_artifacts", False),
            )
            return

        if stage == "evaluate":
            serialized = os.environ.get("TRAIN_PREP_RESULT_JSON")
            if not serialized:
                raise RuntimeError("TRAIN_PREP_RESULT_JSON is required for train evaluate stage")
            prep = json.loads(serialized)
            train_data = TrainWorkflowData.from_json(prep["train_data_json"])
            train_output_model_ids = TrainOutputModelIds.from_json(prep["train_output_model_ids_json"])
            train_ctx = TrainWorkflowDataForFlyteTaskTrainer(
                train_data=train_data,
                dataset_id=prep["dataset_id"],
                organization_id=os.environ.get("SESSION_ORGANIZATION_ID", prep.get("organization_id", "")),
                job_id=os.environ.get("JOB_METADATA_ID", prep.get("job_id", "")),
                train_output_model_ids=train_output_model_ids,
            )

            if not _is_train_ready_for_evaluate(train_data=train_data, train_output_model_ids=train_output_model_ids):
                raise RuntimeError(
                    "Evaluate stage started before training finalization. "
                    "Base model is not in TRAINED_NO_STATS/SUCCESS state."
                )

            evaluate_patch = (
                patch(
                    "job.tasks.evaluate_and_infer.evaluate_and_infer.evaluate",
                    lambda *a, **k: (True, "compose-train-inference-placeholder"),
                )
                if _bool_env("WORKFLOW_EVALUATE_STUB_EVALUATE", True)
                else nullcontext()
            )
            # finalize_train is already executed in a dedicated preceding stage.
            # Keep evaluate stage idempotent by always no-oping embedded finalize call.
            finalize_patch = patch(
                "job.tasks.evaluate_and_infer.evaluate_and_infer.finalize_train", lambda *a, **k: None
            )
            register_patch = (
                patch("job.tasks.evaluate_and_infer.evaluate_and_infer.register_models", lambda *a, **k: None)
                if _bool_env("WORKFLOW_EVALUATE_STUB_REGISTER", True)
                else nullcontext()
            )
            acceptance_patch = (
                patch("job.tasks.evaluate_and_infer.evaluate_and_infer.post_model_acceptance", lambda *a, **k: None)
                if _bool_env("WORKFLOW_EVALUATE_STUB_ACCEPTANCE", True)
                else nullcontext()
            )
            task_infer_patch = (
                patch("job.tasks.evaluate_and_infer.evaluate_and_infer.task_infer_on_unannotated", lambda *a, **k: None)
                if _bool_env("WORKFLOW_EVALUATE_STUB_TASK_INFER", True)
                else nullcontext()
            )
            pipeline_infer_patch = (
                patch(
                    "job.tasks.evaluate_and_infer.evaluate_and_infer.pipeline_infer_on_unannotated",
                    lambda *a, **k: None,
                )
                if _bool_env("WORKFLOW_EVALUATE_STUB_PIPELINE_INFER", True)
                else nullcontext()
            )

            with (
                finalize_patch,
                evaluate_patch,
                register_patch,
                acceptance_patch,
                task_infer_patch,
                pipeline_infer_patch,
            ):
                evaluate_and_infer(
                    train_data=train_ctx,
                    should_activate_model=payload.get("should_activate_model", True),
                    infer_on_pipeline=payload.get("infer_on_pipeline", True),
                    from_scratch=payload.get("from_scratch", False),
                    retain_training_artifacts=payload.get("retain_training_artifacts", False),
                )
            return

        report_progress(progress=-1, message="Preparing training data")
        lock_project(job_type="train", project_id=ID(payload["project_id"]))
        train_data = get_train_data(
            project_id=payload["project_id"],
            task_id=payload["task_id"],
            model_storage_id=payload.get("model_storage_id", ""),
            from_scratch=payload["from_scratch"],
            should_activate_model=payload["should_activate_model"],
            infer_on_pipeline=payload.get("infer_on_pipeline", True),
            hyper_parameters_id=payload.get("hyper_parameters_id", ""),
            min_annotation_size=payload.get("min_annotation_size"),
            max_number_of_annotations=payload.get("max_number_of_annotations"),
            reshuffle_subsets=payload.get("reshuffle_subsets", False),
            training_configuration_json=payload.get("training_configuration_json"),
        )
        dataset = create_task_train_dataset(
            train_data=train_data,
            max_training_dataset_size=payload.get("max_training_dataset_size"),
        )

        if payload.get("enable_training_from_dataset_shard", True):
            train_data.compiled_dataset_shards_id = shard_dataset_for_train(
                train_data=train_data,
                dataset=dataset,
                max_shard_size=payload.get("max_shard_size", 1000),
                progress_callback=lambda *_args, **_kwargs: None,
                num_image_pulling_threads=payload.get("num_image_pulling_threads", 10),
                num_upload_threads=payload.get("num_upload_threads", 2),
            )

        output_models = prepare_train(train_data=train_data, dataset=dataset)
        prep_result = {
            "train_data_json": train_data.to_json(),
            "dataset_id": str(dataset.id_),
            "train_output_model_ids_json": output_models.to_train_output_model_ids().to_json(),
        }
        report_progress(progress=100, message="Training data prepared")
        print(f"{_TRAIN_PREP_RESULT_PREFIX}{json.dumps(prep_result)}")
        return

    if job_type == "optimize_pot":
        from job.models import OptimizationTrainerContext
        from job.tasks.evaluation_task import _evaluate_optimized_model
        from job.tasks.helpers import finalize_optimize, prepare_optimize

        stage = os.environ.get("WORKFLOW_JOB_STAGE", "prepare")

        if stage == "finalize":
            serialized = os.environ.get("OPTIMIZE_PREP_RESULT_JSON")
            if not serialized:
                raise RuntimeError("OPTIMIZE_PREP_RESULT_JSON is required for optimize finalize stage")
            prep = json.loads(serialized)
            trainer_ctx = OptimizationTrainerContext.from_json(prep["trainer_ctx_json"])
            finalize_optimize(
                trainer_ctx=trainer_ctx,
                retain_training_artifacts=payload.get("retain_training_artifacts", False),
            )
            return

        if stage == "evaluate":
            serialized = os.environ.get("OPTIMIZE_PREP_RESULT_JSON")
            if not serialized:
                raise RuntimeError("OPTIMIZE_PREP_RESULT_JSON is required for optimize evaluate stage")
            prep = json.loads(serialized)
            trainer_ctx = OptimizationTrainerContext.from_json(prep["trainer_ctx_json"])
            if _bool_env("WORKFLOW_OPTIMIZE_STUB_EVALUATE", True):
                return

            _evaluate_optimized_model(
                project_id=trainer_ctx.project_id,
                dataset_storage_id=prep["dataset_storage_id"],
                model_storage_id=trainer_ctx.model_storage_id,
                model_id=prep["model_id"],
                optimized_model_id=trainer_ctx.model_to_optimize_id,
                min_annotation_size=payload.get("min_annotation_size"),
                max_annotation_size=payload.get("max_annotation_size"),
                min_number_of_annotations=payload.get("min_number_of_annotations"),
                max_number_of_annotations=payload.get("max_number_of_annotations"),
            )
            return

        compiled_dataset_shards_id = _resolve_compiled_dataset_shards_id_for_optimize(payload)
        trainer_ctx = prepare_optimize(
            project_id=payload["project_id"],
            model_storage_id=payload["model_storage_id"],
            model_id=payload["model_id"],
            compiled_dataset_shards_id=compiled_dataset_shards_id,
            min_annotation_size=payload.get("min_annotation_size"),
            max_annotation_size=payload.get("max_annotation_size"),
            min_number_of_annotations=payload.get("min_number_of_annotations"),
            max_number_of_annotations=payload.get("max_number_of_annotations"),
        )
        prep_result = {
            "trainer_ctx_json": trainer_ctx.to_json(),
            "dataset_storage_id": payload["dataset_storage_id"],
            "model_id": payload["model_id"],
        }
        print(f"{_OPTIMIZE_PREP_RESULT_PREFIX}{json.dumps(prep_result)}")
        return

    raise RuntimeError(f"Unsupported workflow runner job type: {job_type}")


def run() -> None:
    from jobs_common.tasks.utils.secrets import setup_session_from_env

    job_type = os.environ["WORKFLOW_JOB_TYPE"]
    payload = _load_payload()
    stage = os.environ.get("WORKFLOW_JOB_STAGE")
    setup_session_from_env()
    compose_context = SimpleNamespace(
        execution_id=SimpleNamespace(name=_compose_execution_id()),
        task_id=SimpleNamespace(name=_compose_task_id(job_type=job_type, stage=stage)),
    )

    with (
        patch("jobs_common.tasks.utils.secrets.set_env_vars", lambda: None),
        patch("jobs_common.tasks.utils.progress.current_context", lambda: compose_context),
    ):
        _run_job_type(job_type=job_type, payload=payload)


if __name__ == "__main__":
    run()
