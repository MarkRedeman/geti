# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import importlib
from contextlib import ExitStack
from unittest.mock import patch


class WorkflowAdapterError(RuntimeError):
    """Raised when a workflow job payload cannot be adapted/executed."""


def _patched_flyte_wrappers() -> ExitStack:
    stack = ExitStack()
    stack.enter_context(patch("jobs_common.tasks.utils.secrets.set_env_vars", lambda: None))
    stack.enter_context(patch("jobs_common.tasks.utils.progress.report_progress", lambda *args, **kwargs: None))
    stack.enter_context(patch("jobs_common.tasks.utils.progress.publish_metadata_update", lambda metadata: None))
    return stack


def run_import_export_job(job_type: str, payload: dict) -> None:
    """
    Execute dataset/project import-export workflow tasks directly (without Flyte orchestration).
    """
    with _patched_flyte_wrappers():
        if job_type == "export_dataset":
            fn = importlib.import_module("job.tasks.export_tasks.export_dataset_task").export_dataset_task
            fn(
                organization_id=payload["organization_id"],
                project_id=payload["project_id"],
                dataset_storage_id=payload["dataset_storage_id"],
                include_unannotated=payload.get("include_unannotated", False),
                export_format=payload["export_format"],
                save_video_as_images=payload.get("save_video_as_images", False),
            )
            return

        if job_type == "prepare_import_to_new_project":
            fn = importlib.import_module(
                "job.tasks.import_tasks.parse_dataset_new_project"
            ).parse_dataset_for_import_to_new_project
            fn(import_id=payload["import_id"])
            return

        if job_type == "prepare_import_to_existing_project":
            fn = importlib.import_module(
                "job.tasks.import_tasks.parse_dataset_existing_project"
            ).parse_dataset_for_import_to_existing_project
            fn(import_id=payload["import_id"], project_id=payload["project_id"])
            return

        if job_type == "perform_import_to_new_project":
            fn = importlib.import_module(
                "job.tasks.import_tasks.create_project_from_dataset"
            ).create_project_from_dataset
            fn(
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
            fn = importlib.import_module("job.tasks.import_tasks.import_dataset_to_project").import_dataset_to_project
            fn(
                project_id=payload["project_id"],
                import_id=payload["import_id"],
                label_ids_map=payload["label_ids_map"],
                dataset_storage_id=payload["dataset_storage_id"],
                dataset_name=payload["dataset_name"],
                user_id=payload["user_id"],
            )
            return

        if job_type == "export_project":
            fn = importlib.import_module("job.tasks.export_project").export_project
            fn(project_id=payload["project_id"], include_models=payload.get("include_models", "all"))
            return

        if job_type == "import_project":
            fn = importlib.import_module("job.tasks.import_project").import_project
            fn(
                file_id=payload["file_id"],
                keep_original_dates=payload.get("keep_original_dates", False),
                project_name=payload["project_name"],
                user_id=payload["user_id"],
            )
            return

    raise WorkflowAdapterError(f"Unsupported import/export job type: {job_type}")
