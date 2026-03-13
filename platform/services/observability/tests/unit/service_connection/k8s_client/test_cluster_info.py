# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import pytest

from service_connection.k8s_client.cluster_info import create_cluster_info_dump


def test_create_cluster_info_dump_compose_mode_raises(mocker, tmp_path):
    mocker.patch("service_connection.k8s_client.cluster_info.DEPLOYMENT_MODE", "compose")

    with pytest.raises(NotImplementedError, match="compose mode"):
        create_cluster_info_dump(directory=str(tmp_path))
