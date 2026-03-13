"""
Module for operations related to JWT token validation.
"""

# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import logging
import os

import jwt.exceptions
from service_connection.k8s_client.secrets import get_secrets

from users_handler.exceptions import WrongUserToken
from users_handler.users_handler import UsersHandler, UserType

from common.errors import BadTokenError
from config import JWT_SECRET

logger = logging.getLogger(__name__)


def _is_mock_auth_mode() -> bool:
    return os.getenv("AUTH_MODE", "").lower() == "mock"


def _mock_user(token: str) -> UserType:
    user_id = os.getenv("MOCK_USER_ID", "local-admin")
    user_email = os.getenv("MOCK_USER_EMAIL", "local-admin@geti.local")
    return {
        "uid": user_id,
        "name": os.getenv("MOCK_USER_NAME", "Local Admin"),
        "mail": user_email,
        "roles": [],
        "group": 500,
        "registered": True,
        "email_token": token,
    }


def verify_jwt_token(handler: UsersHandler, token: str) -> UserType:
    """
    Wraps UsersHandler token verification with common list of exceptions which should return
    common error (e.g. 'bad request') from the API
    """
    if _is_mock_auth_mode():
        logger.warning("[MOCK AUTH] user_directory token verification bypass active.")
        return _mock_user(token)

    try:
        secret = get_secrets(
            name=JWT_SECRET,
            secrets_list=["key"],
        )["key"]
        user = handler.verify_jwt_token(token, secret)
    except (
        jwt.exceptions.ExpiredSignatureError,
        jwt.exceptions.DecodeError,
        jwt.DecodeError,
        jwt.exceptions.InvalidTokenError,
        WrongUserToken,
    ) as ex:
        logger.exception("error during token verification")
        raise BadTokenError from ex

    return user
