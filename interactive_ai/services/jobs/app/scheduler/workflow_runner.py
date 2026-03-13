# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import json
import os
from unittest.mock import patch

_TRAIN_PREP_RESULT_PREFIX = "TRAIN_PREP_RESULT="


def _load_payload() -> dict:
    return json.loads(os.environ["WORKFLOW_PAYLOAD_JSON"])


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

        import_dataset_to_project(
            project_id=payload["project_id"],
            import_id=payload["import_id"],
            label_ids_map=payload["label_ids_map"],
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
        from jobs_common.jobs.helpers.project_helpers import lock_project
        from job.tasks.prepare_and_train.create_task_train_dataset import create_task_train_dataset
        from job.tasks.prepare_and_train.get_train_data import get_train_data
        from job.tasks.prepare_and_train.train_helpers import finalize_train, prepare_train
        from job.utils.train_workflow_data import TrainWorkflowData
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
        output_models = prepare_train(train_data=train_data, dataset=dataset)
        prep_result = {
            "train_data_json": train_data.to_json(),
            "dataset_id": str(dataset.id_),
            "train_output_model_ids_json": output_models.to_train_output_model_ids().to_json(),
        }
        print(f"{_TRAIN_PREP_RESULT_PREFIX}{json.dumps(prep_result)}")
        return

    raise RuntimeError(f"Unsupported workflow runner job type: {job_type}")


def run() -> None:
    job_type = os.environ["WORKFLOW_JOB_TYPE"]
    payload = _load_payload()

    with (
        patch("jobs_common.tasks.utils.secrets.set_env_vars", lambda: None),
        patch("jobs_common.tasks.utils.progress.report_progress", lambda *a, **k: None),
        patch("jobs_common.tasks.utils.progress.publish_metadata_update", lambda m: None),
    ):
        _run_job_type(job_type=job_type, payload=payload)


if __name__ == "__main__":
    run()
