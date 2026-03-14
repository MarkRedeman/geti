# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

"""
Unit tests for the common.platform module.
"""

from datetime import datetime, timezone
from unittest.mock import Mock

from kubernetes.client import CoreV1Api

from common.platform import _COMPOSE_INSTALL_EPOCH, get_installation_datetime

_PATCH_TARGET = "common.platform"


def test_get_installation_datetime(mocker):
    """Tests the get_installation_datetime function."""
    datetime_expected = Mock(datetime)
    mock_config_map = Mock(metadata=Mock(creation_timestamp=datetime_expected))
    k8s_api = Mock(CoreV1Api, read_namespaced_config_map=Mock(side_effect=[mock_config_map]))
    mock_get_k8s_api = mocker.patch(f"{_PATCH_TARGET}.K8S.get_k8s_api", side_effect=[k8s_api])

    mock_cm_name = "mock_cm_name"
    mock_namespace = "mock_ns"
    mocker.patch(f"{_PATCH_TARGET}.IMPT_CONFIGURATION_CM", mock_cm_name)
    mocker.patch(f"{_PATCH_TARGET}.K8S_CR_NAMESPACE", mock_namespace)

    datetime_actual = get_installation_datetime()

    assert datetime_actual == datetime_expected
    mock_get_k8s_api.assert_called_once_with()
    k8s_api.read_namespaced_config_map.assert_called_once_with(name=mock_cm_name, namespace=mock_namespace)


def test_get_installation_datetime_compose_returns_epoch(mocker):
    """In compose mode with no env override, the fixed epoch is returned."""
    mocker.patch(f"{_PATCH_TARGET}.DEPLOYMENT_MODE", "compose")
    mocker.patch(f"{_PATCH_TARGET}.os.getenv", return_value=None)

    result = get_installation_datetime()

    assert result == _COMPOSE_INSTALL_EPOCH


def test_get_installation_datetime_compose_uses_env_var(mocker):
    """In compose mode, PLATFORM_INSTALLATION_DATETIME env var overrides the epoch."""
    iso_str = "2023-06-15T12:00:00+00:00"
    expected = datetime.fromisoformat(iso_str)

    mocker.patch(f"{_PATCH_TARGET}.DEPLOYMENT_MODE", "compose")
    mocker.patch(f"{_PATCH_TARGET}.os.getenv", return_value=iso_str)

    result = get_installation_datetime()

    assert result == expected


def test_get_installation_datetime_compose_invalid_env_falls_back_to_epoch(mocker):
    """In compose mode, an invalid PLATFORM_INSTALLATION_DATETIME falls back to the epoch."""
    mocker.patch(f"{_PATCH_TARGET}.DEPLOYMENT_MODE", "compose")
    mocker.patch(f"{_PATCH_TARGET}.os.getenv", return_value="not-a-datetime")

    result = get_installation_datetime()

    assert result == _COMPOSE_INSTALL_EPOCH
