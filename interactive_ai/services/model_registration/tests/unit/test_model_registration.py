# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE
from unittest.mock import AsyncMock

import pytest
from botocore.exceptions import ClientError
from grpc.aio import ServicerContext
from grpc_interfaces.model_registration.pb.service_pb2 import (
    ActiveRequest,
    DeregisterRequest,
    ListRequest,
    PurgeProjectRequest,
    RecoverRequest,
    RegisterRequest,
)

from service.config import S3_BUCKETNAME
from service.model_registration import ModelRegistration
from service.responses import Responses


@pytest.fixture
def servicer_context():
    return AsyncMock(spec=ServicerContext)


@pytest.fixture
def s3_client(mocker):
    return mocker.patch("service.model_registration.S3Client")


@pytest.fixture
def converter(mocker):
    return mocker.patch("service.model_registration.ModelConverter")


@pytest.fixture
def ovms_manager(mocker):
    return mocker.patch("service.model_registration.OvmsConfigManager")


@pytest.fixture
def model_registration(s3_client, converter, ovms_manager):
    return ModelRegistration()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name, override, existing, expected_response",
    [
        ("test", True, {"pipeline_name": "test"}, Responses.Created),
        ("test", False, {"pipeline_name": "test"}, Responses.AlreadyRegistered),
        ("new", False, None, Responses.Created),
    ],
)
async def test_register_new_pipelines(
    model_registration,
    converter,
    servicer_context,
    s3_client,
    ovms_manager,
    name,
    override,
    existing,
    expected_response,
):
    s3_client.return_value.get_json_object.return_value = existing
    req = RegisterRequest(name=name, override=override)
    response = await model_registration.register_new_pipelines(req, servicer_context)

    assert response.status == expected_response
    if existing and not override:
        s3_client.return_value.upload_folder.assert_not_called()
        ovms_manager.return_value.add_model.assert_not_called()
        return

    s3_client.return_value.upload_folder.assert_called_once()
    s3_client.return_value.put_json_object.assert_called_once()
    ovms_manager.return_value.sync_model_directory.assert_called_once()
    ovms_manager.return_value.add_model.assert_called_once_with(pipeline_name=name)
    converter.assert_called_once()
    if existing and override:
        s3_client.return_value.delete_folder.assert_called_once_with(bucket_name=S3_BUCKETNAME, object_key=name)
        ovms_manager.return_value.remove_model.assert_called_once_with(pipeline_name=name)
        ovms_manager.return_value.remove_model_directory.assert_called_once_with(pipeline_name=name)


@pytest.mark.asyncio
async def test_register_new_pipelines_error(model_registration, servicer_context, s3_client):
    s3_client.return_value.get_json_object.side_effect = ClientError(
        {"Error": {"Code": 500, "Message": "Error"}}, "get_object"
    )
    req = RegisterRequest(name="test", override=False)
    response = await model_registration.register_new_pipelines(req, servicer_context)
    assert response.status == Responses.Failed


@pytest.mark.asyncio
async def test_deregister_pipeline(model_registration, servicer_context, s3_client, ovms_manager):
    req = DeregisterRequest(name="test")
    response = await model_registration.deregister_pipeline(req, servicer_context)

    assert response.status == Responses.Removed
    s3_client.return_value.delete_folder.assert_called_once_with(bucket_name=S3_BUCKETNAME, object_key="test")
    ovms_manager.return_value.remove_model.assert_called_once_with(pipeline_name="test")
    ovms_manager.return_value.remove_model_directory.assert_called_once_with(pipeline_name="test")


@pytest.mark.asyncio
async def test_deregister_pipeline_failed(model_registration, servicer_context, s3_client):
    s3_client.return_value.delete_folder.side_effect = ClientError(
        {"Error": {"Code": 500, "Message": "Error"}}, "delete_object"
    )
    req = DeregisterRequest(name="test")
    response = await model_registration.deregister_pipeline(req, servicer_context)
    assert response.status == Responses.Failed


@pytest.mark.asyncio
async def test_register_active_pipeline(model_registration, servicer_context):
    req = ActiveRequest()
    response = await model_registration.register_active_pipeline(req, servicer_context)
    assert response.status == Responses.NotImplemented


@pytest.mark.asyncio
async def test_list_pipeline(model_registration, servicer_context, s3_client):
    s3_client.return_value.list_registry_folders.return_value = ["model1", "model2"]
    req = ListRequest()
    response = await model_registration.list_pipelines(req, servicer_context)
    assert response.pipelines == ["model1", "model2"]


@pytest.mark.asyncio
async def test_recover_pipelines_success(model_registration, servicer_context, s3_client, ovms_manager):
    s3_client.return_value.check_folder_exists.return_value = True
    req = RecoverRequest(name="test")
    response = await model_registration.recover_pipeline(req, servicer_context)
    assert response.success is True
    s3_client.return_value.download_folder.assert_called_once()
    s3_client.return_value.put_json_object.assert_called_once()
    ovms_manager.return_value.sync_model_directory.assert_called_once()
    ovms_manager.return_value.add_model.assert_called_once_with(pipeline_name="test")


@pytest.mark.asyncio
async def test_recover_pipelines_not_found(model_registration, servicer_context, s3_client, ovms_manager):
    s3_client.return_value.check_folder_exists.return_value = False
    req = RecoverRequest(name="test")
    response = await model_registration.recover_pipeline(req, servicer_context)
    assert response.success is False
    s3_client.return_value.put_json_object.assert_not_called()
    ovms_manager.return_value.sync_model_directory.assert_not_called()
    ovms_manager.return_value.add_model.assert_not_called()


@pytest.mark.asyncio
async def test_delete_project_pipelines(model_registration, servicer_context, s3_client, ovms_manager):
    s3_client.return_value.list_folders.return_value = ["test-model1", "test-model2", "other-model"]
    req = PurgeProjectRequest(project_id="test")
    response = await model_registration.delete_project_pipelines(req, servicer_context)
    assert response.success is True
    assert s3_client.return_value.delete_folder.call_count == 2
    assert ovms_manager.return_value.remove_model.call_count == 2
    assert ovms_manager.return_value.remove_model_directory.call_count == 2


@pytest.mark.asyncio
async def test_delete_project_pipelines_failed(model_registration, servicer_context, s3_client):
    s3_client.return_value.list_folders.return_value = ["test-model1"]
    s3_client.return_value.delete_folder.side_effect = ClientError(
        {"Error": {"Code": 500, "Message": "Error"}}, "delete_object"
    )
    req = PurgeProjectRequest(project_id="test")
    response = await model_registration.delete_project_pipelines(req, servicer_context)
    assert response.success is False
