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
    assert cfg["mediapipe_config_list"] == []

    manager.remove_model("p1")
    cfg_after = json.loads((tmp_path / "models.json").read_text())
    names_after = [item["config"]["name"] for item in cfg_after["model_config_list"]]
    assert names_after == ["p2"]


def test_add_remove_graph_model(tmp_path, monkeypatch):
    monkeypatch.setenv("OVMS_MODELS_DIR", str(tmp_path))
    manager = OvmsConfigManager()

    graph_dir = tmp_path / "graph-pipeline"
    graph_dir.mkdir()
    (graph_dir / "graph.pbtxt").write_text("graph")
    (graph_dir / "config.json").write_text(
        '{"model_config_list": [{"config": {"name": "submodel-a", "base_path": "submodel-a"}}]}'
    )

    (graph_dir / "submodel-a").mkdir()
    (graph_dir / "submodel-a" / "1").mkdir()
    (graph_dir / "submodel-a" / "1" / "model.xml").write_text("xml")

    manager.add_model("graph-pipeline")

    cfg = json.loads((tmp_path / "models.json").read_text())
    assert cfg["model_config_list"] == [
        {
            "config": {
                "name": "submodel-a",
                "base_path": "/models/graph-pipeline/submodel-a",
            }
        }
    ]
    assert cfg["mediapipe_config_list"] == [{"name": "graph-pipeline"}]

    manager.remove_model("graph-pipeline")
    cfg_after = json.loads((tmp_path / "models.json").read_text())
    assert cfg_after["model_config_list"] == []
    assert cfg_after["mediapipe_config_list"] == []


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


def test_sync_model_directory_keeps_graph_layout(tmp_path, monkeypatch):
    monkeypatch.setenv("OVMS_MODELS_DIR", str(tmp_path))
    manager = OvmsConfigManager()

    source = tmp_path / "graph_source"
    source.mkdir()
    (source / "graph.pbtxt").write_text("graph")
    (source / "config.json").write_text('{"model_config_list": []}')
    (source / "model-a").mkdir()
    (source / "model-a" / "1").mkdir()
    (source / "model-a" / "1" / "model.xml").write_text("xml")

    manager.sync_model_directory("pipeline", source)

    assert (tmp_path / "pipeline" / "model-a" / "1" / "model.xml").exists()
    assert not (tmp_path / "pipeline" / "1" / "model.xml").exists()


def test_sync_model_directory_normalizes_plain_model_layout(tmp_path, monkeypatch):
    monkeypatch.setenv("OVMS_MODELS_DIR", str(tmp_path))
    manager = OvmsConfigManager()

    source = tmp_path / "plain_source"
    source.mkdir()
    (source / "model-a").mkdir()
    (source / "model-a" / "1").mkdir()
    (source / "model-a" / "1" / "model.xml").write_text("xml")

    manager.sync_model_directory("pipeline", source)

    assert (tmp_path / "pipeline" / "1" / "model.xml").exists()
    assert not (tmp_path / "pipeline" / "model-a").exists()
