# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE
import base64
import os
from binascii import a2b_base64


def get_sub_from_jwt_token(uid: str) -> str:
    """
    Generate the JWT subject string (sub) based on a given user ID (uid).

    :param uid: The user ID used to construct the IDTokenSubject object.

    :return: A base64 encoded serialized JWT subject string.
    """
    conn_id = os.getenv("DEX_CONNECTOR_ID", "local")
    if conn_id == "local":
        user_id = uid
    else:
        user_id = f"cn={uid},dc=example,dc=org"
    message = bytearray()
    message.append((1 << 3) | 2)
    message.extend(_encode_varint(len(user_id)))
    message.extend(user_id.encode("utf-8"))
    message.append((2 << 3) | 2)
    message.extend(_encode_varint(len(conn_id)))
    message.extend(conn_id.encode("utf-8"))
    sub: str = base64.b64encode(bytes(message)).decode(encoding="utf8").rstrip("=")
    return sub


def _encode_varint(value: int) -> bytes:
    out = bytearray()
    while value >= 0x80:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value)
    return bytes(out)


def base64_encode(data: str) -> str:
    """Encode data as base64 with padding removed"""
    return (
        base64.encodebytes(data.encode("utf-8"))
        .decode("utf-8")
        .replace("=", "")
        .replace("\n", "")
    )


def ab64_decode(data: str) -> str:
    """Decode data as base64 with padding removed"""
    data = data.replace(".", "+")
    return a2b_base64(data + "=" * (-len(data) % 4)).decode("utf-8")
