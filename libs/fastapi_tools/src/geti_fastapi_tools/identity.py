import logging
import os
from collections.abc import Mapping

import jwt

from geti_fastapi_tools.exceptions import (
    InvalidRequestAccessTokenException,
    MissingRequestAccessTokenException,
    UserException,
)

logger = logging.getLogger(__name__)

ACCESS_TOKEN_HEADER_NAME = "x-auth-request-access-token"  # noqa: S105
AUTH_MODE_ENV_NAME = "AUTH_MODE"
MOCK_AUTH_MODE_VALUE = "mock"
MOCK_USER_ID_ENV_NAME = "MOCK_USER_ID"


def _is_mock_auth_mode() -> bool:
    return os.getenv(AUTH_MODE_ENV_NAME, "").lower() == MOCK_AUTH_MODE_VALUE


def _mock_access_token_payload() -> dict[str, str]:
    user_id = os.getenv(MOCK_USER_ID_ENV_NAME, "local-admin")
    return {
        "owner_id": user_id,
        "preferred_username": user_id,
        "source": "browser",
    }


class RestApiAuth:
    """Helper class for extracting user information from request headers"""

    @classmethod
    def get_access_token_data(cls, headers: Mapping[str, str | bytes]) -> dict:
        """
        Extract the access token from the request headers

        :param headers: HTTP request headers
        :return: Token payload
        :raises MissingRequestAccessTokenException: if the request headers do not contain the access token
        :raises InvalidRequestAccessTokenException: if the access token is invalid
        """
        id_token_header = headers.get(ACCESS_TOKEN_HEADER_NAME)

        if id_token_header is None:
            if _is_mock_auth_mode():
                logger.warning("[MOCK AUTH] Missing access token header, using local mock identity.")
                return _mock_access_token_payload()
            # Note: this is standard behavior for internal requests
            logger.debug("No access token provided in the request header")
            raise MissingRequestAccessTokenException

        try:
            return jwt.decode(
                jwt=id_token_header,
                options={
                    "verify_signature": False,
                    "verify_exp": True,
                },
            )
        except jwt.PyJWTError as err:
            if _is_mock_auth_mode():
                logger.warning("[MOCK AUTH] Invalid access token header, using local mock identity.")
                return _mock_access_token_payload()
            logger.exception(f"Header {ACCESS_TOKEN_HEADER_NAME} could not be decoded. Value: `{id_token_header!r}`")
            raise InvalidRequestAccessTokenException(value=id_token_header) from err

    @classmethod
    def get_user_id(cls, headers: Mapping[str, str | bytes]) -> str:
        """
        Get the user ID from a request headers

        :param headers: HTTP request headers
        :return: string representing the ID of the user
        :raises UserException: if the request headers do not contain the expected information
        """
        decoded_data = cls.get_access_token_data(headers)
        try:
            return decoded_data.get("owner_id", decoded_data["preferred_username"])
        except KeyError as err:
            raise UserException("No user id found in JWT (missing key 'preferred_username' or 'owner_id')") from err

    @classmethod
    def get_source(cls, headers: Mapping[str, str | bytes]) -> str | None:
        """
        Get the 'source' claim from a request headers

        :param headers: HTTP request headers
        :return: Value of the 'source', or None if not found
        :raises UserException: if the request headers do not contain the expected information
        """
        decoded_data = cls.get_access_token_data(headers)
        return decoded_data.get("source")
