"""
Functions for kubernetes config maps management
"""

# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import logging
import os

from kubernetes.client.rest import ApiException

from service_connection.k8s_client.apis import K8S

from config import DEPLOYMENT_MODE, K8S_CR_NAMESPACE

logger = logging.getLogger(__name__)

# Compose-mode defaults for well-known config map fields that have no
# runtime-specific values (pure platform configuration).
_COMPOSE_CM_DEFAULTS: dict[str, dict[str, str]] = {
    "impt-configuration": {
        "invite-user-expiration": "43200",
        "password_reset_expiration": "15",
    },
}


def _get_config_map_from_env(name: str, field_list: list[str] | None) -> dict:
    """
    Compose-mode fallback: reads config-map fields from environment variables or
    built-in defaults.

    Each key is looked up as ``GETI_CM_<NAME>_<KEY>`` (upper-cased, hyphens and
    dots replaced with underscores).  When a variable is not set the function
    falls back to ``_COMPOSE_CM_DEFAULTS``, then logs a warning.
    """
    defaults = _COMPOSE_CM_DEFAULTS.get(name, {})
    # If no field_list requested, return all known defaults for this CM.
    keys_to_return: list[str] = field_list if field_list is not None else list(defaults.keys())

    ret: dict[str, str] = {}
    for key in keys_to_return:
        env_var = f"GETI_CM_{name}_{key}".upper().replace("-", "_").replace(".", "_")
        value = os.getenv(env_var) or defaults.get(key)
        if value is not None:
            ret[key] = value
        else:
            logger.warning(
                f"[COMPOSE MODE] Config map {name!r}/{key!r} not found. "
                f"Set env var {env_var!r} or add a default in _COMPOSE_CM_DEFAULTS."
            )
    return ret


def get_config_map(name: str, field_list: list[str] | None = None) -> dict:
    """
    Returns fields from config map
    :param name: K8s config map name
    :param field_list: list of strings with labels. Example: ['password', 'token']
    :return: dict of demanded fields, if field does not exist returns None.
    Example {'password':'intel123', 'token': None}
    :raise: ApiException when config map is not found
    """
    if DEPLOYMENT_MODE == "compose":
        logger.debug(f"[COMPOSE MODE] Reading config map {name!r} from environment / defaults.")
        return _get_config_map_from_env(name=name, field_list=field_list)

    k8s_api = K8S.get_k8s_api()
    ret: dict[str, str] = {}
    try:
        config_map = k8s_api.read_namespaced_config_map(namespace=K8S_CR_NAMESPACE, name=name)
    except ApiException as ex:
        logger.info(f"Could not found configmap: {name}: {ex}")
        return ret

    # return whole cm when field_list is empty
    if field_list is None:
        return config_map.data

    for field in field_list:
        if field in config_map.data:
            ret[field] = config_map.data[field]
        else:
            logger.error(f"Key: {field} does not exist in config_map.data {name}")
    return ret


def update_config_map(name: str, data: dict[str, str]):  # noqa: ANN201
    """
    Update configmap defined by name with parameters from data
    :param name: name of config map to update
    :param data: fields of config map which will be updated
    """
    k8s_api = K8S.get_k8s_api()
    body = {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {"name": name, "namespace": K8S_CR_NAMESPACE},
        "data": data,
    }
    return k8s_api.patch_namespaced_config_map(name=name, namespace=K8S_CR_NAMESPACE, body=body)
