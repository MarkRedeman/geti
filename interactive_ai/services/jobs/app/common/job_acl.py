# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

from geti_types import CTX_SESSION_VAR
from grpc_interfaces.account_service.client import AccountServiceClient
from grpc_interfaces.account_service.pb.user_pb2 import UserRolesRequest
from grpc_interfaces.account_service.pb.user_common_pb2 import UserRole, UserRoleOperation


def _set_job_view_access(user_id: str, job_id: str, operation: str) -> None:
    if not user_id:
        return

    user_id_normalized = user_id.lower()
    if user_id_normalized in {"geti", "00000000-0000-0000-0000-000000000000"}:
        return

    session = CTX_SESSION_VAR.get()
    metadata = session.as_tuple()

    request = UserRolesRequest(
        user_id=user_id,
        organization_id=str(session.organization_id),
        roles=[
            UserRoleOperation(
                role=UserRole(
                    role="view_job",
                    resource_type="job",
                    resource_id=job_id,
                ),
                operation=operation,
            )
        ],
    )

    with AccountServiceClient(metadata_getter=lambda: metadata) as client:
        client.user_stub.set_roles(request, metadata=metadata)


def grant_job_view_access(user_id: str, job_id: str) -> None:
    _set_job_view_access(user_id=user_id, job_id=job_id, operation="CREATE")


def revoke_job_view_access(user_id: str, job_id: str) -> None:
    _set_job_view_access(user_id=user_id, job_id=job_id, operation="DELETE")
