# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import time
import os

from geti_logger_tools.logger_config import initialize_logger
from grpc import RpcError
from grpc_interfaces.account_service.pb.user_common_pb2 import UserRole, UserRoleOperation
from grpc_interfaces.account_service.pb.user_pb2 import UserRolesRequest
from users_handler_client import UsersHandlerConnection

from account_service_client import AccountServiceConnection
from users_handler.exceptions import EmailAlreadyExists

from common import get_sub_from_jwt_token

logger = initialize_logger(__name__)


def main() -> None:
    """
    Main function that will:
        - create default organization and workspace
        - add initial user to account service and openldap
        - get 'sub' from manually created jwt token
        - update user's external_id in Account Service by 'sub' key.
    """
    acc_svc = AccountServiceConnection()
    for _ in range(15):
        try:
            organization_id = acc_svc.client.create_default_organization()
            workspace_id = acc_svc.client.create_default_workspace(organization_id=organization_id)
            break
        except RpcError as rpc_err:
            rpc_err_message = str(rpc_err)
            logger.warning(rpc_err)
            if "no healthy upstream" in rpc_err_message.lower() or "StatusCode.UNAVAILABLE" in rpc_err_message:
                time.sleep(60)
            else:
                raise rpc_err
    else:
        raise RuntimeError("Connection to account service has timed out - no healthy upstream.")
    uh_connection = UsersHandlerConnection()
    user_id = acc_svc.client.create_initial_user(organization_id=organization_id)
    try:
        uh_connection.create_initial_user(
            uid=user_id,
            workspace_id=workspace_id,
            organization_id=organization_id,
            apply_roles_in_spicedb=False,
        )
    except EmailAlreadyExists:
        logger.info("User exists in ldap")

    # Assign bootstrap roles via account service API instead of direct SpiceDB writes.
    role_ops = [
        UserRoleOperation(
            role=UserRole(role="organization_admin", resource_type="organization", resource_id=organization_id),
            operation="TOUCH",
        ),
        UserRoleOperation(
            role=UserRole(role="workspace_admin", resource_type="workspace", resource_id=workspace_id),
            operation="TOUCH",
        ),
    ]
    acc_svc.client.user_stub.set_roles(
        UserRolesRequest(user_id=user_id, organization_id=organization_id, roles=role_ops)
    )
    dex_static_user_id = os.getenv("DEX_STATIC_USER_ID", "")
    sub_source_uid = dex_static_user_id if dex_static_user_id else user_id
    sub = get_sub_from_jwt_token(uid=sub_source_uid)
    acc_svc.client.update_user_external_id(uid=user_id, organization_id=organization_id, external_id=sub)


if __name__ == "__main__":
    main()
