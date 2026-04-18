# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

from collections.abc import Sequence

from geti_types import CTX_SESSION_VAR, ID
from grpc_interfaces.account_service.client import AccountServiceClient
from grpc_interfaces.account_service.pb.user_pb2 import UserGetRolesRequest
from grpc_interfaces.account_service.pb.user_common_pb2 import UserRole


def _metadata() -> tuple[tuple[str, str], ...]:
    return CTX_SESSION_VAR.get().as_tuple()


def _get_roles(user_id: str, organization_id: str, resource_type: str) -> Sequence[UserRole]:
    request = UserGetRolesRequest(
        user_id=user_id,
        organization_id=organization_id,
        resource_type=resource_type,
    )
    with AccountServiceClient(metadata_getter=_metadata) as client:
        return client.user_stub.get_roles(request, metadata=_metadata()).roles


def get_permitted_project_ids(user_id: str, organization_id: str) -> list[ID]:
    return [ID(role.resource_id) for role in _get_roles(user_id, organization_id, "project")]


def can_view_all_workspace_jobs(user_id: str, organization_id: str, workspace_id: str) -> bool:
    workspace_roles = _get_roles(user_id, organization_id, "workspace")
    if any(role.resource_id == workspace_id and role.role == "admin" for role in workspace_roles):
        return True

    organization_roles = _get_roles(user_id, organization_id, "organization")
    return any(role.role == "admin" for role in organization_roles)
