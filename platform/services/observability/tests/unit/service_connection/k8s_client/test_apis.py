# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import pytest

from service_connection.k8s_client.apis import K8S


def reset_k8s_singletons() -> None:
    K8S._k8s_api = None
    K8S._custom_k8s_api = None
    K8S._ext_k8s_api = None
    K8S._apps_k8s_api = None
    K8S._cord_k8s_api = None


def test_create_k8s_apis_compose_mode_raises(mocker, request):
    request.addfinalizer(reset_k8s_singletons)
    mocker.patch("service_connection.k8s_client.apis.DEPLOYMENT_MODE", "compose")

    with pytest.raises(NotImplementedError, match="compose mode"):
        K8S.create_k8s_apis()


def test_get_k8s_api_compose_mode_raises(mocker, request):
    request.addfinalizer(reset_k8s_singletons)
    mocker.patch("service_connection.k8s_client.apis.DEPLOYMENT_MODE", "compose")

    with pytest.raises(NotImplementedError, match="compose mode"):
        K8S.get_k8s_api()
