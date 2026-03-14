# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

"""
Platform management utilities.
"""

import os
from datetime import datetime, timezone

from kubernetes.client.rest import ApiException
from service_connection.k8s_client.apis import K8S

from config import DEPLOYMENT_MODE, IMPT_CONFIGURATION_CM, K8S_CR_NAMESPACE

# Compose-mode fallback: a fixed installation epoch so callers that compare
# against it still get a sensible (distant-past) value.
_COMPOSE_INSTALL_EPOCH = datetime(2020, 1, 1, tzinfo=timezone.utc)


def get_installation_datetime() -> datetime:
    """Returns platform installation timestamp.

    In compose mode, no Kubernetes config map is available.  A fixed epoch
    datetime is returned so that log-archive date-range logic works without
    crashing.
    """
    if DEPLOYMENT_MODE == "compose":
        env_dt = os.getenv("PLATFORM_INSTALLATION_DATETIME")
        if env_dt:
            try:
                return datetime.fromisoformat(env_dt)
            except ValueError:
                pass
        return _COMPOSE_INSTALL_EPOCH

    k8s_api = K8S.get_k8s_api()
    try:
        config_map = k8s_api.read_namespaced_config_map(name=IMPT_CONFIGURATION_CM, namespace=K8S_CR_NAMESPACE)
    except ApiException as err:
        raise OSError("Failed to retrieve the platform installation date.") from err

    return config_map.metadata.creation_timestamp
