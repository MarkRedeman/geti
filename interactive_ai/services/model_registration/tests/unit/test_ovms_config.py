# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import json

from service.ovms_config import OvmsConfigManager


def test_add_remove_model(tmp_path, monkeypatch):
    monkeypatch.setenv("OVMS_MODELS_DIR", str(tmp_path))
    manager = OvmsConfigManager()

    manager.add_model("p1")
    manager.add_model("p2")

    cfg = json.loads((tmp_path / "models.json").read_text())
    names = [item["config"]["name"] for item in cfg["model_config_list"]]
    assert names == ["p1", "p2"]

    manager.remove_model("p1")
    cfg_after = json.loads((tmp_path / "models.json").read_text())
    names_after = [item["config"]["name"] for item in cfg_after["model_config_list"]]
    assert names_after == ["p2"]


def test_sync_and_remove_model_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("OVMS_MODELS_DIR", str(tmp_path))
    manager = OvmsConfigManager()

    source = tmp_path / "source"
    source.mkdir()
    (source / "graph.pbtxt").write_text("data")
    (source / "sub").mkdir()
    (source / "sub" / "weights.bin").write_bytes(b"abc")

    manager.sync_model_directory("pipeline", source)
    assert (tmp_path / "pipeline" / "graph.pbtxt").read_text() == "data"
    assert (tmp_path / "pipeline" / "sub" / "weights.bin").read_bytes() == b"abc"

    manager.remove_model_directory("pipeline")
    assert not (tmp_path / "pipeline").exists()
