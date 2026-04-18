# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

from datetime import datetime, timezone
import logging
import os
import pathlib
import shutil
import sys
import tempfile
from collections.abc import AsyncGenerator
from zipfile import BadZipFile

import aiofiles
import grpc
from botocore.exceptions import ClientError
from grpc_interfaces.model_registration.pb.service_pb2 import (
    ActiveRequest,
    Chunk,
    DeregisterRequest,
    DownloadGraphRequest,
    Error,
    ErrorCode,
    ListRequest,
    ListResponse,
    PurgeProjectRequest,
    PurgeProjectResponse,
    RecoverRequest,
    RecoverResponse,
    RegisterRequest,
    StatusResponse,
)
from grpc_interfaces.model_registration.pb.service_pb2_grpc import ModelRegistrationServicer

from service.config import S3_BUCKETNAME
from service.model_converter import GraphVariant, ModelConverter, UnsupportedModelType
from service.ovms_config import OvmsConfigManager
from service.responses import Responses
from service.s3client import S3Client

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)


def _registry_key(pipeline_name: str) -> str:
    return f"{pipeline_name}/.registry.json"


class ModelRegistration(ModelRegistrationServicer):
    """
    This class is the main handler for ModelRegistration API calss
    """

    def __init__(self) -> None:
        self.s3 = S3Client()
        self.converter = ModelConverter(self.s3)
        self.ovms = OvmsConfigManager()
        super().__init__()

    def make_error(self, code: ErrorCode.ValueType) -> Error:
        messages = {
            ErrorCode.MODEL_ALREADY_REGISTERED: "Model is already registered.",
            ErrorCode.UNSUPPORTED_MODEL_TYPE: "Unsupported model type.",
            ErrorCode.INVALID_MODEL_ZIP_PACKAGE: "Invalid model zip package.",
            ErrorCode.INTERNAL_ERROR: "Internal error.",
            ErrorCode.NOT_IMPLEMENTED: "Not implemented.",
        }
        message = messages.get(code, "Unknown error.")
        return Error(code=code, message=message)

    def handle_exception(self, error_code: ErrorCode.ValueType, message: str) -> StatusResponse:
        logger.exception(message)
        return StatusResponse(status=Responses.Failed, error=self.make_error(code=error_code))

    def _write_registry_record(self, pipeline_name: str, project_id: str | None = None) -> None:
        payload = {
            "pipeline_name": pipeline_name,
            "project_id": project_id,
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
            "deployment_mode": "compose",
        }
        self.s3.put_json_object(bucket_name=S3_BUCKETNAME, object_key=_registry_key(pipeline_name), payload=payload)

    async def register_new_pipelines(
        self,
        req: RegisterRequest,
        context: grpc.aio.ServicerContext,  # noqa: ARG002
    ) -> StatusResponse:
        """
        Registers new pipeline
        """
        pipeline_name = req.name if len(req.name) > 0 else f"{req.project.id}_active"
        try:
            existing = self.s3.get_json_object(bucket_name=S3_BUCKETNAME, object_key=_registry_key(pipeline_name))
            if existing and not req.override:
                logger.info(f"Model {pipeline_name} already registered (compose registry)")
                return StatusResponse(
                    status=Responses.AlreadyRegistered,
                    error=self.make_error(code=ErrorCode.MODEL_ALREADY_REGISTERED),
                )

            if existing and req.override:
                self.s3.delete_folder(bucket_name=S3_BUCKETNAME, object_key=pipeline_name)
                self.ovms.remove_model(pipeline_name=pipeline_name)
                self.ovms.remove_model_directory(pipeline_name=pipeline_name)

            export_dir = self.converter.prepare_graph(project=req.project, models=req.model)
            try:
                self.s3.upload_folder(bucket_name=S3_BUCKETNAME, object_key=pipeline_name, local_folder_path=export_dir)
                self.ovms.sync_model_directory(pipeline_name=pipeline_name, source_dir=export_dir)
            finally:
                self.converter._delete_dir(dir_path=export_dir)
            self.ovms.add_model(pipeline_name=pipeline_name)
            self._write_registry_record(pipeline_name=pipeline_name, project_id=req.project.id)
            return StatusResponse(status=Responses.Created)
        except ClientError as s3_err:
            response = self.handle_exception(
                ErrorCode.INTERNAL_ERROR, f"Failed to create inference {pipeline_name}. S3 error: {s3_err}"
            )
        except BadZipFile as zip_err:
            response = self.handle_exception(
                ErrorCode.INVALID_MODEL_ZIP_PACKAGE,
                f"Failed to create inference {pipeline_name}. Invalid model zip package: {zip_err}",
            )
        except UnsupportedModelType as model_err:
            response = self.handle_exception(
                ErrorCode.UNSUPORTED_MODEL_TYPE,
                f"Failed to create inference {pipeline_name}. Unsupported model type: {model_err}",
            )
        except OSError as os_err:
            response = self.handle_exception(
                ErrorCode.INTERNAL_ERROR, f"Failed to create inference {pipeline_name}. Encountered OS error: {os_err}"
            )
        except RuntimeError as err:
            response = self.handle_exception(
                ErrorCode.INTERNAL_ERROR,
                f"Failed to create inference {pipeline_name}. Encountered runtime error: {err}",
            )

        return response

    async def download_graph(
        self,
        req: DownloadGraphRequest,
        context: grpc.aio.ServicerContext,
    ) -> AsyncGenerator[Chunk, None]:  # type: ignore
        """
        Download a graph for given models
        """
        graph_directory = None
        graph_archive_path = None
        try:
            graph_directory = pathlib.Path(
                self.converter.prepare_graph(
                    models=req.models, project=req.project, graph_variant=GraphVariant.OVMS_DEPLOYMENT
                )
            )
            graph_archive_path = graph_directory.parent.joinpath(f"{req.project.id}.zip")

            # Create archive with prepared graph
            # Due to shutil.make_archive intricacies, we have to change working dir manually
            # and create zip file in another directory
            cwd = os.getcwd()
            try:
                os.chdir(graph_directory)
                shutil.make_archive(
                    base_name=f"../{str(req.project.id)}",
                    root_dir=None,
                    base_dir=None,
                    format="zip",
                )
            finally:
                os.chdir(cwd)

            # Stream archived graph as a response
            async with aiofiles.open(graph_archive_path, "rb") as archive:
                while archive_chunk := await archive.read(1024 * 1024):
                    yield Chunk(buffer=archive_chunk)

        except (RuntimeError, ClientError) as err:
            error_message = f"Failed to create graph, {req.project=} {req.models=}. Encountered error: {err}"
            logger.exception(error_message)
            await context.abort(grpc.StatusCode.INTERNAL, details=error_message)
        finally:
            if graph_directory:
                self.converter._delete_dir(dir_path=str(graph_directory))
            if graph_archive_path:
                graph_archive_path.unlink(missing_ok=True)

    async def deregister_pipeline(
        self,
        request: DeregisterRequest,
        context: grpc.aio.ServicerContext,  # noqa: ARG002
    ) -> StatusResponse:
        """
        Deregisters existing pipeline
        """
        try:
            self.s3.delete_folder(bucket_name=S3_BUCKETNAME, object_key=request.name)
            self.ovms.remove_model(pipeline_name=request.name)
            self.ovms.remove_model_directory(pipeline_name=request.name)
            return StatusResponse(status=Responses.Removed)
        except ClientError as s3_err:
            response = self.handle_exception(
                ErrorCode.INTERNAL_ERROR,
                f"Failed to remove inference {request.name}. Encountered S3 client error: {s3_err}",
            )
        except OSError as os_err:
            response = self.handle_exception(
                ErrorCode.INTERNAL_ERROR,
                f"Failed to remove inference {request.name}. Encountered OS error: {os_err}",
            )
        except RuntimeError as err:
            response = self.handle_exception(
                ErrorCode.INTERNAL_ERROR, f"Failed to remove inference {request.name}. Encountered runtime error: {err}"
            )
        return response

    async def register_active_pipeline(
        self,
        request: ActiveRequest,  # noqa: ARG002
        context: grpc.aio.ServicerContext,  # noqa: ARG002
    ) -> StatusResponse:
        return StatusResponse(status=Responses.NotImplemented, error=self.make_error(code=ErrorCode.NOT_IMPLEMENTED))

    async def list_pipelines(
        self,
        request: ListRequest,  # noqa: ARG002
        context: grpc.aio.ServicerContext,  # noqa: ARG002
    ) -> ListResponse:
        """
        List existing pipelines
        """
        pipelines = self.s3.list_registry_folders(bucket_name=S3_BUCKETNAME)
        return ListResponse(pipelines=pipelines)

    async def recover_pipeline(
        self,
        request: RecoverRequest,
        context: grpc.aio.ServicerContext,  # noqa: ARG002
    ) -> RecoverResponse:
        """
        Re-register a pipeline from S3, if possible

        Checks if the folder with model artifacts exists on S3. If so, the model will
        be registered with ModelMesh and a success response is returned
        """
        pipeline_name = request.name
        if self.s3.check_folder_exists(bucket_name=S3_BUCKETNAME, object_key=pipeline_name):
            export_dir = tempfile.mkdtemp(prefix="recover-", dir="/tmp")
            try:
                self.s3.download_folder(
                    bucket_name=S3_BUCKETNAME, object_key=pipeline_name, local_folder_path=export_dir
                )
                self.ovms.sync_model_directory(pipeline_name=pipeline_name, source_dir=export_dir)
            finally:
                self.converter._delete_dir(dir_path=export_dir)
            self.ovms.add_model(pipeline_name=pipeline_name)
            self._write_registry_record(pipeline_name=pipeline_name)
            logger.info(f"Model `{pipeline_name}` recovered successfully in compose mode")
            return RecoverResponse(success=True)
        logger.info(f"Unable to recover model `{pipeline_name}` in compose mode")
        return RecoverResponse(success=False)

    async def delete_project_pipelines(
        self,
        request: PurgeProjectRequest,
        context: grpc.aio.ServicerContext,  # noqa: ARG002
    ) -> PurgeProjectResponse:
        """
        Remove all project inference pipelines and inference services.

        This endpoint does the following:
        - Delete all existing inference services for a project from the cluster
        - Remove all inference model artifacts for the project from S3

        If all pipelines and artifacts are deleted without errors, the endpoint
        returns a success response
        """
        project_prefix = request.project_id + "-"
        success = True

        folder_names = self.s3.list_folders(bucket_name=S3_BUCKETNAME)
        project_folder_names = [n for n in folder_names if n.startswith(project_prefix)]
        logger.info(f"Deleting {len(project_folder_names)} compose model folders for project {request.project_id}")
        for folder_name in project_folder_names:
            try:
                self.s3.delete_folder(bucket_name=S3_BUCKETNAME, object_key=folder_name)
                self.ovms.remove_model(pipeline_name=folder_name)
                self.ovms.remove_model_directory(pipeline_name=folder_name)
            except ClientError as err:
                logger.error(
                    f"Failed to remove inference model artifact folder {folder_name}. S3 client returned error: {err}"
                )
                success = False
        return PurgeProjectResponse(success=success)
