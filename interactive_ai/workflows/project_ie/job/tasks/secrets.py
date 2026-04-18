# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import os
from functools import wraps

PROJECT_IE_SECRETS: list[str] = []


def signing_key_env_vars(fn):  # noqa: ANN001, ANN201
    """
    Decorator to set task environment variables for signing keys
    """

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not os.environ.get("SIGNING_IE_PRIVKEY"):
            raise RuntimeError("SIGNING_IE_PRIVKEY must be set in compose mode.")
        return fn(*args, **kwargs)

    return wrapper
