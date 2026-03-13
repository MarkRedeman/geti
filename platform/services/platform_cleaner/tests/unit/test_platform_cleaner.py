"""Tests for platform cleaner compose/K8s behavior."""

# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import importlib
import sys


def test_module_import_skips_incluster_config_in_compose(monkeypatch, mocker):
    monkeypatch.setenv("DEPLOYMENT_MODE", "compose")
    load_incluster_config = mocker.patch("kubernetes_asyncio.config.load_incluster_config")

    sys.modules.pop("platform_cleaner", None)
    module = importlib.import_module("platform_cleaner")
    importlib.reload(module)

    load_incluster_config.assert_not_called()


def test_module_import_loads_incluster_config_outside_compose(monkeypatch, mocker):
    monkeypatch.delenv("DEPLOYMENT_MODE", raising=False)
    load_incluster_config = mocker.patch("kubernetes_asyncio.config.load_incluster_config")

    sys.modules.pop("platform_cleaner", None)
    module = importlib.import_module("platform_cleaner")
    importlib.reload(module)

    assert load_incluster_config.called
