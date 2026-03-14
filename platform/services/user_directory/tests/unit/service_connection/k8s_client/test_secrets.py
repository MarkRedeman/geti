# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

"""Unit tests for user_directory k8s_client secrets compose-mode fallback."""

from service_connection.k8s_client.secrets import get_secrets


_PATCH_TARGET = "service_connection.k8s_client.secrets"


def test_get_secrets_compose_mode_reads_env(mocker):
    """In compose mode, get_secrets reads from GETI_SECRET_<NAME>_<KEY> env vars."""
    mocker.patch(f"{_PATCH_TARGET}.DEPLOYMENT_MODE", "compose")
    mocker.patch(
        f"{_PATCH_TARGET}.os.getenv",
        side_effect=lambda k, d=None: {
            "GETI_SECRET_IMPT_JWT_CONFIG_KEY": "my-jwt-secret",
        }.get(k, d),
    )

    result = get_secrets("impt-jwt-config", ["key"])

    assert result == {"key": "my-jwt-secret"}


def test_get_secrets_compose_mode_missing_env_omits_key(mocker):
    """In compose mode, missing env vars are omitted from the result (with a warning logged)."""
    mocker.patch(f"{_PATCH_TARGET}.DEPLOYMENT_MODE", "compose")
    mocker.patch(f"{_PATCH_TARGET}.os.getenv", return_value=None)

    result = get_secrets("impt-jwt-config", ["key"])

    assert result == {}


def test_get_secrets_k8s_mode_reads_namespace(mocker):
    """In non-compose mode, get_secrets delegates to the Kubernetes API."""
    mocker.patch(f"{_PATCH_TARGET}.DEPLOYMENT_MODE", "k8s")
    import base64

    raw = base64.b64encode(b"my-secret-value").decode()
    mock_secret = mocker.MagicMock()
    mock_secret.data = {"key": raw}
    mock_api = mocker.MagicMock()
    mock_api.read_namespaced_secret.return_value = mock_secret
    mocker.patch(f"{_PATCH_TARGET}.K8S.get_k8s_api", return_value=mock_api)
    mocker.patch(f"{_PATCH_TARGET}.convert_from_base_64", return_value="my-secret-value")

    # K8S_CR_NAMESPACE is baked into the default arg at import time, so pass
    # the namespace explicitly to control which value reaches the K8S call.
    result = get_secrets("impt-jwt-config", ["key"], namespace="test-ns")

    assert result == {"key": "my-secret-value"}
    mock_api.read_namespaced_secret.assert_called_once_with(namespace="test-ns", name="impt-jwt-config")
