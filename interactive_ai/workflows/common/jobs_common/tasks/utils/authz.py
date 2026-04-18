# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

from geti_types import CTX_SESSION_VAR
from grpc_interfaces.account_service.client import AccountServiceClient
from grpc_interfaces.account_service.pb.user_pb2 import UserRolesRequest
from grpc_interfaces.account_service.pb.user_common_pb2 import UserRole, UserRoleOperation


def assign_project_admin_role(user_id: str, project_id: str) -> None:
    session = CTX_SESSION_VAR.get()
    metadata = session.as_tuple()

    request = UserRolesRequest(
        user_id=user_id,
        organization_id=str(session.organization_id),
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

    with AccountServiceClient(metadata_getter=lambda: metadata) as client:
        client.user_stub.set_roles(request, metadata=metadata)
