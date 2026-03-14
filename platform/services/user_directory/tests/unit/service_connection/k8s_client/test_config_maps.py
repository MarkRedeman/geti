# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

"""Unit tests for user_directory k8s_client config_maps compose-mode fallback."""

import pytest

from service_connection.k8s_client.config_maps import get_config_map


_PATCH_TARGET = "service_connection.k8s_client.config_maps"


def test_get_config_map_compose_mode_returns_env_value(mocker):
    """In compose mode, get_config_map reads the value from the env var."""
    mocker.patch(f"{_PATCH_TARGET}.DEPLOYMENT_MODE", "compose")
    mocker.patch(
        f"{_PATCH_TARGET}.os.getenv",
        side_effect=lambda k, d=None: {
            "GETI_CM_IMPT_CONFIGURATION_INVITE_USER_EXPIRATION": "99999",
        }.get(k, d),
    )

    result = get_config_map("impt-configuration", ["invite-user-expiration"])

    assert result == {"invite-user-expiration": "99999"}


def test_get_config_map_compose_mode_falls_back_to_defaults(mocker):
    """In compose mode, missing env vars fall back to _COMPOSE_CM_DEFAULTS."""
    mocker.patch(f"{_PATCH_TARGET}.DEPLOYMENT_MODE", "compose")
    # No env vars set; os.getenv returns None for everything.
    mocker.patch(f"{_PATCH_TARGET}.os.getenv", return_value=None)

    result = get_config_map("impt-configuration", ["invite-user-expiration", "password_reset_expiration"])

    assert result["invite-user-expiration"] == "43200"
    assert result["password_reset_expiration"] == "15"


def test_get_config_map_compose_mode_no_field_list_returns_all_defaults(mocker):
    """In compose mode with field_list=None, all defaults for the CM are returned."""
    mocker.patch(f"{_PATCH_TARGET}.DEPLOYMENT_MODE", "compose")
    mocker.patch(f"{_PATCH_TARGET}.os.getenv", return_value=None)

    result = get_config_map("impt-configuration")

    assert "invite-user-expiration" in result
    assert "password_reset_expiration" in result


def test_get_config_map_k8s_mode_reads_namespace(mocker):
    """In non-compose mode, get_config_map delegates to the Kubernetes API."""
    mocker.patch(f"{_PATCH_TARGET}.DEPLOYMENT_MODE", "k8s")
    mock_cm = mocker.MagicMock()
    mock_cm.data = {"invite-user-expiration": "43200"}
    mock_api = mocker.MagicMock()
    mock_api.read_namespaced_config_map.return_value = mock_cm
    mocker.patch(f"{_PATCH_TARGET}.K8S.get_k8s_api", return_value=mock_api)
    mocker.patch(f"{_PATCH_TARGET}.K8S_CR_NAMESPACE", "test-ns")

    result = get_config_map("impt-configuration", ["invite-user-expiration"])

    assert result == {"invite-user-expiration": "43200"}
    mock_api.read_namespaced_config_map.assert_called_once_with(
        namespace="test-ns", name="impt-configuration"
    )
