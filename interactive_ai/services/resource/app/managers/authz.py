# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

from collections.abc import Sequence

from geti_types import CTX_SESSION_VAR, ID
from grpc_interfaces.account_service.client import AccountServiceClient
from grpc_interfaces.account_service.pb.user_pb2 import FindUserRequest, UserGetRolesRequest, UserRolesRequest
from grpc_interfaces.account_service.pb.user_common_pb2 import UserRole, UserRoleOperation


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


def get_permitted_project_ids(user_id: str, organization_id: str) -> tuple[ID, ...]:
    return tuple(ID(role.resource_id) for role in _get_roles(user_id, organization_id, "project"))


def assign_project_admin_role(user_id: str, organization_id: str, project_id: str) -> None:
    request = UserRolesRequest(
        user_id=user_id,
        organization_id=organization_id,
        roles=[
            UserRoleOperation(
                role=UserRole(
                    role="admin",
                    resource_type="project",
                    resource_id=project_id,
                ),
                operation="CREATE",
            )
        ],
    )
    with AccountServiceClient(metadata_getter=_metadata) as client:
        client.user_stub.set_roles(request, metadata=_metadata())


def remove_project_roles(organization_id: str, project_id: str) -> None:
    find_user_request = FindUserRequest(organization_id=organization_id)
    with AccountServiceClient(metadata_getter=_metadata) as client:
        users = client.user_stub.find(find_user_request, metadata=_metadata()).users
        for user in users:
            request = UserRolesRequest(
                user_id=user.id,
                organization_id=organization_id,
                roles=[
                    UserRoleOperation(
                        role=UserRole(
                            role="admin",
                            resource_type="project",
                            resource_id=project_id,
                        ),
                        operation="DELETE",
                    ),
                    UserRoleOperation(
                        role=UserRole(
                            role="contributor",
                            resource_type="project",
                            resource_id=project_id,
                        ),
                        operation="DELETE",
                    ),
                ],
            )
            client.user_stub.set_roles(request, metadata=_metadata())
